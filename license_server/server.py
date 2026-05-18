import secrets
import sqlite3
import os
import uuid
import time
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, render_template_string
from yookassa import Configuration as YKConfig, Payment as YKPayment
from yookassa.domain.common import SecurityHelper

log = logging.getLogger("spee4ka.server")

app = Flask(__name__)

DB_PATH = os.environ.get("SPEE4KA_DB", "licenses.db")

ADMIN_PASSWORD = os.environ.get("SPEE4KA_ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    raise RuntimeError("SPEE4KA_ADMIN_PASSWORD env variable is required")

# Simple in-memory rate limiter: 10 requests per IP per 60 seconds
_rate_buckets: dict = defaultdict(list)
_rate_lock = threading.Lock()
_rate_gc_counter = 0
RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 60
_RATE_GC_EVERY = 200  # prune stale IPs every N rate checks


def _is_rate_limited(ip: str) -> bool:
    global _rate_gc_counter
    now = time.time()
    with _rate_lock:
        _rate_gc_counter += 1
        if _rate_gc_counter >= _RATE_GC_EVERY:
            _rate_gc_counter = 0
            stale = [
                k for k, v in _rate_buckets.items()
                if not v or now - v[-1] > RATE_LIMIT_WINDOW
            ]
            for k in stale:
                del _rate_buckets[k]

        bucket = [t for t in _rate_buckets[ip] if now - t < RATE_LIMIT_WINDOW]
        _rate_buckets[ip] = bucket
        if len(bucket) >= RATE_LIMIT_MAX:
            return True
        _rate_buckets[ip].append(now)
        return False

YUKASSA_SHOP_ID = os.environ.get("YUKASSA_SHOP_ID", "")
YUKASSA_SECRET_KEY = os.environ.get("YUKASSA_SECRET_KEY", "")
PRICE_RUB = os.environ.get("SPEE4KA_PRICE_RUB", "990.00")
PROMO_CODE = os.environ.get("SPEE4KA_PROMO_CODE", "")
PROMO_PRICE_RUB = os.environ.get("SPEE4KA_PROMO_PRICE_RUB", "10.00")
BASE_URL = os.environ.get("SPEE4KA_BASE_URL", "https://spee4ka.ru")
LICENSE_DAYS = int(os.environ.get("SPEE4KA_LICENSE_DAYS", "365"))

if YUKASSA_SHOP_ID and YUKASSA_SECRET_KEY:
    YKConfig.configure(YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY)


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            status TEXT DEFAULT 'unused',
            machine_id TEXT,
            activated_at TEXT,
            expires_at TEXT,
            reset_count INTEGER DEFAULT 0,
            last_reset_at TEXT,
            email TEXT,
            order_id TEXT,
            payment_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        -- Partial unique index protects against duplicate webhook deliveries from YuKassa.
        CREATE UNIQUE INDEX IF NOT EXISTS idx_licenses_order_id
            ON licenses(order_id) WHERE order_id IS NOT NULL AND order_id != '';
    """)
    conn.commit()
    conn.close()


_init_db()


def generate_key() -> str:
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "SP4K-" + "-".join(parts)


def _admin_password_from_request() -> str:
    # Prefer header to keep the password out of nginx access logs.
    # Query-string fallback is retained only for legacy clients/bookmarks.
    pwd = request.headers.get("X-Admin-Password", "")
    if not pwd:
        body = request.get_json(silent=True) or {}
        pwd = body.get("admin_password", "")
    if not pwd:
        pwd = request.args.get("admin", "")
    return pwd


def _admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        pwd = _admin_password_from_request()
        if pwd != ADMIN_PASSWORD:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/activate", methods=["POST"])
def api_activate():
    ip = request.headers.get("X-Real-IP") or request.remote_addr
    if _is_rate_limited(ip):
        return jsonify({"valid": False, "error": "too_many_requests"}), 429

    data = request.json or {}
    key = (data.get("key") or "").strip().upper()
    machine_id = (data.get("machine_id") or "").strip()

    if not key or not machine_id:
        return jsonify({"valid": False, "error": "key and machine_id required"}), 400

    conn = _get_db()
    row = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"valid": False, "error": "key_not_found"}), 404

    if row["status"] == "unused":
        conn.execute(
            "UPDATE licenses SET status='active', machine_id=?, activated_at=datetime('now') WHERE key=?",
            (machine_id, key),
        )
        conn.commit()
        expires = row["expires_at"] or ""
        conn.close()
        return jsonify({"valid": True, "expires": expires})

    if row["status"] == "active":
        if row["machine_id"] == machine_id:
            expires = row["expires_at"] or ""
            conn.close()
            return jsonify({"valid": True, "expires": expires})
        conn.close()
        # Same error code for "not found" and "wrong device" — prevents enumeration
        return jsonify({"valid": False, "error": "key_not_found"}), 404

    conn.close()
    return jsonify({"valid": False, "error": "key_not_found"}), 404


@app.route("/api/check", methods=["POST"])
def api_check():
    ip = request.headers.get("X-Real-IP") or request.remote_addr
    if _is_rate_limited(ip):
        return jsonify({"valid": False, "error": "too_many_requests"}), 429

    data = request.json or {}
    key = (data.get("key") or "").strip().upper()
    machine_id = (data.get("machine_id") or "").strip()

    if not key or not machine_id:
        return jsonify({"valid": False, "error": "key and machine_id required"}), 400

    conn = _get_db()
    row = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"valid": False, "error": "key not found"}), 404

    if row["status"] != "active":
        return jsonify({"valid": False, "error": f"key status: {row['status']}"}), 403

    if row["machine_id"] != machine_id:
        return jsonify({"valid": False, "error": "machine_id mismatch"}), 403

    if row["expires_at"]:
        try:
            exp = datetime.fromisoformat(row["expires_at"])
            if exp < datetime.utcnow():
                return jsonify({"valid": False, "error": "license expired"}), 403
        except ValueError:
            pass

    return jsonify({"valid": True, "expires": row["expires_at"] or ""})


@app.route("/api/generate", methods=["POST"])
@_admin_required
def api_generate():
    data = request.json or {}
    count = min(data.get("count", 1), 100)
    days = data.get("days", 365)
    email = data.get("email", "")
    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()

    conn = _get_db()
    keys = []
    for _ in range(count):
        key = generate_key()
        conn.execute(
            "INSERT INTO licenses (key, expires_at, email) VALUES (?, ?, ?)",
            (key, expires, email),
        )
        keys.append(key)
    conn.commit()
    conn.close()

    return jsonify({"keys": keys, "expires": expires})


@app.route("/api/reset", methods=["POST"])
@_admin_required
def api_reset():
    key = (request.json or {}).get("key", "").strip().upper()
    if not key:
        return jsonify({"error": "key required"}), 400

    conn = _get_db()
    row = conn.execute("SELECT * FROM licenses WHERE key = ?", (key,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "key not found"}), 404

    conn.execute(
        "UPDATE licenses SET machine_id=NULL, status='unused', reset_count=reset_count+1, last_reset_at=datetime('now') WHERE key=?",
        (key,),
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "key": key})


@app.route("/api/delete", methods=["POST"])
@_admin_required
def api_delete():
    key = (request.json or {}).get("key", "").strip().upper()
    if not key:
        return jsonify({"error": "key required"}), 400

    conn = _get_db()
    row = conn.execute("SELECT key FROM licenses WHERE key = ?", (key,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "key not found"}), 404

    conn.execute("DELETE FROM licenses WHERE key = ?", (key,))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "key": key})


@app.route("/api/list", methods=["GET"])
@_admin_required
def api_list():
    conn = _get_db()
    rows = conn.execute(
        "SELECT key, status, machine_id, activated_at, expires_at, reset_count, email, created_at FROM licenses ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify({"licenses": [dict(r) for r in rows]})


@app.route("/api/create-payment", methods=["POST"])
def api_create_payment():
    if not YUKASSA_SHOP_ID:
        return jsonify({"error": "payment not configured"}), 503

    data = request.json or {}
    email = ""
    promo = (data.get("promo") or "").strip().upper()
    if PROMO_CODE and promo == PROMO_CODE.upper():
        price = PROMO_PRICE_RUB
        promo_applied = True
    else:
        price = PRICE_RUB
        promo_applied = False

    order_id = str(uuid.uuid4())
    try:
        payment = YKPayment.create({
            "amount": {"value": price, "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": f"{BASE_URL}/thanks?order_id={order_id}",
            },
            "capture": True,
            "description": "Лицензия Спичка — бессрочно",
            "metadata": {"email": email, "order_id": order_id},
        }, order_id)
    except Exception as ex:
        log.error(f"YuKassa create payment error: {ex}")
        return jsonify({"error": "payment service error"}), 502

    return jsonify({
        "payment_id": payment.id,
        "order_id": order_id,
        "confirmation_url": payment.confirmation.confirmation_url,
        "promo_applied": promo_applied,
        "price": price,
    })


@app.route("/api/payment", methods=["POST"])
def payment_webhook():
    client_ip = request.headers.get("X-Real-IP") or request.remote_addr
    if not SecurityHelper().is_ip_trusted(client_ip):
        log.warning(f"Webhook from untrusted IP: {client_ip}")
        return jsonify({"error": "forbidden"}), 403

    payload = request.json or {}
    event = payload.get("event", "")
    obj = payload.get("object", {})
    payment_id = obj.get("id", "")

    if event != "payment.succeeded" or not payment_id:
        return jsonify({"ok": True})

    try:
        payment = YKPayment.find_one(payment_id)
    except Exception as ex:
        log.error(f"YuKassa find_one error: {ex}")
        return jsonify({"error": "cannot verify payment"}), 502

    if payment.status != "succeeded":
        return jsonify({"ok": True})

    metadata = dict(payment.metadata) if payment.metadata else {}
    order_id = metadata.get("order_id", "")
    email = metadata.get("email", "")

    conn = _get_db()
    existing = conn.execute(
        "SELECT key FROM licenses WHERE order_id = ?", (order_id,)
    ).fetchone()
    if existing:
        conn.close()
        log.info(f"Duplicate webhook for order={order_id}, ignored")
        return jsonify({"ok": True})

    key = generate_key()
    expires = (datetime.utcnow() + timedelta(days=LICENSE_DAYS)).isoformat()
    try:
        conn.execute(
            "INSERT INTO licenses (key, expires_at, email, order_id, payment_id) VALUES (?, ?, ?, ?, ?)",
            (key, expires, email, order_id, payment_id),
        )
        conn.commit()
        log.info(f"License issued: {key[:9]}... order={order_id} email={email}")
    except sqlite3.IntegrityError:
        # Race: a parallel webhook delivery beat us to the UNIQUE order_id index.
        log.info(f"Concurrent webhook for order={order_id}, ignored")
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/thanks")
def thanks_page():
    order_id = request.args.get("order_id", "").strip()
    key = None
    if order_id:
        conn = _get_db()
        row = conn.execute(
            "SELECT key FROM licenses WHERE order_id = ?", (order_id,)
        ).fetchone()
        conn.close()
        if row:
            key = row["key"]
    return render_template_string(THANKS_HTML, key=key, order_id=order_id)


THANKS_HTML = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>Спасибо за покупку — Спичка</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Segoe UI,sans-serif;max-width:560px;margin:80px auto;padding:0 24px;text-align:center;background:#f7f7f7;color:#222}
h1{font-size:2rem;margin-bottom:8px}
.sub{color:#666;margin-bottom:40px}
.key-box{background:#fff;border:2px solid #2a7;border-radius:12px;padding:28px;margin:24px 0}
.key{font-family:Consolas,monospace;font-size:1.5rem;letter-spacing:2px;color:#1a1a1a;user-select:all}
.copy-btn{margin-top:16px;padding:10px 28px;background:#2a7;color:#fff;border:none;border-radius:8px;font-size:1rem;cursor:pointer}
.copy-btn:hover{background:#3b8}
.waiting{color:#888;font-size:.95rem;margin-top:32px}
.step{text-align:left;background:#fff;border-radius:12px;padding:20px 24px;margin-top:24px;line-height:1.9}
</style>
{% if key %}
<script>
function copyKey(){navigator.clipboard.writeText('{{key}}');const b=document.getElementById('cbtn');b.textContent='Скопировано!';setTimeout(()=>b.textContent='Скопировать',2000)}
localStorage.removeItem('spee4ka_order_id');
</script>
{% else %}
<script>
(function(){
  var params = new URLSearchParams(location.search);
  var oid = params.get('order_id');
  if(!oid){
    oid = localStorage.getItem('spee4ka_order_id');
    if(oid){ location.replace('/thanks?order_id='+oid); return; }
  }
  setTimeout(function(){ location.reload(); }, 6000);
})();
</script>
{% endif %}
</head><body>
<h1>{% if key %}Спасибо за покупку!{% else %}Обрабатываем платёж…{% endif %}</h1>
<p class="sub">{% if key %}Ваш лицензионный ключ Спичка<br><small style="color:#c0392b;font-weight:600">Сохраните ключ — он показывается один раз</small>{% else %}Страница обновится автоматически через несколько секунд{% endif %}</p>

{% if key %}
<div class="key-box">
  <div class="key" id="key">{{key}}</div>
  <button class="copy-btn" id="cbtn" onclick="copyKey()">Скопировать</button>
</div>
<div class="step">
  <b>Шаг 1 — Скачайте и установите Спичку:</b><br><br>
  <a href="https://github.com/Dmitrybell77/spee4ka/releases/latest/download/Spee4ka_Setup.exe"
     style="display:inline-block;padding:12px 32px;background:#4338ca;color:#fff;border-radius:8px;text-decoration:none;font-size:1rem;font-weight:600;">
    ⬇ Скачать Спичку для Windows
  </a><br>
  <span style="color:#888;font-size:.85rem;">Запустите Spee4ka_Setup.exe и следуйте инструкции установщика</span>
</div>
<div class="step" style="margin-top:12px;">
  <b>Шаг 2 — Активируйте лицензию:</b><br>
  1. Запустите Спичку — найдите иконку микрофона в трее<br>
  2. Правая кнопка → <b>Настройки</b><br>
  3. Введите ключ в поле «Лицензионный ключ» → <b>Активировать</b><br>
  4. Сохраните ключ — он показывается один раз
</div>
<div class="step" style="margin-top:12px;">
  <b>Шаг 3 — Настройте Яндекс API (опционально):</b><br>
  Подключите Яндекс для более точного распознавания и полировки текста.<br>
  <a href="/instruction.html" target="_blank" rel="noopener" style="color:#4338CA;font-weight:600">Читать инструкцию по подключению →</a>
</div>
<div class="step" style="margin-top:16px;font-size:.9rem;color:#555">
  🧾 <b>Нужен чек?</b> Напишите на <a href="mailto:info@spee4ka.ru">info@spee4ka.ru</a> — пришлём в течение дня.
</div>
{% else %}
<div class="waiting">⏳ Ожидаем подтверждение от платёжной системы…</div>
<div style="margin-top:40px;padding:20px;background:#fff;border-radius:12px;font-size:.9rem;">
  <b>Оплатили через СБП или мобильный банк?</b><br>
  <span style="color:#888;">Введите номер заказа — он был в ссылке после оплаты</span><br><br>
  <input id="oid" type="text" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    style="width:100%;box-sizing:border-box;padding:10px;border:1.5px solid #ddd;border-radius:8px;font-size:.85rem;font-family:monospace;">
  <button onclick="goOrder()" style="margin-top:10px;width:100%;padding:10px;background:#4338ca;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.95rem;">
    Найти мой ключ
  </button>
</div>
<script>
function goOrder(){
  var v=document.getElementById('oid').value.trim();
  if(v) location.href='/thanks?order_id='+encodeURIComponent(v);
}
</script>
{% endif %}
</body></html>
"""


@app.route("/admin")
def admin_page():
    return render_template_string(ADMIN_HTML)


ADMIN_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Спичка — Admin</title>
<style>
body{font-family:Segoe UI,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#f5f5f5}
h1,h2{color:#333}
table{width:100%;border-collapse:collapse;background:#fff}
th,td{padding:8px 12px;border:1px solid #ddd;text-align:left;font-size:13px}
th{background:#444;color:#fff}
tr:nth-child(even){background:#f9f9f9}
input,button{padding:8px 12px;margin:4px;font-size:14px}
button{background:#444;color:#fff;border:none;cursor:pointer;border-radius:4px}
button:hover{background:#666}
.gen{background:#2a7;border-radius:4px}
.gen:hover{background:#3b8}
.reset{background:#c44;border-radius:4px}
.reset:hover{background:#d55}
.del{background:none;border:none;color:#aaa;font-size:13px;cursor:pointer;padding:2px 5px;border-radius:3px;line-height:1}
.del:hover{color:#c44;background:#fee}
.msg{padding:8px;margin:8px 0;border-radius:4px}
.ok{background:#dfd;color:#060}
.err{background:#fdd;color:#600}
#login{max-width:360px;margin:120px auto;background:#fff;padding:32px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.1);text-align:center}
#login h2{margin-top:0}
#login input{width:100%;box-sizing:border-box;margin:8px 0}
#login button{width:100%;margin-top:8px}
#panel{display:none}
</style>
</head><body>

<div id="login">
  <h2>Спичка Admin</h2>
  <input id="pwd-input" type="password" placeholder="Пароль" onkeydown="if(event.key==='Enter')login()">
  <button onclick="login()">Войти</button>
  <div id="login-err" class="msg err" style="display:none">Неверный пароль</div>
</div>

<div id="panel">
<h1>Спичка License Admin</h1>

<h2>Generate Keys</h2>
<input id="count" type="number" value="1" min="1" max="100" placeholder="Count">
<input id="days" type="number" value="365" min="1" placeholder="Days">
<input id="email" type="email" placeholder="Email (optional)">
<button class="gen" onclick="generate()">Generate</button>
<div id="gen-msg"></div>

<h2>Licenses</h2>
<button onclick="loadList()">Refresh</button>
<div id="list-msg"></div>
<table><thead><tr>
<th></th><th>Key</th><th>Status</th><th>Machine ID</th><th>Создан</th><th>Activated</th><th>Expires</th><th>Resets</th><th>Email</th><th>Action</th>
</tr></thead><tbody id="tbody"></tbody></table>
</div>

<script>
let P = sessionStorage.getItem('adm') || '';
if(P) tryEnter();

function login(){
  P = document.getElementById('pwd-input').value;
  tryEnter();
}

function authHeaders(extra){
  const h = Object.assign({'X-Admin-Password': P}, extra || {});
  return h;
}

async function tryEnter(){
  const r = await fetch('/api/list', {headers: authHeaders()});
  if(r.status === 401){
    document.getElementById('login-err').style.display='block';
    P = '';
    sessionStorage.removeItem('adm');
    return;
  }
  sessionStorage.setItem('adm', P);
  document.getElementById('login').style.display='none';
  document.getElementById('panel').style.display='block';
  const d = await r.json();
  renderList(d.licenses||[]);
}

async function generate(){
 const r=await fetch('/api/generate',{
  method:'POST',
  headers: authHeaders({'Content-Type':'application/json'}),
  body:JSON.stringify({count:+document.getElementById('count').value,days:+document.getElementById('days').value,email:document.getElementById('email').value})
 });
 const d=await r.json();
 const m=document.getElementById('gen-msg');
 if(d.keys){m.innerHTML='<div class="msg ok">Keys: '+d.keys.join('<br>')+'</div>'}
 else{m.innerHTML='<div class="msg err">'+(d.error||'Error')+'</div>'}
}

async function loadList(){
 const r=await fetch('/api/list', {headers: authHeaders()});
 const d=await r.json();
 renderList(d.licenses||[]);
}

function renderList(licenses){
 const tb=document.getElementById('tbody');
 tb.innerHTML='';
 licenses.forEach(l=>{
  const tr=document.createElement('tr');
  tr.innerHTML=`<td><button class="del" onclick="deleteKey('${l.key}')" title="Удалить ключ">✕</button></td><td>${l.key}</td><td>${l.status}</td><td>${l.machine_id||'—'}</td><td>${l.created_at||'—'}</td><td>${l.activated_at||'—'}</td><td>${l.expires_at||'—'}</td><td>${l.reset_count}</td><td>${l.email||'—'}</td><td>${l.status==='active'?'<button class=\"reset\" onclick=\"resetKey(\\''+l.key+'\\')\">Reset</button>':''}</td>`;
  tb.appendChild(tr);
 });
}

async function resetKey(key){
 if(!confirm('Reset binding for '+key+'?'))return;
 const r=await fetch('/api/reset',{
  method:'POST',
  headers: authHeaders({'Content-Type':'application/json'}),
  body:JSON.stringify({key})
 });
 const d=await r.json();
 if(d.ok){loadList()}else{alert(d.error||'Error')}
}

async function deleteKey(key){
 if(!confirm('Удалить ключ '+key+'?\nЭто действие необратимо.'))return;
 const r=await fetch('/api/delete',{
  method:'POST',
  headers: authHeaders({'Content-Type':'application/json'}),
  body:JSON.stringify({key})
 });
 const d=await r.json();
 if(d.ok){loadList()}else{alert(d.error||'Error')}
}
</script>
</body></html>
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

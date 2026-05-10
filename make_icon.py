"""Generate spee4ka.ico — microphone icon at 16/32/48/64/128/256px."""
from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).parent / "spee4ka.ico"
BG_COLOR  = (45, 45, 48, 255)    # dark charcoal background
MIC_COLOR = (255, 255, 255, 255) # white mic
ACC_COLOR = (80, 180, 255, 255)  # blue accent ring


def draw_mic(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size

    # --- background circle ---
    pad = max(1, s // 16)
    d.ellipse([pad, pad, s - pad - 1, s - pad - 1],
              fill=BG_COLOR, outline=ACC_COLOR, width=max(1, s // 32))

    # --- mic capsule (rounded rect) ---
    cw  = s * 0.28          # capsule width
    ch  = s * 0.38          # capsule height
    cx  = s / 2             # center x
    cy  = s * 0.38          # capsule center y
    r   = cw / 2            # corner radius = half-width → pill shape
    x0, y0 = cx - cw / 2, cy - ch / 2
    x1, y1 = cx + cw / 2, cy + ch / 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=MIC_COLOR)

    # --- stand: U-arc ---
    aw  = s * 0.46          # arc bounding box width
    ah  = s * 0.26          # arc height
    ax0 = cx - aw / 2
    ax1 = cx + aw / 2
    ay0 = y0 + s * 0.12     # top of arc bounding box
    ay1 = ay0 + ah
    lw  = max(1, round(s * 0.055))
    d.arc([ax0, ay0, ax1, ay1], start=0, end=180, fill=MIC_COLOR, width=lw)

    # --- vertical stem from arc midpoint down ---
    stem_top  = ay0 + ah / 2
    stem_bot  = s * 0.78
    d.line([(cx, stem_top), (cx, stem_bot)], fill=MIC_COLOR, width=lw)

    # --- base horizontal bar ---
    bw  = s * 0.34
    d.line([(cx - bw / 2, stem_bot), (cx + bw / 2, stem_bot)],
           fill=MIC_COLOR, width=lw)

    return img


img_big = draw_mic(256)
img_big.save(OUT, format="ICO", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print(f"Saved {OUT}  ({OUT.stat().st_size // 1024} KB)")

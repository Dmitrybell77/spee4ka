"""
Convert logo_c.svg to spee4ka.ico using only Pillow.
Rasterises the flame path by computing Bezier points, draws mic body and stick.
"""
from PIL import Image, ImageDraw
import math

# SVG viewBox: 0 0 100 118
VW, VH = 100, 118


def cubic_bezier_points(p0, p1, p2, p3, steps=40):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def flame_polygon():
    """Return list of (x,y) points approximating the flame SVG path."""
    segs = [
        # P0           P1           P2           P3
        ((50,115), (24,115), ( 8,101), ( 8, 80)),
        (( 8, 80), ( 8, 58), (16, 40), (24, 26)),
        ((24, 26), (28, 18), (30, 10), (32,  4)),
        ((32,  4), (34,  1), (37,  1), (40,  5)),
        ((40,  5), (42,  9), (43, 16), (44, 24)),
        ((44, 24), (47, 17), (52, 11), (56, 15)),
        ((56, 15), (60, 10), (63,  9), (65, 14)),
        ((65, 14), (67, 20), (65, 31), (61, 39)),
        ((61, 39), (69, 33), (79, 29), (83, 37)),
        ((83, 37), (89, 49), (92, 67), (90, 83)),
        ((90, 83), (89,101), (83,113), (69,116)),
        ((69,116), (62,118), (56,117), (50,115)),
    ]
    pts = []
    for seg in segs:
        pts.extend(cubic_bezier_points(*seg)[:-1])  # skip last to avoid dup
    pts.append((50, 115))
    return pts


def scale_pts(pts, size):
    sx = size / VW
    sy = size / VH
    return [(x * sx, y * sy) for x, y in pts]


def gradient_pixel(x, y, size):
    """Linear gradient from top-left to bottom-right: #4338CA → #818CF8."""
    stops = [
        (0.00, (0x43, 0x38, 0xCA)),
        (0.35, (0x7C, 0x3A, 0xED)),
        (0.68, (0xA8, 0x55, 0xF7)),
        (1.00, (0x81, 0x8C, 0xF8)),
    ]
    t = (x + y) / (2 * size)
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return (r, g, b, 255)
    return (0x81, 0x8C, 0xF8, 255)


def rounded_rect(draw, x0, y0, x1, y1, rx, fill, size_scale):
    rx = rx * size_scale
    draw.rounded_rectangle([x0, y0, x1, y1], radius=rx, fill=fill)


def render(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    sx = size / VW
    sy = size / VH

    # --- Draw gradient flame ---
    # First draw solid purple flame, then overlay gradient via pixel mask
    flame_pts = scale_pts(flame_polygon(), size)
    # Draw flame with base colour
    draw.polygon(flame_pts, fill=(0x43, 0x38, 0xCA, 255))

    # Apply gradient: create gradient layer, mask with flame shape
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad_data = []
    for py in range(size):
        for px in range(size):
            grad_data.append(gradient_pixel(px, py, size))
    grad.putdata(grad_data)

    flame_mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(flame_mask)
    mask_draw.polygon(flame_pts, fill=255)

    img.paste(grad, (0, 0), flame_mask)

    # --- Mic body (white rounded rect) ---
    # SVG: x=33 y=64 w=34 h=27 rx=13.5
    mx0 = 33 * sx
    my0 = 64 * sy
    mx1 = (33 + 34) * sx
    my1 = (64 + 27) * sy
    mrx = 13.5
    draw.rounded_rectangle([mx0, my0, mx1, my1], radius=mrx * sx, fill=(255, 255, 255, 255))

    # --- Stripes (gradient, clipped to mic body) ---
    stripe_col = gradient_pixel(int((mx0 + mx1) / 2), int((my0 + my1) / 2), size)
    for sy_off in [69, 84]:
        s0 = sy_off * sy
        s1 = (sy_off + 3.5) * sy
        # clamp to mic body
        s0 = max(s0, my0)
        s1 = min(s1, my1)
        if s1 > s0:
            draw.rectangle([mx0, s0, mx1, s1], fill=stripe_col)

    # --- Stick (white rounded rect) ---
    # SVG: x=47.5 y=91 w=5 h=21 rx=2.5
    stx0 = 47.5 * sx
    sty0 = 91 * sy
    stx1 = (47.5 + 5) * sx
    sty1 = (91 + 21) * sy
    draw.rounded_rectangle([stx0, sty0, stx1, sty1], radius=2.5 * sx, fill=(255, 255, 255, 255))

    return img


def main():
    sizes = [256, 128, 64, 48, 32, 16]
    frames = []
    for s in sizes:
        img = render(s)
        frames.append(img)

    out = "d:/YandexDisk/ВАЙБ-КОДИНГ/Govorun 2.1/spee4ka.ico"
    frames[0].save(
        out,
        format="ICO",
        append_images=frames[1:],
        sizes=[(s, s) for s in sizes],
    )
    print(f"Saved {out}")
    print(f"Sizes: {sizes}")


if __name__ == "__main__":
    main()

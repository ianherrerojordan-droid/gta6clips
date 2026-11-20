import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
F = "/tmp/claude-0/-home-user-gta6clips/295e1aaf-2fba-54fa-acd8-e1ec37a4c90c/scratchpad/fonts/"
OUT = "/home/user/gta6clips/canal/"

def grad_v(w, h, cols):
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(h - 1, 1) * (len(cols) - 1); k = min(int(t), len(cols) - 2); f = t - k
        c = tuple(int(cols[k][i] + (cols[k + 1][i] - cols[k][i]) * f) for i in range(3))
        d.line([(0, y), (w, y)], fill=c)
    return im

def mascara_texto(size, xy, txt, font, anchor="mm", stroke=0):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).text(xy, txt, font=font, fill=255, anchor=anchor, stroke_width=stroke, stroke_fill=255)
    return m

def palabra_gta(im, xy, txt, font, cols, prof=18, borde=10, glow=(255, 40, 140)):
    """Texto con relleno degradado, borde negro grueso y extrusion 3D hacia abajo-derecha."""
    W, H = im.size
    m_fill = mascara_texto((W, H), xy, txt, font)
    bb = m_fill.getbbox()
    m_out = mascara_texto((W, H), xy, txt, font, stroke=borde)
    # brillo
    g = Image.new("RGBA", (W, H), glow + (0,)); g.putalpha(m_out.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.8)))
    im.alpha_composite(g)
    # extrusion
    for k in range(prof, 0, -1):
        capa = Image.new("RGBA", (W, H), (60, 8, 60, 255) if k > 2 else (20, 2, 25, 255))
        capa.putalpha(ImageChops.offset(m_out, k, k))
        im.alpha_composite(capa)
    negro = Image.new("RGBA", (W, H), (12, 2, 18, 255)); negro.putalpha(m_out); im.alpha_composite(negro)
    gr = grad_v(bb[2] - bb[0], bb[3] - bb[1], cols).convert("RGBA")
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0)); full.paste(gr, (bb[0], bb[1]))
    full.putalpha(m_fill); im.alpha_composite(full)
    # reflejo blanco arriba
    hl = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    mh = Image.new("L", (W, H), 0); ImageDraw.Draw(mh).rectangle([0, bb[1], W, bb[1] + (bb[3] - bb[1]) * 0.18], fill=70)
    hl.putalpha(ImageChops.multiply(mh, m_fill)); im.alpha_composite(hl)

def estrellas(im, cx, cy, r, n=6):
    gap = r * 2.4; x0 = cx - gap * (n - 1) / 2
    d = ImageDraw.Draw(im)
    for k in range(n):
        x = x0 + k * gap
        pts = [(x + (r if j % 2 == 0 else r * 0.45) * math.cos(math.radians(-90 + j * 36)),
                cy + (r if j % 2 == 0 else r * 0.45) * math.sin(math.radians(-90 + j * 36))) for j in range(10)]
        d.polygon([(px + 4, py + 4) for px, py in pts], fill=(10, 2, 15))
        d.polygon(pts, fill=(255, 255, 255), outline=(10, 2, 15), width=max(3, r // 8))

def fondo(w, h):
    im = grad_v(w, h, [(18, 6, 38), (70, 12, 80), (160, 30, 110), (250, 110, 90)]).convert("RGBA")
    d = ImageDraw.Draw(im)
    for y in range(0, h, 6):  # lineas tipo VHS
        d.line([(0, y), (w, y)], fill=(0, 0, 0, 28))
    return im

ROSA_NARANJA = [(255, 70, 170), (255, 90, 120), (255, 150, 60), (255, 215, 90)]
CIAN = [(160, 250, 255), (60, 200, 255)]

# ---------- foto de perfil 1024
W = 1024
im = fondo(W, W)
estrellas(im, W // 2, 180, 40)
palabra_gta(im, (W // 2, 430), "FACTS", ImageFont.truetype(F + "BowlbyOneSC-Regular.ttf", 228), ROSA_NARANJA, prof=20, borde=14)
palabra_gta(im, (W // 2, 720), "VICE CITY", ImageFont.truetype(F + "BowlbyOneSC-Regular.ttf", 132), CIAN, prof=12, borde=10, glow=(0, 180, 255))
im.convert("RGB").save(OUT + "en_foto_perfil.png")

def palmera(d, x, base, alto, inc, g, col=(14, 3, 22)):
    pts = [(x + inc * (i / 20) ** 2, base - alto * i / 20) for i in range(21)]
    for i in range(20):
        d.line([pts[i], pts[i + 1]], fill=col, width=int(g * (1 - i / 30)))
    tx, ty = pts[-1]
    for ang in [200, 225, 250, 290, 315, 340, 20, 160]:
        a = math.radians(ang); L = alto * 0.45
        h = [(tx + math.cos(a) * L * t, ty + math.sin(a) * L * t * 0.6 + L * 0.5 * t * t) for t in [i / 12 for i in range(13)]]
        for i in range(12):
            d.line([h[i], h[i + 1]], fill=col, width=max(2, int(g * 1.4 * (1 - i / 13))))

# ---------- banner 2560x1440
W, H = 2560, 1440
im = fondo(W, H)
import random; random.seed(3)
sol = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sol)
ds.ellipse([W // 2 - 420, 640, W // 2 + 420, 1480], fill=(255, 190, 90, 150))
sol = sol.filter(ImageFilter.GaussianBlur(60)); im.alpha_composite(sol)
d = ImageDraw.Draw(im)
x = 0
while x < W:
    bw = random.randint(50, 130); bh = random.randint(90, 360)
    d.rectangle([x, 1180 - bh, x + bw, 1440], fill=(28, 6, 44))
    for wy in range(1180 - bh + 20, 1170, 34):
        for wx in range(x + 10, x + bw - 10, 26):
            if random.random() < 0.25: d.rectangle([wx, wy, wx + 8, wy + 12], fill=(255, 170, 120))
    x += bw + random.randint(2, 10)
d.rectangle([0, 1180, W, H], fill=(16, 3, 26))
for px, alto, inc, g in [(150, 1000, 110, 34), (420, 760, -70, 26), (2150, 780, 80, 26), (2420, 1040, -120, 34)]:
    palmera(d, px, 1300, alto, inc, g)
# zona visible en TODOS los dispositivos: 1546x423 centrada -> x 507-2053, y 508-931
ZX0, ZX1, ZY0, ZY1 = 507 + 60, 2053 - 60, 508 + 18, 931 - 18
fb = ImageFont.truetype(F + "BowlbyOneSC-Regular.ttf", 200)
while ImageDraw.Draw(im).textbbox((0, 0), "VICE CITY FACTS", font=fb, stroke_width=12)[2] > (ZX1 - ZX0) - 40:
    fb = ImageFont.truetype(F + "BowlbyOneSC-Regular.ttf", fb.size - 4)
estrellas(im, W // 2, ZY0 + 34, 30)
palabra_gta(im, (W // 2, 712), "VICE CITY FACTS", fb, ROSA_NARANJA, prof=14, borde=12)
fs = ImageFont.truetype(F + "Anton.ttf", 64)
ImageDraw.Draw(im).text((W // 2 + 3, ZY1 - 32 + 3), "A NEW GTA 6 FACT EVERY DAY", font=fs, fill=(10, 2, 15), anchor="mm")
ImageDraw.Draw(im).text((W // 2, ZY1 - 32), "A NEW GTA 6 FACT EVERY DAY", font=fs, fill=(255, 255, 255), anchor="mm")
im.convert("RGB").save(OUT + "en_banner.png")
print("ok")

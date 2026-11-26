"""Erzeugt das Website-Icon (Monogramm „s=“, weiß kursiv auf Schwarz) einmalig nach skripte/favicon/:
favicon.svg, favicon.ico (16/32/48 px), apple-touch-icon.png (180 px), icon-512.png.
webseite.py kopiert diese Dateien bei jedem Lauf nach webseite/. Nur neu laufen lassen, wenn sich das Icon ändern soll.

Braucht fontTools und Pillow sowie die Schrift Georgia kursiv (Windows: C:/Windows/Fonts/georgiai.ttf).
Die Buchstaben werden als Pfade gespeichert, das Icon hängt also nicht von installierten Schriften ab."""
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw

from pfade import SKRIPTE

SCHRIFT = "C:/Windows/Fonts/georgiai.ttf"
ZIEL = SKRIPTE / "favicon"
HINTERGRUND, VORDERGRUND = "#111111", "#ffffff"
GROESSE, RADIUS, BREITE = 48, 10, 30  # Kachel 48×48, Eckenradius, Breite der Buchstaben


def pfad_und_box():
    """SVG-Pfad von „s=“ in Schrifteinheiten (y nach oben) und dessen Begrenzungsrahmen."""
    font = TTFont(SCHRIFT)
    glyphen = font.getGlyphSet()
    cmap = font.getBestCmap()
    pen, box, x = SVGPathPen(glyphen), BoundsPen(glyphen), 0
    for zeichen in "s=":
        name = cmap[ord(zeichen)]
        glyphen[name].draw(TransformPen(pen, (1, 0, 0, 1, x, 0)))
        glyphen[name].draw(TransformPen(box, (1, 0, 0, 1, x, 0)))
        x += glyphen[name].width
    return pen.getCommands(), box.bounds


def svg():
    pfad, (x0, y0, x1, y1) = pfad_und_box()
    k = BREITE / (x1 - x0)
    tx = GROESSE / 2 - (x0 + x1) / 2 * k
    ty = GROESSE / 2 + (y0 + y1) / 2 * k  # y wird gespiegelt
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GROESSE} {GROESSE}">'
            f'<rect width="{GROESSE}" height="{GROESSE}" rx="{RADIUS}" fill="{HINTERGRUND}"/>'
            f'<path transform="translate({tx:.3f} {ty:.3f}) scale({k:.6f} {-k:.6f})" fill="{VORDERGRUND}" d="{pfad}"/>'
            f'</svg>\n')


def bild(px, rund=True):
    """Rastert das Icon über dieselben Pfade (4-fach überabgetastet, dann verkleinert)."""
    pfad, (x0, y0, x1, y1) = pfad_und_box()
    s = px * 4
    k = BREITE / (x1 - x0) * s / GROESSE
    tx, ty = s / 2 - (x0 + x1) / 2 * k, s / 2 + (y0 + y1) / 2 * k
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=RADIUS * s / GROESSE if rund else 0, fill=HINTERGRUND)
    # Konturen als Polygone; Gerade/Ungerade-Regel per XOR, damit Innenflächen (Löcher) frei bleiben
    font = TTFont(SCHRIFT)
    glyphen, cmap = font.getGlyphSet(), font.getBestCmap()
    maske, x = Image.new("1", (s, s), 0), 0
    for zeichen in "s=":
        g = glyphen[cmap[ord(zeichen)]]
        rec = RecordingPen()
        g.draw(TransformPen(rec, (k, 0, 0, -k, tx + x * k, ty)))
        x += g.width
        for kontur in konturen(rec.value):
            m = Image.new("1", (s, s), 0)
            ImageDraw.Draw(m).polygon(kontur, fill=1)
            maske = ImageChops.logical_xor(maske, m)
    d.bitmap((0, 0), maske.convert("L"), fill=VORDERGRUND)
    return img.resize((px, px), Image.LANCZOS)


def konturen(befehle, schritte=16):
    """RecordingPen-Befehle -> Liste von Punktlisten (quadratische/kubische Kurven angenähert)."""
    aus, akt, p = [], [], None
    for op, pts in befehle:
        if op == "moveTo":
            akt, p = [pts[0]], pts[0]
        elif op == "lineTo":
            akt.append(pts[0]); p = pts[0]
        elif op == "qCurveTo":
            # TrueType: mehrere Kontrollpunkte mit impliziten Mittelpunkten
            ctrl, ende = list(pts[:-1]), pts[-1]
            for i, c in enumerate(ctrl):
                ziel = ende if i == len(ctrl) - 1 else ((c[0] + ctrl[i + 1][0]) / 2, (c[1] + ctrl[i + 1][1]) / 2)
                for t in range(1, schritte + 1):
                    t /= schritte
                    akt.append(((1 - t) ** 2 * p[0] + 2 * (1 - t) * t * c[0] + t * t * ziel[0],
                                (1 - t) ** 2 * p[1] + 2 * (1 - t) * t * c[1] + t * t * ziel[1]))
                p = ziel
        elif op == "curveTo":
            c1, c2, ende = pts
            for t in range(1, schritte + 1):
                t /= schritte
                akt.append(tuple((1 - t) ** 3 * p[j] + 3 * (1 - t) ** 2 * t * c1[j] + 3 * (1 - t) * t * t * c2[j]
                                 + t ** 3 * ende[j] for j in (0, 1)))
            p = ende
        elif op in ("closePath", "endPath"):
            if len(akt) > 2:
                aus.append(akt)
            akt = []
    return aus


def main():
    ZIEL.mkdir(exist_ok=True)
    (ZIEL / "favicon.svg").write_text(svg(), encoding="utf-8")
    bild(48).save(ZIEL / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[bild(16), bild(32)])
    bild(180, rund=False).save(ZIEL / "apple-touch-icon.png")  # iOS rundet selbst ab
    bild(512).save(ZIEL / "icon-512.png")
    print("geschrieben:", ", ".join(p.name for p in sorted(ZIEL.iterdir())))


if __name__ == "__main__":
    main()

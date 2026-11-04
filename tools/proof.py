"""Render a small set of specimens from the built fonts."""

from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFont

from build import FAMILIES, FILES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "specimens"
NAME = FAMILIES["Stitched"].removesuffix(" Display")
LINEN = (239, 230, 211)
NIGHT = (43, 52, 62)
INK = (57, 52, 49)
CREAM = (248, 231, 203)
RED = (166, 62, 71)
GOLD = (237, 183, 124)


def font(style, size):
    return ImageFont.truetype(ROOT / "fonts" / f"{FILES[style]}.ttf", size)


def fitted_font(style, text, size, width):
    while font(style, size).getlength(text) > width:
        size -= 1
    return font(style, size)


def cloth(canvas, color):
    random = Random(2604)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width, canvas.height), fill=color)
    strength = 7 if sum(color) > 400 else 5
    for y in range(0, canvas.height, 6):
        for x in range(0, canvas.width, 6):
            x_offset = random.choice((-1, 0, 0, 1))
            y_offset = random.choice((-1, 0, 0, 1))
            vertical = random.randint(-strength, strength)
            horizontal = random.randint(-strength, strength)
            draw.line((x + x_offset, y, x + x_offset, y + 4),
                      fill=tuple(max(0, min(255, value + vertical)) for value in color), width=2)
            draw.line((x, y + y_offset + 3, x + 4, y + y_offset + 3),
                      fill=tuple(max(0, min(255, value + horizontal)) for value in color))


def centered(draw, y, text, face, color, width):
    x = round((width - draw.textlength(text, font=face)) / 2)
    draw.text((x, y), text, font=face, fill=color)


def wordmark():
    title = NAME.upper()
    face = fitted_font("Stitched", title, 245, 1270)
    canvas = Image.new("RGBA", (1400, 320), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    box = draw.textbbox((0, 0), title, font=face)
    x = round((canvas.width - (box[2] - box[0])) / 2 - box[0])
    y = round((canvas.height - (box[3] - box[1])) / 2 - box[1])
    draw.text((x, y), title, font=face, fill=(*RED, 255))
    canvas.save(OUTPUT / "wordmark.png", optimize=True)


def preview():
    canvas = Image.new("RGB", (1400, 840), LINEN)
    cloth(canvas, LINEN)
    draw = ImageDraw.Draw(canvas)
    title = NAME.upper()
    centered(draw, 65, title, fitted_font("Stitched", title, 225, 1230), RED, canvas.width)
    draw.line((100, 355, 1300, 355), fill=(202, 184, 161), width=2)
    centered(draw, 390, "PLAY   LEVELS   SETTINGS", font("StitchedUI", 62), INK, canvas.width)
    centered(draw, 510, "The First Stitch", font("StitchedUI", 65), INK, canvas.width)
    centered(draw, 635, "SHIFT  0123456789", font("StitchedUI", 55), INK, canvas.width)
    canvas.save(OUTPUT / "preview.png", optimize=True)


def phone(dark):
    background = NIGHT if dark else LINEN
    body = CREAM if dark else INK
    title = GOLD if dark else RED
    canvas = Image.new("RGB", (390, 844), background)
    cloth(canvas, background)
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 20), "390 x 844 px", font=font("StitchedUI", 14), fill=body)
    draw.line((24, 56, 366, 56), fill=body)
    draw.text((24, 74), "SHIFT", font=fitted_font("Stitched", "SHIFT", 68, 342), fill=title)
    draw.text((24, 173), "The First Stitch",
              font=fitted_font("StitchedUI", "The First Stitch", 32, 342), fill=body)
    for index, word in enumerate(("PLAY", "LEVELS", "SETTINGS")):
        top = 252 + index * 88
        draw.rounded_rectangle((22, top - 8, 368, top + 60), radius=10, outline=body, width=2)
        draw.text((42, top + 1), word, font=font("StitchedUI", 35), fill=body)
    draw.text((24, 534), "A small shift can", font=font("StitchedUI", 24), fill=body)
    draw.text((24, 569), "change a whole world.", font=font("StitchedUI", 24), fill=body)
    draw.line((24, 640, 366, 640), fill=body)
    draw.text((24, 662), "SHIFT  01 / 09", font=font("StitchedUI", 22), fill=body)
    draw.text((24, 714), "Il1  O0  Café  forêt", font=font("StitchedUI", 19), fill=body)
    draw.text((24, 755), "e é & @ : ; 6", font=font("StitchedUI", 23), fill=body)
    draw.text((305, 747), "@", font=font("Stitched", 35), fill=title)
    canvas.save(OUTPUT / f"phone-{'night' if dark else 'linen'}.png", optimize=True)


def glyphs(style):
    rows = (
        "ABCDEFGHIJKLM", "NOPQRSTUVWXYZ", "abcdefghijklm", "nopqrstuvwxyz",
        "0123456789!?&", "@&:;.,!?-+*/", "ÀÁÂÄÅÆÇÈÉÊËÌÍ",
        "àáâäåæçèéêëìí", "ÑÖØÙÜÝßœøłđþ€",
    )
    canvas = Image.new("RGB", (1600, 1210), LINEN)
    cloth(canvas, LINEN)
    draw = ImageDraw.Draw(canvas)
    draw.text((74, 25), f"{NAME.upper()} / {style.upper()}", font=font("StitchedUI", 29), fill=RED)
    for row_index, row in enumerate(rows):
        top = 100 + row_index * 121
        for column, char in enumerate(row):
            left = 68 + column * 112
            draw.rounded_rectangle((left, top, left + 100, top + 104), radius=8,
                                   outline=(202, 184, 161), width=2)
            draw.text((left + 16, top + 9), char, font=font(style, 68), fill=INK)
    canvas.save(OUTPUT / f"glyphs-{'display' if style == 'Stitched' else 'ui'}.png", optimize=True)


if __name__ == "__main__":
    OUTPUT.mkdir(exist_ok=True)
    wordmark()
    preview()
    phone(False)
    phone(True)
    glyphs("Stitched")
    glyphs("StitchedUI")

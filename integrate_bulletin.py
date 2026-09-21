import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
RADAR_PATH = ROOT / "radar_download" / "radar_images" / "latest_radar.png"
MAP_PATH = ROOT / "latest_warning_map.png"
IMD_HTML_PATH = ROOT / "imd_response.html"
OUTPUT_PATH = ROOT / "final_bulletin.png"

CANVAS_SIZE = (1600, 1100)
NAVY = (12, 47, 82)
BLUE = (32, 91, 145)
PALE_BLUE = (235, 243, 250)
INK = (24, 34, 45)
MUTED = (91, 105, 119)
WHITE = (255, 255, 255)


def load_font(size, bold=False):
    filename = "arialbd.ttf" if bold else "arial.ttf"
    font_path = Path(r"C:\Windows\Fonts") / filename
    try:
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default()


def read_bulletin_metadata():
    metadata = {}
    if IMD_HTML_PATH.exists():
        html = IMD_HTML_PATH.read_text(encoding="utf-8", errors="replace")
        patterns = {
            "date": r"Date \(DB\):\s*([^|<]+)",
            "toi": r"Time TOI \(DB\):\s*([^|<]+)",
            "valid": r"Valid Up To \(DB\):\s*([^|<]+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()

    now = datetime.now().astimezone()
    metadata.setdefault("date", now.strftime("%Y-%m-%d"))
    metadata.setdefault("toi", now.strftime("%H:%M:%S"))
    metadata.setdefault("valid", "Not supplied")
    return metadata


def draw_centered(draw, box, text, font, fill):
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), text, font=font)
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    draw.text(
        ((left + right - text_width) / 2, (top + bottom - text_height) / 2),
        text,
        font=font,
        fill=fill,
    )


def place_image(canvas, image, box):
    left, top, right, bottom = box
    inner_box = (left + 12, top + 12, right - 12, bottom - 12)
    contained = ImageOps.contain(image, (inner_box[2] - inner_box[0], inner_box[3] - inner_box[1]))
    position = (
        inner_box[0] + (inner_box[2] - inner_box[0] - contained.width) // 2,
        inner_box[1] + (inner_box[3] - inner_box[1] - contained.height) // 2,
    )
    canvas.alpha_composite(contained, position)


def main():
    print("Checking files...")

    if not RADAR_PATH.exists():
        raise FileNotFoundError(f"Radar image not found: {RADAR_PATH}")
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Warning map not found: {MAP_PATH}")

    radar = Image.open(RADAR_PATH).convert("RGBA")
    warning_map = Image.open(MAP_PATH).convert("RGBA")
    metadata = read_bulletin_metadata()

    canvas = Image.new("RGBA", CANVAS_SIZE, WHITE)
    draw = ImageDraw.Draw(canvas)

    header_height = 175
    draw.rectangle((0, 0, CANVAS_SIZE[0], header_height), fill=NAVY)
    draw.rectangle((0, header_height - 8, CANVAS_SIZE[0], header_height), fill=(226, 162, 44))

    draw_centered(draw, (40, 18, 1560, 62), "INDIA METEOROLOGICAL DEPARTMENT", load_font(30, True), WHITE)
    draw_centered(draw, (40, 62, 1560, 112), "NOWCAST BULLETIN", load_font(42, True), WHITE)
    draw_centered(draw, (40, 112, 1560, 154), "TELANGANA", load_font(27, True), (214, 231, 245))

    issue_line = (
        f"Date: {metadata['date']}    |    Time of Issue: {metadata['toi']}    |    "
        f"Valid Up To: {metadata['valid']}"
    )
    draw_centered(draw, (40, 900, 1560, 948), issue_line, load_font(23, True), NAVY)

    margin = 40
    gap = 30
    panel_top = 205
    panel_bottom = 875
    radar_box = (margin, panel_top, 940, panel_bottom)
    map_box = (margin + 940 + gap, panel_top, 1560, panel_bottom)

    for box in (radar_box, map_box):
        draw.rounded_rectangle(box, radius=8, fill=PALE_BLUE, outline=BLUE, width=3)

    draw.text((radar_box[0] + 18, radar_box[1] + 16), "HYDERABAD RADAR", font=load_font(26, True), fill=NAVY)
    draw.text((map_box[0] + 18, map_box[1] + 16), "TELANGANA DISTRICT WARNINGS", font=load_font(26, True), fill=NAVY)

    place_image(canvas, radar, (radar_box[0], radar_box[1] + 58, radar_box[2], radar_box[3]))
    place_image(canvas, warning_map, (map_box[0], map_box[1] + 58, map_box[2], map_box[3]))

    draw.line((margin, 980, 1560, 980), fill=(193, 204, 215), width=2)
    footer = "Source: India Meteorological Department | Telangana nowcast products"
    draw_centered(draw, (40, 990, 1560, 1032), footer, load_font(18), MUTED)
    draw_centered(draw, (40, 1035, 1560, 1075), "For official weather information, refer to the latest IMD bulletin.", load_font(16), MUTED)

    canvas.convert("RGB").save(OUTPUT_PATH, quality=95)

    print("Radar found:", radar.size)
    print("Warning map found:", warning_map.size)
    print("Bulletin generated successfully!")
    print("Saved: final_bulletin.png")
    print("Final size:", canvas.size)


if __name__ == "__main__":
    main()
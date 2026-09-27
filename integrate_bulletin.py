import textwrap
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from download_warning_map import atomic_replace


ROOT = Path(__file__).resolve().parent
RADAR_PATH = ROOT / "radar_download" / "radar_images" / "latest_radar.png"
MAP_PATH = ROOT / "latest_warning_map.png"
HEADER_PATH = ROOT / "assets" / "imd_header.jpg"
IMD_HTML_PATH = ROOT / "imd_response.html"
OUTPUT_PATH = ROOT / "final_bulletin.png"

CANVAS_SIZE = (1240, 1754)
WHITE = (255, 255, 255)
INK = (0, 0, 0)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)


def load_font(size, bold=False, telugu=False):
    windows = Path(r"C:\Windows\Fonts")
    names = []
    if telugu:
        names.append("nirmala.ttf")
        names.append("Nirmala.ttf")
    if bold:
        names.extend(["timesbd.ttf", "times.ttf", "arialbd.ttf"])
    else:
        names.extend(["times.ttf", "arial.ttf"])
    for name in names:
        path = windows / name
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def read_bulletin_metadata():
    metadata = {}
    if IMD_HTML_PATH.exists():
        html = IMD_HTML_PATH.read_text(encoding="utf-8", errors="replace")
        import re

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


def apply_bulletin_times(metadata, issued=None, valid=None):
    if issued is not None:
        metadata["date"] = issued.strftime("%Y-%m-%d")
        metadata["toi"] = issued.strftime("%H:%M:%S")
    if valid is not None:
        metadata["valid"] = valid.strftime("%H:%M:%S")
    return metadata


def contain_image(image, box):
    left, top, right, bottom = box
    max_w = max(1, right - left)
    max_h = max(1, bottom - top)
    copy = image.copy()
    copy.thumbnail((max_w, max_h))
    x = left + (max_w - copy.width) // 2
    y = top + (max_h - copy.height) // 2
    return copy, (x, y)


def draw_wrapped(draw, text, xy, font, fill, max_width, line_gap=6):
    if not text:
        return xy[1]
    x, y = xy
    lines = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width=92) or [""])
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        box = draw.textbbox((x, y), line, font=font)
        y = box[3] + line_gap
    return y


def main(issued=None, valid=None, warning_sections=None, no_warnings_text=None):
    print("Checking files...")

    if not RADAR_PATH.exists():
        raise FileNotFoundError(f"Radar image not found: {RADAR_PATH}")
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Warning map not found: {MAP_PATH}")

    radar = Image.open(RADAR_PATH).convert("RGBA")
    warning_map = Image.open(MAP_PATH).convert("RGBA")
    metadata = apply_bulletin_times(read_bulletin_metadata(), issued, valid)
    warning_sections = warning_sections or {}
    no_warnings_text = (no_warnings_text or "").strip()

    canvas = Image.new("RGB", CANVAS_SIZE, WHITE)
    draw = ImageDraw.Draw(canvas)
    margin = 48
    y = 28

    if HEADER_PATH.is_file():
        header = Image.open(HEADER_PATH).convert("RGB")
        header.thumbnail((CANVAS_SIZE[0] - 2 * margin, 150))
        x = (CANVAS_SIZE[0] - header.width) // 2
        canvas.paste(header, (x, y))
        y += header.height + 16

    title_font = load_font(28, bold=True)
    title = "District level Nowcast of Telangana"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(
        ((CANVAS_SIZE[0] - (title_box[2] - title_box[0])) // 2, y),
        title,
        font=title_font,
        fill=INK,
    )
    y += (title_box[3] - title_box[1]) + 10
    draw.line((margin, y, CANVAS_SIZE[0] - margin, y), fill=INK, width=2)
    y += 16

    body_bold = load_font(18, bold=True)
    issue = f"TIME OF ISSUE: {metadata['date']} ({metadata['toi']} Hrs IST)"
    valid_line = f"Valid upto: ({metadata['valid']} Hrs IST)"
    draw.text((margin, y), issue, font=body_bold, fill=INK)
    valid_box = draw.textbbox((0, 0), valid_line, font=body_bold)
    draw.text(
        (CANVAS_SIZE[0] - margin - (valid_box[2] - valid_box[0]), y),
        valid_line,
        font=body_bold,
        fill=INK,
    )
    y += 36

    body = load_font(16)
    telugu = load_font(16, telugu=True)
    heading_fills = {"orange": ORANGE, "yellow": YELLOW, "red": (255, 0, 0)}
    headings = {
        "orange": "Orange Warning(Be Prepared)",
        "yellow": "Yellow Warning(Be Updated)",
        "red": "Red Warning(Take Action)",
    }
    rendered = False
    for key in ("orange", "yellow", "red"):
        section = warning_sections.get(key) or {}
        english = (section.get("english") or "").strip()
        te = (section.get("telugu") or "").strip()
        if key == "red" and not english and not te:
            continue
        heading = headings[key]
        hb = draw.textbbox((margin, y), heading, font=body_bold)
        draw.rectangle((hb[0] - 2, hb[1] - 1, hb[2] + 2, hb[3] + 1), fill=heading_fills[key])
        draw.text((margin, y), heading, font=body_bold, fill=INK)
        y = hb[3] + 8
        if english:
            y = draw_wrapped(draw, english, (margin, y), body, INK, CANVAS_SIZE[0] - 2 * margin)
        if te:
            y = draw_wrapped(draw, te, (margin, y), telugu, INK, CANVAS_SIZE[0] - 2 * margin)
        if not english and not te and no_warnings_text:
            y = draw_wrapped(draw, no_warnings_text, (margin, y), telugu, INK, CANVAS_SIZE[0] - 2 * margin)
        y += 10
        rendered = True
    if not rendered and no_warnings_text:
        y = draw_wrapped(draw, no_warnings_text, (margin, y), telugu, INK, CANVAS_SIZE[0] - 2 * margin)
        y += 10

    y += 8
    panel_bottom = CANVAS_SIZE[1] - 40
    mid = CANVAS_SIZE[0] // 2
    radar_img, radar_pos = contain_image(radar, (margin, y, mid - 12, panel_bottom))
    map_img, map_pos = contain_image(warning_map, (mid + 12, y, CANVAS_SIZE[0] - margin, panel_bottom))
    canvas.paste(radar_img, radar_pos, radar_img)
    canvas.paste(map_img, map_pos, map_img)

    tmp_png = OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".tmp.png")
    canvas.save(tmp_png, quality=95)
    saved_png = atomic_replace(tmp_png, OUTPUT_PATH)
    print("Radar found:", radar.size)
    print("Warning map found:", warning_map.size)
    print(f"Integrated image saved: {saved_png.name}")
    print("Final size:", canvas.size)
    return saved_png


if __name__ == "__main__":
    main()

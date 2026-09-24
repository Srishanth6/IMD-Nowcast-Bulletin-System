"""
IMD Nowcast Bulletin — Page 1 integration.

Combines Person 1 radar and Person 2 warning-map outputs into a Word
bulletin that follows the official Telangana nowcast Page 1 structure.
Warning text is parsed from the live IMD server, not from hard-coded lists.
"""

from __future__ import annotations

import html as html_lib
import io
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image

from download_warning_map import URL as IMD_NOWCAST_URL, extract_svg


ROOT = Path(__file__).resolve().parent

RADAR_PATH = ROOT / "radar_download" / "radar_images" / "latest_radar.png"
WARNING_MAP_PATH = ROOT / "latest_warning_map.png"
WARNING_SVG_PATH = ROOT / "latest_warning_map.svg"
HEADER_PATH = ROOT / "assets" / "imd_header.jpg"
PAGE2_IMPACTS_PATH = ROOT / "assets" / "expected_impacts_moderate.jpg"
PAGE3_IMPACTS_PATH = ROOT / "assets" / "expected_impacts_heavy_rain.jpg"
PAGE4_IMPACTS_PATH = ROOT / "assets" / "expected_impacts_very_severe.jpg"
OUTPUT_PATH = ROOT / "IMD_Nowcast_Bulletin.docx"

try:
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))
NOWCAST_VALIDITY = timedelta(hours=3)

ORANGE_FILL = "FFA500"
YELLOW_FILL = "FFFF00"
NAVY = RGBColor(0x0C, 0x2F, 0x52)
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

LEVELS = (
    ("red", "Red Warning(Take Action)", "FF0000"),
    ("orange", "Orange Warning(Be Prepared)", ORANGE_FILL),
    ("yellow", "Yellow Warning(Be Updated)", YELLOW_FILL),
)

ALWAYS_SHOW_LEVELS = {"orange", "yellow"}


class BulletinInputError(FileNotFoundError):
    """Raised when a required bulletin input image is missing."""


def datetimes_from_imd(page_fields: dict):
    """Use the issue time published on the latest IMD page, not the local clock."""
    date_db = page_fields.get("date_db")
    toi = page_fields.get("time_toi_db")
    valid_text = page_fields.get("valid_upto_db")
    if not date_db or not toi:
        raise BulletinInputError(
            "The latest IMD page did not include Date (DB) and Time TOI (DB)."
        )
    issued = datetime.strptime(f"{date_db} {toi}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    if valid_text:
        valid = datetime.strptime(f"{date_db} {valid_text}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        if valid <= issued:
            valid += timedelta(days=1)
    else:
        valid = issued + NOWCAST_VALIDITY
    return issued, valid


def _has_telugu(text: str) -> bool:
    return bool(re.search(r"[\u0C00-\u0C7F]", text))


def parse_nowcast_page(page_html: str) -> dict:
    """Extract fields that exist on dist_nowcast.php (map page)."""
    prefix = page_html.split("<!DOCTYPE", 1)[0]
    fields = {
        "date_db": None,
        "time_toi_db": None,
        "valid_upto_db": None,
        "official_bulletin_href": None,
        "map_fill_counts": Counter(),
    }
    date_match = re.search(r"Date \(DB\):\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", prefix)
    toi_match = re.search(r"Time TOI \(DB\):\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2})", prefix)
    valid_match = re.search(r"Valid Up To \(DB\):\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2})", prefix)
    if date_match:
        fields["date_db"] = date_match.group(1)
    if toi_match:
        fields["time_toi_db"] = toi_match.group(1)
    if valid_match:
        fields["valid_upto_db"] = valid_match.group(1)

    href_match = re.search(
        r"<a\s+href=['\"]([^'\"]+)['\"][^>]*>\s*Download Nowcast Bulletin",
        page_html,
        flags=re.I,
    )
    if href_match:
        fields["official_bulletin_href"] = href_match.group(1)

    svg = extract_svg(page_html)
    fills = re.findall(
        r"<path[^>]*fill=['\"](green|yellow|orange|red)['\"]",
        svg,
        flags=re.I,
    )
    fields["map_fill_counts"] = Counter(color.lower() for color in fills)
    return fields


def parse_official_bulletin_docx(docx_bytes: bytes) -> dict:
    """Extract Orange/Yellow/Red English and Telugu text from IMD's Word bulletin."""
    sections = {}
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    runs = []
    for node in root.iter(f"{W_NS}t"):
        if node.text:
            runs.append(html_lib.unescape(node.text).strip())

    heading_keys = {
        "orange warning": "orange",
        "yellow warning": "yellow",
        "red warning": "red",
    }
    index = 0
    while index < len(runs):
        compact = re.sub(r"\s+", "", runs[index]).lower()
        matched_key = None
        for prefix, key in heading_keys.items():
            if compact.startswith(prefix.replace(" ", "")):
                matched_key = key
                break
        if matched_key is None:
            index += 1
            continue
        english = ""
        telugu = ""
        if index + 1 < len(runs):
            english = runs[index + 1]
        if index + 2 < len(runs) and _has_telugu(runs[index + 2]):
            telugu = runs[index + 2]
            index += 3
        else:
            index += 2
        sections[matched_key] = {"english": english, "telugu": telugu}
    return sections


def fetch_nowcast_page() -> str:
    page = requests.get(
        IMD_NOWCAST_URL,
        params={"_": str(int(datetime.now(IST).timestamp()))},
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        timeout=30,
    )
    page.raise_for_status()
    html_path = ROOT / "imd_response.html"
    html_path.write_text(page.text, encoding="utf-8")
    return page.text


def load_imd_warning_content(page_html: str) -> dict:
    page_fields = parse_nowcast_page(page_html)

    print("Fields available on dist_nowcast.php:")
    print(f"  Date (DB): {page_fields['date_db']}")
    print(f"  Time TOI (DB): {page_fields['time_toi_db']}")
    print(f"  Valid Up To (DB): {page_fields['valid_upto_db']}")
    print(f"  Map polygon fills: {dict(page_fields['map_fill_counts'])}")
    print(f"  Official bulletin link: {page_fields['official_bulletin_href']}")
    print("  English/Telugu warning sentences: not present on this page")
    print("  District name attributes: not present in the SVG")

    warning_sections = {}
    href = page_fields["official_bulletin_href"]
    if href:
        bulletin_url = urljoin(IMD_NOWCAST_URL, href)
        print("Fetching official IMD warning text from:")
        print(f"  {bulletin_url}")
        bulletin = requests.get(bulletin_url, timeout=60)
        bulletin.raise_for_status()
        warning_sections = parse_official_bulletin_docx(bulletin.content)
        print("Fields available in the official IMD Word bulletin:")
        for key in ("orange", "yellow", "red"):
            section = warning_sections.get(key)
            if section:
                print(f"  {key} English: {section['english'][:90]}...")
                print(f"  {key} Telugu: present" if section["telugu"] else f"  {key} Telugu: absent")
            else:
                print(f"  {key}: not present")

    return {
        "page_fields": page_fields,
        "warning_sections": warning_sections,
    }


def format_issue_line(issued: datetime) -> str:
    return f"TIME OF ISSUE: {issued.strftime('%Y-%m-%d')} ({issued.strftime('%H:%M:%S')} Hrs IST)"


def format_valid_line(valid: datetime) -> str:
    return f"Valid upto: ({valid.strftime('%H:%M:%S')} Hrs IST)"


def set_run_font(run, name="Times New Roman", size=11, bold=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    r_fonts = rpr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        rpr.append(r_fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        r_fonts.set(qn(attr), name)
    if color is not None:
        run.font.color.rgb = color


def shade_run(run, fill: str):
    rpr = run._element.get_or_add_rPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:fill"), fill)
    rpr.append(shading)


def set_cell_width(cell, width_emu: int):
    cell.width = width_emu


def disable_table_borders(table):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "auto")
        borders.append(element)
    tbl_pr.append(borders)


def add_bottom_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "000000")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def add_paragraph(document, text="", *, align="left", space_after=4, space_before=0):
    paragraph = document.add_paragraph()
    alignment = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
    }[align]
    paragraph.alignment = alignment
    paragraph.paragraph_format.space_before = Pt(space_before)
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = 1.08
    if text:
        run = paragraph.add_run(text)
        set_run_font(run)
    return paragraph


def picture_size(path: Path, max_width_in: float, max_height_in: float):
    with Image.open(path) as image:
        width_px, height_px = image.size
    aspect = width_px / height_px
    width = max_width_in
    height = width / aspect
    if height > max_height_in:
        height = max_height_in
        width = height * aspect
    return Inches(width), Inches(height)


def require_input(path: Path, label: str):
    if not path.is_file():
        raise BulletinInputError(
            f"{label} not found:\n  {path.relative_to(ROOT).as_posix()}\n"
            "Generate this file with the existing module before creating the bulletin."
        )
    print(f"Loaded {label}: {path.relative_to(ROOT).as_posix()}")
    return path


def add_page_break(document):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.add_run().add_break(WD_BREAK.PAGE)


def add_impact_page(document, image_path: Path, label: str):
    if not image_path.is_file():
        print(f"WARNING: {label} reference page not found: {image_path.relative_to(ROOT).as_posix()}")
        return
    paragraph = add_paragraph(document, align="center", space_before=6, space_after=6)
    width, height = picture_size(image_path, 7.1, 9.4)
    paragraph.add_run().add_picture(str(image_path), width=width, height=height)
    print(f"Loaded {label}: {image_path.relative_to(ROOT).as_posix()}")


def add_warning_block(document, title: str, fill: str, english: str, telugu: str = ""):
    heading = add_paragraph(document, space_after=2, space_before=4)
    run = heading.add_run(title)
    set_run_font(run, size=12, bold=True)
    shade_run(run, fill)

    if english:
        english_para = add_paragraph(document, space_after=2)
        english_run = english_para.add_run(english)
        set_run_font(english_run, size=11)

    if telugu:
        telugu_para = add_paragraph(document, space_after=6)
        telugu_run = telugu_para.add_run(telugu)
        set_run_font(telugu_run, name="Nirmala UI", size=11)


def build_document(radar_path: Path, map_path: Path, warning_data: dict, issued: datetime, valid: datetime):
    print(format_issue_line(issued))
    print(format_valid_line(valid))

    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.27)
    section.bottom_margin = Cm(1.27)
    section.left_margin = Cm(1.27)
    section.right_margin = Cm(1.27)

    header = add_paragraph(document, align="center", space_after=0)
    if HEADER_PATH.is_file():
        header_width, header_height = picture_size(HEADER_PATH, 7.1, 1.35)
        header.add_run().add_picture(
            str(HEADER_PATH),
            width=header_width,
            height=header_height,
        )
        print(f"Loaded IMD header: {HEADER_PATH.relative_to(ROOT).as_posix()}")
    else:
        run = header.add_run(
            "India Meteorological Department  |  Meteorological Centre, Hyderabad"
        )
        set_run_font(run, size=12, bold=True, color=NAVY)

    title = add_paragraph(document, align="center", space_before=4, space_after=6)
    title_run = title.add_run("District level Nowcast of Telangana")
    set_run_font(title_run, size=16, bold=True)
    add_bottom_border(title)

    usable_width = section.page_width - section.left_margin - section.right_margin
    half = usable_width // 2
    time_table = document.add_table(rows=1, cols=2)
    time_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    disable_table_borders(time_table)
    left_cell, right_cell = time_table.rows[0].cells
    set_cell_width(left_cell, int(half))
    set_cell_width(right_cell, int(half))

    left_cell.text = ""
    left_para = left_cell.paragraphs[0]
    left_run = left_para.add_run(format_issue_line(issued))
    set_run_font(left_run, size=11, bold=True)

    right_cell.text = ""
    right_para = right_cell.paragraphs[0]
    right_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_run = right_para.add_run(format_valid_line(valid))
    set_run_font(right_run, size=11, bold=True)

    add_paragraph(document, space_after=2)

    warning_sections = warning_data.get("warning_sections") or {}
    fill_counts = warning_data.get("page_fields", {}).get("map_fill_counts") or Counter()
    for key, title_text, fill in LEVELS:
        section = warning_sections.get(key) or {}
        english = (section.get("english") or "").strip()
        telugu = (section.get("telugu") or "").strip()
        has_map_color = fill_counts.get(key, 0) > 0
        if not english and not telugu and not has_map_color and key not in ALWAYS_SHOW_LEVELS:
            continue
        add_warning_block(document, title_text, fill, english, telugu)
        if english:
            print(f"{title_text}: {english}")
        elif has_map_color:
            print(
                f"{title_text}: map has {fill_counts[key]} {key} polygon(s); "
                "no English/Telugu sentence was present in the IMD text source."
            )
        else:
            print(f"{title_text}: no IMD warning text for this colour")

    image_table = document.add_table(rows=1, cols=2)
    image_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    disable_table_borders(image_table)
    radar_cell, map_cell = image_table.rows[0].cells
    set_cell_width(radar_cell, int(half))
    set_cell_width(map_cell, int(half))
    radar_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    map_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

    radar_cell.text = ""
    radar_para = radar_cell.paragraphs[0]
    radar_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    radar_w, radar_h = picture_size(radar_path, 3.35, 2.85)
    radar_para.add_run().add_picture(str(radar_path), width=radar_w, height=radar_h)

    map_cell.text = ""
    map_para = map_cell.paragraphs[0]
    map_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    map_w, map_h = picture_size(map_path, 3.35, 3.35)
    map_para.add_run().add_picture(str(map_path), width=map_w, height=map_h)

    add_page_break(document)
    add_impact_page(
        document,
        PAGE2_IMPACTS_PATH,
        "Page 2 Expected Impacts (Moderate Thunderstorm/Lightning)",
    )
    add_page_break(document)
    add_impact_page(
        document,
        PAGE3_IMPACTS_PATH,
        "Page 3 Expected Impacts (Heavy Rain)",
    )
    add_page_break(document)
    add_impact_page(
        document,
        PAGE4_IMPACTS_PATH,
        "Page 4 Expected Impacts (Very Severe Thunderstorm/Squall)",
    )

    duty = add_paragraph(document, align="right", space_before=18, space_after=0)
    duty_run = duty.add_run("డ్యూటీ అధికారి / ड्यूटी अधिकारी / Duty Officer")
    set_run_font(duty_run, name="Nirmala UI", size=12)

    return document


def main():
    print("=" * 60)
    print(" IMD NOWCAST BULLETIN")
    print("=" * 60)
    os.chdir(ROOT)
    print("Fetching latest IMD data...")

    try:
        page_html = fetch_nowcast_page()
    except Exception as error:
        print(f"ERROR: could not fetch the latest IMD nowcast page: {error}")
        return 1

    try:
        from radar_download.radar_scraper import download_latest_radar

        print("Downloading latest radar image...")
        radar_file = download_latest_radar()
    except Exception as error:
        print(f"ERROR: could not download the latest radar image: {error}")
        return 1
    if not radar_file or not Path(radar_file).is_file():
        print("ERROR: the latest radar image was not downloaded.")
        return 1
    radar_path = Path(radar_file)
    print(f"Latest radar saved: {radar_path.as_posix()}")

    try:
        from download_warning_map import save_warning_map

        print("Downloading latest warning map...")
        map_path = save_warning_map(page_html)
    except Exception as error:
        print(f"ERROR: could not download the latest warning map: {error}")
        return 1
    print(f"Latest warning map saved: {Path(map_path).as_posix()}")

    try:
        warning_data = load_imd_warning_content(page_html)
        issued, valid = datetimes_from_imd(warning_data["page_fields"])
    except Exception as error:
        print(f"ERROR: could not extract the IMD issue time: {error}")
        return 1

    print(
        "Issue time extracted: "
        f"{issued.strftime('%Y-%m-%d')} ({issued.strftime('%H:%M:%S')} Hrs IST)"
    )
    print("Generating final bulletin...")

    try:
        document = build_document(radar_path, map_path, warning_data, issued, valid)
        document.save(OUTPUT_PATH)
    except Exception as error:
        print(f"ERROR: could not generate the bulletin: {error}")
        return 1

    print("Bulletin generated successfully!")
    print(f"Saved: {OUTPUT_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

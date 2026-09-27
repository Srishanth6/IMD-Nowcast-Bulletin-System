"""
IMD Nowcast Bulletin.

Combines Person 1 radar and Person 2 warning-map outputs into a Word
bulletin that follows the official Telangana nowcast sample format.
Times come from the live IMD nowcast page, not hard-coded values.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import io
import json
import os
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

from download_warning_map import URL as IMD_NOWCAST_URL, extract_svg
from download_warning_map import atomic_replace
from integrate_bulletin import OUTPUT_PATH as COMPOSITE_PATH
from integrate_bulletin import main as build_composite_image


ROOT = Path(__file__).resolve().parent

RADAR_PATH = ROOT / "radar_download" / "radar_images" / "latest_radar.png"
WARNING_MAP_PATH = ROOT / "latest_warning_map.png"
WARNING_SVG_PATH = ROOT / "latest_warning_map.svg"
HEADER_PATH = ROOT / "assets" / "imd_header.jpg"
PAGE2_IMPACTS_PATH = ROOT / "assets" / "expected_impacts_moderate.jpg"
PAGE3_IMPACTS_PATH = ROOT / "assets" / "expected_impacts_heavy_rain.jpg"
PAGE4_IMPACTS_PATH = ROOT / "assets" / "expected_impacts_very_severe.jpg"
OUTPUT_PATH = ROOT / "IMD_Nowcast_Bulletin.docx"
SERVED_BULLETIN_NAME = "telangana_nowcast.docx"
DOWNLOAD_PHP_PATH = ROOT / "dist_nowcast3.php"
DEFAULT_WX_DIR = Path("/var/www/html/tlng/wx")
DOWNLOAD_BULLETIN_URL = urljoin(IMD_NOWCAST_URL, "dist_nowcast3.php")
HTML_BULLETIN_URL = urljoin(IMD_NOWCAST_URL, "dist_nowcast4.php")
CYCLE_STATE_PATH = ROOT / ".imd_nowcast_cycle_state.json"

IST = timezone(timedelta(hours=5, minutes=30))
NOWCAST_VALIDITY = timedelta(hours=3)

ORANGE_FILL = "FFA500"
YELLOW_FILL = "FFFF00"
NAVY = RGBColor(0x0C, 0x2F, 0x52)
BLUE = RGBColor(0x20, 0x5B, 0x91)
INK = RGBColor(0x24, 0x34, 0x45)
GOLD = RGBColor(0xE2, 0xA2, 0x2C)
PALE_FILL = "EBF3FA"
BORDER_BLUE = "205B91"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

LEVELS = (
    ("red", "Red Warning(Take Action)", "FF0000"),
    ("orange", "Orange Warning(Be Prepared)", ORANGE_FILL),
    ("yellow", "Yellow Warning(Be Updated)", YELLOW_FILL),
)

ALWAYS_SHOW_LEVELS = {"orange", "yellow"}


class BulletinInputError(FileNotFoundError):
    """Raised when a required bulletin input image is missing."""


def load_cycle_state() -> dict:
    if not CYCLE_STATE_PATH.exists():
        return {}
    try:
        return json.loads(CYCLE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cycle_state(state: dict) -> dict:
    CYCLE_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return state


SKIP_RESTORE = object()


def backup_current_outputs() -> dict[Path, bytes | object | None]:
    backup: dict[Path, bytes | object | None] = {}
    for target in (OUTPUT_PATH, COMPOSITE_PATH):
        if not target.exists():
            backup[target] = None
            continue
        try:
            backup[target] = target.read_bytes()
        except OSError:
            print(f"WARNING: {target.name} is locked; leaving the existing file unchanged")
            backup[target] = SKIP_RESTORE
    return backup


def restore_output_backups(backup: dict[Path, bytes | object | None]) -> None:
    for target, payload in backup.items():
        if payload is SKIP_RESTORE:
            continue
        tmp_path = target.with_name(target.name + ".restore.tmp")
        try:
            if payload is None:
                if target.exists():
                    target.unlink()
                continue
            tmp_path.write_bytes(payload)
            os.replace(os.fspath(tmp_path.resolve()), os.fspath(target.resolve()))
        except OSError:
            print(f"WARNING: could not restore locked file: {target.name}")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


def radar_file_metadata(path: Path) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=IST).strftime("%Y-%m-%d %H:%M:%S IST")
        return {"hash": digest, "timestamp": timestamp}
    except Exception:
        return None


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


def _is_structural_bulletin_run(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower()
    return compact.startswith(
        (
            "orangewarning",
            "yellowwarning",
            "redwarning",
            "timeofissue",
            "validupto",
            "districtlevelnowcast",
            "nowarnings",
        )
    ) or "duty officer" in text.lower() or "డ్యూటీ" in text


def _warning_heading_key(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text).lower()
    if compact.startswith("orangewarning"):
        return "orange"
    if compact.startswith("yellowwarning"):
        return "yellow"
    if compact.startswith("redwarning"):
        return "red"
    return None


def _split_no_warnings(text: str | None) -> tuple[str, str]:
    text = html_lib.unescape((text or "").strip())
    if not text:
        return "", ""
    parts = [part.strip() for part in re.split(r"\s*/\s*", text) if part.strip()]
    english = ""
    telugu = ""
    for part in parts:
        if _has_telugu(part) and not english:
            telugu = part if not telugu else telugu
        elif _has_telugu(part):
            telugu = part
        else:
            english = part
    if _has_telugu(text) and not telugu:
        telugu = text
    if re.search(r"[A-Za-z]", text) and not english:
        english = parts[0] if parts else text
    return english, telugu


def _paragraphs_from_docx(docx_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs = []
    for para in root.iter(f"{W_NS}p"):
        text = "".join(node.text or "" for node in para.iter(f"{W_NS}t"))
        text = html_lib.unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _sections_from_blocks(blocks: list[str]) -> dict:
    sections = {}
    no_warnings_text = None
    no_warnings_english = ""
    no_warnings_telugu = ""
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if re.search(r"no\s*warnings", block, flags=re.I) or "హెచ్చరికలు లేవు" in block:
            if _has_telugu(block) and not re.search(r"[A-Za-z]", block):
                no_warnings_telugu = block
            elif re.search(r"no\s*warnings", block, flags=re.I) and not _has_telugu(block):
                no_warnings_english = block
            else:
                no_warnings_text = block
                english, telugu = _split_no_warnings(block)
                no_warnings_english = no_warnings_english or english
                no_warnings_telugu = no_warnings_telugu or telugu
            index += 1
            continue
        matched_key = _warning_heading_key(block)
        if matched_key is None:
            index += 1
            continue
        english = ""
        telugu = ""
        next_index = index + 1
        while next_index < len(blocks) and not _is_structural_bulletin_run(blocks[next_index]) and _warning_heading_key(blocks[next_index]) is None:
            candidate = blocks[next_index]
            if _has_telugu(candidate) and not re.search(r"[A-Za-z]", candidate):
                telugu = f"{telugu} {candidate}".strip() if telugu else candidate
            elif english:
                if _has_telugu(candidate):
                    telugu = f"{telugu} {candidate}".strip() if telugu else candidate
                else:
                    english = f"{english} {candidate}".strip()
            else:
                english = candidate
            next_index += 1
            if english and telugu:
                break
        sections[matched_key] = {"english": english, "telugu": telugu}
        index = next_index
    if not no_warnings_text and (no_warnings_english or no_warnings_telugu):
        no_warnings_text = " / ".join(part for part in (no_warnings_english, no_warnings_telugu) if part)
    return {
        "sections": sections,
        "no_warnings_text": no_warnings_text,
        "no_warnings_english": no_warnings_english,
        "no_warnings_telugu": no_warnings_telugu,
    }


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
    """Extract warning body text from IMD's Word bulletin, without inventing districts."""
    return _sections_from_blocks(_paragraphs_from_docx(docx_bytes))


def parse_official_bulletin_html(html: str) -> dict:
    """Extract warning body text from IMD's HTML Word bulletin (dist_nowcast4.php)."""
    cleaned = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<img\b[^>]*>", " ", cleaned, flags=re.I)
    blocks = []
    for match in re.finditer(
        r"<(h[1-6]|p|td|div|li)(?:\s[^>]*)?>(.*?)</\1>",
        cleaned,
        flags=re.I | re.S,
    ):
        text = re.sub(r"<[^>]+>", " ", match.group(2))
        text = html_lib.unescape(re.sub(r"\s+", " ", text)).strip()
        if text and text not in blocks:
            blocks.append(text)
    return _sections_from_blocks(blocks)


def _merge_section(primary: dict | None, secondary: dict | None) -> dict:
    primary = primary or {}
    secondary = secondary or {}
    return {
        "english": (primary.get("english") or secondary.get("english") or "").strip(),
        "telugu": (primary.get("telugu") or secondary.get("telugu") or "").strip(),
    }


def merge_warning_parses(*parsed: dict) -> dict:
    sections = {}
    no_warnings_text = None
    no_warnings_english = ""
    no_warnings_telugu = ""
    for item in parsed:
        if not item:
            continue
        for key, section in (item.get("sections") or {}).items():
            sections[key] = _merge_section(sections.get(key), section)
        no_warnings_text = no_warnings_text or item.get("no_warnings_text")
        no_warnings_english = no_warnings_english or (item.get("no_warnings_english") or "")
        no_warnings_telugu = no_warnings_telugu or (item.get("no_warnings_telugu") or "")
    if no_warnings_text and not (no_warnings_english or no_warnings_telugu):
        no_warnings_english, no_warnings_telugu = _split_no_warnings(no_warnings_text)
    if not no_warnings_text and (no_warnings_english or no_warnings_telugu):
        no_warnings_text = " / ".join(part for part in (no_warnings_english, no_warnings_telugu) if part)
    return {
        "sections": sections,
        "no_warnings_text": no_warnings_text,
        "no_warnings_english": no_warnings_english,
        "no_warnings_telugu": no_warnings_telugu,
    }


def resolve_warning_sections(warning_data: dict) -> dict:
    """Fill Orange/Yellow slots from live IMD text; never invent districts."""
    sections = dict(warning_data.get("warning_sections") or {})
    notice_en = (warning_data.get("no_warnings_english") or "").strip()
    notice_te = (warning_data.get("no_warnings_telugu") or "").strip()
    if not notice_en and not notice_te:
        notice_en, notice_te = _split_no_warnings(warning_data.get("no_warnings_text"))
    resolved = {}
    for key, _title, _fill in LEVELS:
        section = _merge_section(sections.get(key), None)
        has_level_text = bool(section["english"] or section["telugu"])
        if not has_level_text and key in ALWAYS_SHOW_LEVELS and (notice_en or notice_te):
            section = {"english": notice_en, "telugu": notice_te}
        if section["english"] or section["telugu"] or key in ALWAYS_SHOW_LEVELS:
            resolved[key] = section
    return resolved


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

    parsed_sources = []
    href = page_fields["official_bulletin_href"] or "dist_nowcast3.php"
    bulletin_url = urljoin(IMD_NOWCAST_URL, href)
    print("Fetching official IMD warning text from:")
    print(f"  {bulletin_url}")
    try:
        bulletin = requests.get(bulletin_url, timeout=60)
        bulletin.raise_for_status()
        parsed_docx = parse_official_bulletin_docx(bulletin.content)
        parsed_sources.append(parsed_docx)
        print("Fields available in the official IMD Word bulletin:")
        if parsed_docx.get("no_warnings_text"):
            print(f"  Official notice: {parsed_docx['no_warnings_text']}")
        for key in ("orange", "yellow", "red"):
            section = (parsed_docx.get("sections") or {}).get(key)
            if section and (section.get("english") or section.get("telugu")):
                english = section.get("english") or ""
                print(f"  {key} English: {english[:90]}..." if english else f"  {key} English: absent")
                print(f"  {key} Telugu: present" if section.get("telugu") else f"  {key} Telugu: absent")
            else:
                print(f"  {key}: not present")
    except Exception as error:
        print(f"WARNING: could not parse dist_nowcast3.php: {error}")

    print("Fetching IMD HTML nowcast bulletin from:")
    print(f"  {HTML_BULLETIN_URL}")
    try:
        html_bulletin = requests.get(HTML_BULLETIN_URL, timeout=60)
        html_bulletin.raise_for_status()
        html_text = html_bulletin.content.decode("utf-8", errors="replace")
        parsed_html = parse_official_bulletin_html(html_text)
        parsed_sources.append(parsed_html)
        print("Fields available in dist_nowcast4.php:")
        if parsed_html.get("no_warnings_text"):
            print(f"  Official notice: {parsed_html['no_warnings_text']}")
        for key in ("orange", "yellow", "red"):
            section = (parsed_html.get("sections") or {}).get(key)
            if section and (section.get("english") or section.get("telugu")):
                english = section.get("english") or ""
                print(f"  {key} English: {english[:90]}..." if english else f"  {key} English: absent")
                print(f"  {key} Telugu: present" if section.get("telugu") else f"  {key} Telugu: absent")
            else:
                print(f"  {key}: not present")
    except Exception as error:
        print(f"WARNING: could not parse dist_nowcast4.php: {error}")

    merged = merge_warning_parses(*parsed_sources)
    return {
        "page_fields": page_fields,
        "warning_sections": merged.get("sections") or {},
        "no_warnings_text": merged.get("no_warnings_text"),
        "no_warnings_english": merged.get("no_warnings_english") or "",
        "no_warnings_telugu": merged.get("no_warnings_telugu") or "",
    }


def _section_text(section: dict | None) -> str:
    if not section:
        return "none"
    english = (section.get("english") or "").strip()
    telugu = (section.get("telugu") or "").strip()
    if english and telugu:
        return f"{english} | {telugu}"
    return english or telugu or "none"


def print_imd_warning_data(warning_data: dict) -> None:
    resolved = resolve_warning_sections(warning_data)
    fills = warning_data.get("page_fields", {}).get("map_fill_counts") or {}
    notice = warning_data.get("no_warnings_text") or "none"
    print("=== IMD WARNING DATA ===")
    print(f"Orange Warning: {_section_text(resolved.get('orange'))}")
    print(f"Yellow Warning: {_section_text(resolved.get('yellow'))}")
    print(
        "District Warning Data: "
        f"official notice={notice}; map fills={dict(fills)}"
    )
    print("========================")


def format_issue_line(issued: datetime) -> str:
    return f"TIME OF ISSUE: {issued.strftime('%Y-%m-%d')} ({issued.strftime('%H:%M:%S')} Hrs IST)"


def format_valid_line(valid: datetime) -> str:
    return f"Valid upto: ({valid.strftime('%H:%M:%S')} Hrs IST)"


def format_bottom_timestamp(issued: datetime, valid: datetime) -> str:
    return (
        f"Date: {issued.strftime('%Y-%m-%d')}  |  "
        f"Time of Issue: {issued.strftime('%H:%M:%S')}  |  "
        f"Valid Up To: {valid.strftime('%H:%M:%S')}"
    )


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


def set_cell_width(cell, width):
    cell.width = width


def shade_run(run, fill: str):
    rpr = run._element.get_or_add_rPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:fill"), fill)
    rpr.append(shading)


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
    width, height = picture_size(image_path, 6.25, 9.4)
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
    require_input(radar_path, "Hyderabad radar image")
    require_input(map_path, "Telangana warning map")

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
        header_width, header_height = picture_size(HEADER_PATH, 6.25, 1.36)
        header.add_run().add_picture(
            str(HEADER_PATH),
            width=header_width,
            height=header_height,
        )
        print(f"Loaded IMD header: {HEADER_PATH.relative_to(ROOT).as_posix()}")
    else:
        run = header.add_run(
            "Government of India (Ministry of Earth Sciences)  |  "
            "India Meteorological Department  |  Meteorological Centre, Hyderabad"
        )
        set_run_font(run, size=12, bold=True)

    title = add_paragraph(document, align="center", space_before=4, space_after=4)
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

    warning_sections = resolve_warning_sections(warning_data)
    no_warnings_text = (warning_data.get("no_warnings_text") or "").strip()
    rendered_warning_text = False
    for key, title_text, fill in LEVELS:
        section_data = warning_sections.get(key) or {}
        english = (section_data.get("english") or "").strip()
        telugu = (section_data.get("telugu") or "").strip()
        if key not in ALWAYS_SHOW_LEVELS and not english and not telugu:
            continue
        add_warning_block(document, title_text, fill, english, telugu)
        rendered_warning_text = bool(english or telugu) or rendered_warning_text
        print(f"{title_text}: {english or telugu or '(heading only)'}")
    if not rendered_warning_text:
        print("Official IMD bulletin did not include Orange/Yellow/Red warning sentences.")

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
    radar_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    radar_w, radar_h = picture_size(radar_path, 3.47, 2.84)
    radar_para.add_run().add_picture(str(radar_path), width=radar_w, height=radar_h)

    map_cell.text = ""
    map_para = map_cell.paragraphs[0]
    map_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    map_w, map_h = picture_size(map_path, 3.47, 4.01)
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

    print("Building verification image final_bulletin.png...")
    png_saved = None
    try:
        png_saved = build_composite_image(
            issued=issued,
            valid=valid,
            warning_sections=warning_sections,
            no_warnings_text=no_warnings_text,
        )
    except Exception as error:
        print(f"WARNING: could not write final_bulletin.png: {error}")
    return document, png_saved


def nowcast_wx_directories() -> list[Path]:
    """Directories that Apache/PHP can use for Download Nowcast Bulletin."""
    directories: list[Path] = []
    seen: set[Path] = set()
    env_dir = os.environ.get("IMD_WX_DIR", "").strip()
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(DEFAULT_WX_DIR)
    candidates.append(ROOT)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        directories.append(candidate)
    return directories


def _copy_if_needed(source: Path, destination: Path) -> Path | None:
    if not source.is_file():
        return None
    if destination.exists() and destination.resolve() == source.resolve():
        return destination
    try:
        shutil.copy2(source, destination)
    except OSError:
        return None
    return destination


def publish_generated_bulletin(docx_path: Path) -> list[Path]:
    """Copy the generated bulletin (and download PHP) into the IMD wx folder."""
    published: list[Path] = []
    seen: set[Path] = set()
    for directory in nowcast_wx_directories():
        if not directory.is_dir() or not os.access(directory, os.W_OK):
            continue
        for name in (OUTPUT_PATH.name, SERVED_BULLETIN_NAME):
            copied = _copy_if_needed(docx_path, directory / name)
            if copied is not None:
                key = copied.resolve()
                if key not in seen:
                    seen.add(key)
                    published.append(copied)
        php_copy = _copy_if_needed(DOWNLOAD_PHP_PATH, directory / DOWNLOAD_PHP_PATH.name)
        if php_copy is not None:
            key = php_copy.resolve()
            if key not in seen:
                seen.add(key)
                published.append(php_copy)
    return published


def live_download_matches(docx_path: Path) -> bool:
    """True when the IP Download Nowcast Bulletin link returns this generated file."""
    try:
        response = requests.get(
            DOWNLOAD_BULLETIN_URL,
            timeout=60,
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        )
        response.raise_for_status()
    except Exception as error:
        print(f"WARNING: could not check Download Nowcast Bulletin: {error}")
        return False
    return response.content == docx_path.read_bytes()


def require_readable_image(path: Path, label: str) -> Path:
    try:
        with Image.open(path) as image:
            image.load()
    except Exception as error:
        raise BulletinInputError(f"{label} is unreadable: {path} ({error})") from error
    return path


def run_bulletin_cycle():
    started_at = datetime.now(IST)
    print(f"[{started_at.strftime('%H:%M')} IST] Starting bulletin cycle")

    backup = backup_current_outputs()
    previous_state = load_cycle_state()
    previous_radar_hash = previous_state.get("radar_hash")
    previous_radar_time = previous_state.get("radar_timestamp")
    previous_issue = previous_state.get("issue_time")

    try:
        print(f"[{datetime.now(IST).strftime('%H:%M')} IST] Fetching latest IMD data")
        page_html = fetch_nowcast_page()

        try:
            from radar_download.radar_scraper import download_latest_radar

            print(f"[{datetime.now(IST).strftime('%H:%M')} IST] Downloading latest radar image")
            radar_file = download_latest_radar()
        except Exception as error:
            raise RuntimeError(f"could not download the latest radar image: {error}") from error

        if not radar_file or not Path(radar_file).is_file():
            raise RuntimeError("the latest radar image was not downloaded")
        radar_path = Path(radar_file)
        try:
            require_readable_image(radar_path, "Hyderabad radar image")
        except BulletinInputError as error:
            print(f"WARNING: {error}. Continuing with the downloaded file.")
        radar_meta = radar_file_metadata(radar_path)
        if radar_meta:
            print(f"Latest radar timestamp: {radar_meta['timestamp']}")
            if previous_radar_hash and previous_radar_hash == radar_meta["hash"]:
                print(f"Previous radar timestamp: {previous_radar_time or 'n/a'}")
                print("Radar source has not published a newer image yet; using the latest available file.")
        print(f"Latest radar saved: {radar_path.as_posix()}")

        try:
            from download_warning_map import save_warning_map

            print(f"[{datetime.now(IST).strftime('%H:%M')} IST] Downloading latest warning map")
            map_path = save_warning_map(page_html)
        except Exception as error:
            raise RuntimeError(f"could not download the latest warning map: {error}") from error
        print(f"Latest warning map saved: {Path(map_path).as_posix()}")

        try:
            warning_data = load_imd_warning_content(page_html)
            issued, valid = datetimes_from_imd(warning_data["page_fields"])
        except Exception as error:
            raise RuntimeError(f"could not extract the IMD issue time: {error}") from error

        if previous_issue and previous_issue == issued.strftime("%Y-%m-%d %H:%M:%S"):
            print(f"Previous issue time: {previous_issue}")
            print(f"Latest issue time: {issued.strftime('%Y-%m-%d %H:%M:%S')} IST")
            print("IMD source time is unchanged; regenerating the bulletin with the latest available data.")

        print(
            "Issue time extracted: "
            f"{issued.strftime('%Y-%m-%d')} ({issued.strftime('%H:%M:%S')} Hrs IST)"
        )
        print(f"[{datetime.now(IST).strftime('%H:%M')} IST] Generating bulletin")
        print_imd_warning_data(warning_data)

        document, png_saved = build_document(radar_path, map_path, warning_data, issued, valid)
        temp_output = OUTPUT_PATH.with_name(OUTPUT_PATH.stem + ".tmp.docx")
        document.save(str(temp_output))
        try:
            saved_path = atomic_replace(temp_output, OUTPUT_PATH)
        except OSError as error:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except OSError:
                    pass
            raise RuntimeError(f"could not save the bulletin DOCX: {error}") from error
        if temp_output.exists():
            try:
                temp_output.unlink()
            except OSError:
                pass

        docx_replaced = saved_path.resolve() == OUTPUT_PATH.resolve()
        png_replaced = bool(png_saved) and Path(png_saved).resolve() == COMPOSITE_PATH.resolve()
        if not docx_replaced:
            print(
                f"WARNING: {OUTPUT_PATH.name} is open/locked. "
                f"Latest bulletin saved as {saved_path.name}. "
                "Close Word and rerun to replace the main bulletin file."
            )
        if png_saved and not png_replaced:
            print(
                f"WARNING: {COMPOSITE_PATH.name} is open/locked. "
                f"Latest PNG saved as {Path(png_saved).name}."
            )
        if not png_saved:
            print(f"WARNING: {COMPOSITE_PATH.name} was not written.")

        published = publish_generated_bulletin(saved_path)
        complete = docx_replaced and png_replaced
        save_cycle_state(
            {
                "status": "success" if complete else "locked",
                "issue_time": issued.strftime("%Y-%m-%d %H:%M:%S"),
                "valid_time": valid.strftime("%Y-%m-%d %H:%M:%S"),
                "radar_hash": radar_meta["hash"] if radar_meta else None,
                "radar_timestamp": radar_meta["timestamp"] if radar_meta else None,
                "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "published": [str(path) for path in published],
                "docx": str(saved_path),
                "png": str(png_saved) if png_saved else None,
            }
        )

        if complete:
            print(f"[{datetime.now(IST).strftime('%H:%M')} IST] Bulletin generated successfully")
        else:
            print(
                f"[{datetime.now(IST).strftime('%H:%M')} IST] Bulletin cycle finished, "
                "but a required output file was locked and was not replaced."
            )
        print(f"Saved: {saved_path.name}")
        if published:
            print("Published for Download Nowcast Bulletin:")
            for path in published:
                print(f"  {path.as_posix()}")
            print(f"Download URL: {DOWNLOAD_BULLETIN_URL}")
            if live_download_matches(OUTPUT_PATH):
                print("Download Nowcast Bulletin is serving this generated bulletin.")
            else:
                print(
                    "WARNING: the IP download link is still serving the previous "
                    "server-generated bulletin. Run this script on the IMD Apache "
                    "host (or set IMD_WX_DIR to /var/www/html/tlng/wx) so "
                    "dist_nowcast3.php and IMD_Nowcast_Bulletin.docx land in that folder."
                )
        else:
            print(
                "WARNING: could not copy the bulletin into the IMD wx folder. "
                "Set IMD_WX_DIR to /var/www/html/tlng/wx on the Apache server."
            )
        return {
            "status": "success" if complete else "locked",
            "issued": issued,
            "valid": valid,
            "radar": radar_meta,
            "docx": saved_path,
            "png": png_saved,
        }

    except Exception as error:
        restore_output_backups(backup)
        print(f"[{datetime.now(IST).strftime('%H:%M')} IST] Bulletin cycle failed: {error}")
        return {"status": "failed", "error": str(error)}


def main():
    print("=" * 60)
    print(" IMD NOWCAST BULLETIN")
    print("=" * 60)
    os.chdir(ROOT)
    result = run_bulletin_cycle()
    if result["status"] == "success":
        return 0
    if result["status"] == "stale":
        print("No new bulletin generated because the latest IMD/radar data is unchanged.")
        return 0
    if result["status"] == "locked":
        print("A required output file was locked. Close it and run generate_bulletin.py again.")
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())

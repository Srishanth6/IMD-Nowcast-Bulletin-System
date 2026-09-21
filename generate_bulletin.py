from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from integrate_bulletin import IMD_HTML_PATH, read_bulletin_metadata


ROOT = Path(__file__).resolve().parent
IMAGE_PATH = ROOT / "integrated_bulletin.png"
OUTPUT_PATH = ROOT / "IMD_Nowcast_Bulletin.docx"

NAVY = "0C2F52"
BLUE = "205B91"
LIGHT_BLUE = "EBF3FA"
GOLD = "E2A22C"
DARK_GRAY = "243445"


def set_cell_shading(cell, fill):
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_border(cell, color=BLUE, size="8"):
    properties = cell._tc.get_or_add_tcPr()
    borders = properties.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        properties.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top=100, start=140, bottom=100, end=140):
    properties = cell._tc.get_or_add_tcPr()
    margins = properties.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        properties.append(margins)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        element = margins.find(qn("w:" + side))
        if element is None:
            element = OxmlElement("w:" + side)
            margins.append(element)
        element.set(qn("w:w"), str(value))
        element.set(qn("w:type"), "dxa")


def set_cell_text(cell, text, color=DARK_GRAY, bold=False, size=10.5):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_header(document):
    section = document.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run("INDIA METEOROLOGICAL DEPARTMENT")
    run.font.name = "Arial"
    run.font.size = Pt(10)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)


def add_title(document):
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(2)
    run = paragraph.add_run("NOWCAST BULLETIN")
    run.font.name = "Arial"
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(NAVY)

    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(12)
    run = paragraph.add_run("TELANGANA")
    run.font.name = "Arial"
    run.font.size = Pt(15)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(BLUE)


def add_metadata_table(document, metadata):
    table = document.add_table(rows=1, cols=3)
    table.autofit = False
    table.columns[0].width = Inches(2.25)
    table.columns[1].width = Inches(2.25)
    table.columns[2].width = Inches(2.25)
    labels = (
        ("BULLETIN DATE", metadata["date"]),
        ("TIME OF ISSUE", metadata["toi"]),
        ("VALID UP TO", metadata["valid"]),
    )
    for cell, (label, value) in zip(table.rows[0].cells, labels):
        set_cell_shading(cell, LIGHT_BLUE)
        set_cell_border(cell)
        set_cell_margins(cell)
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(2)
        label_run = paragraph.add_run(label + "\n")
        label_run.font.name = "Arial"
        label_run.font.size = Pt(8.5)
        label_run.font.bold = True
        label_run.font.color.rgb = RGBColor.from_string(BLUE)
        value_run = paragraph.add_run(value)
        value_run.font.name = "Arial"
        value_run.font.size = Pt(11)
        value_run.font.bold = True
        value_run.font.color.rgb = RGBColor.from_string(DARK_GRAY)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def main():
    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(
            f"Integrated bulletin image not found: {IMAGE_PATH}\n"
            "Run the image integration script first."
        )
    if not IMD_HTML_PATH.is_file():
        raise FileNotFoundError(
            f"IMD metadata file not found: {IMD_HTML_PATH}\n"
            "Run the IMD page download step first."
        )

    metadata = read_bulletin_metadata()
    if any(not metadata.get(key) for key in ("date", "toi", "valid")):
        raise ValueError(
            "Required IMD bulletin metadata is missing from imd_response.html "
            "(date, issue time, or valid-up-to time)."
        )

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.55)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)
    section.header_distance = Inches(0.25)
    section.footer_distance = Inches(0.25)

    styles = document.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(10)

    add_header(document)
    add_title(document)
    add_metadata_table(document, metadata)

    image_paragraph = document.add_paragraph()
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.paragraph_format.space_before = Pt(4)
    image_paragraph.paragraph_format.space_after = Pt(10)
    image_paragraph.add_run().add_picture(str(IMAGE_PATH), width=Inches(7.1))

    separator = document.add_paragraph()
    separator.alignment = WD_ALIGN_PARAGRAPH.CENTER
    separator.paragraph_format.space_after = Pt(5)
    run = separator.add_run("________________________________________________________________")
    run.font.name = "Arial"
    run.font.size = Pt(7)
    run.font.color.rgb = RGBColor.from_string(GOLD)

    footer_paragraph = document.add_paragraph()
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_paragraph.paragraph_format.space_after = Pt(0)
    run = footer_paragraph.add_run(
        "Source: India Meteorological Department | Telangana nowcast products"
    )
    run.font.name = "Arial"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor.from_string(DARK_GRAY)

    document.save(OUTPUT_PATH)
    print("Bulletin document generated successfully!")
    print("Saved: IMD_Nowcast_Bulletin.docx")
    print("Output path:", OUTPUT_PATH)


if __name__ == "__main__":
    main()

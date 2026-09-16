from pathlib import Path
from datetime import date
import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Inches, Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"
REPORT_DIR = ROOT / "report"
FIG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today().strftime("%d %B %Y")
BLUE = "#1F4E79"
LIGHT_BLUE = "#DCE6F1"
MID_BLUE = "#9FBAD0"
GREY = "#666666"
LIGHT_GREY = "#F2F4F7"
BORDER = "#B7C1CC"


def rounded_box(ax, xy, width, height, label, fill=LIGHT_BLUE, edge=BLUE,
                fontsize=10, weight="normal"):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        linewidth=1.2, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, label, ha="center", va="center",
            fontsize=fontsize, weight=weight, color="#1B1B1B", wrap=True)


def arrow(ax, start, end, color=BLUE, style="-|>"):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style,
                                 mutation_scale=13, linewidth=1.3,
                                 color=color, connectionstyle="arc3,rad=0"))


def make_pipeline():
    path = FIG_DIR / "figure_1_research_pipeline.png"
    fig, ax = plt.subplots(figsize=(11, 4.8), dpi=220)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.8)
    ax.axis("off")
    ax.text(0.2, 4.45, "Research and data pipeline", fontsize=16, weight="bold",
            color=BLUE, ha="left")
    stages = [
        (0.25, 2.55, 1.7, 0.95, "Public feeds\nand policies"),
        (2.25, 2.55, 1.7, 0.95, "Raw snapshots\nand hashes"),
        (4.25, 2.55, 1.7, 0.95, "Normalize\nindicators"),
        (6.25, 2.55, 1.7, 0.95, "Classify\nDanish scope"),
        (8.25, 2.55, 2.2, 0.95, "Enrich and\ncompare"),
    ]
    for x, y, w, h, t in stages:
        rounded_box(ax, (x, y), w, h, t)
    for i in range(len(stages) - 1):
        x, y, w, h, _ = stages[i]
        nx, ny, nw, nh, _ = stages[i + 1]
        arrow(ax, (x + w + 0.06, y + h / 2), (nx - 0.06, ny + nh / 2))
    rounded_box(ax, (1.15, 0.65), 2.4, 0.9, "Quantitative analysis", fill="#EAF2F8")
    rounded_box(ax, (4.3, 0.65), 2.4, 0.9, "Policy and delisting\nanalysis", fill="#EAF2F8")
    rounded_box(ax, (7.45, 0.65), 2.5, 0.9, "Findings, discussion\nand conclusion", fill="#EAF2F8")
    arrow(ax, (9.35, 2.5), (8.75, 1.62))
    arrow(ax, (5.55, 1.55), (5.55, 1.62))
    arrow(ax, (2.35, 1.55), (2.35, 1.62))
    ax.text(5.5, 0.18, "All transformations remain traceable to a timestamped raw snapshot.",
            ha="center", fontsize=9, color=GREY)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def make_lifecycle():
    path = FIG_DIR / "figure_2_blocklist_lifecycle.png"
    fig, ax = plt.subplots(figsize=(11, 4.3), dpi=220)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4.3)
    ax.axis("off")
    ax.text(0.2, 3.95, "Blocklist entry lifecycle", fontsize=16, weight="bold", color=BLUE)
    boxes = [
        (0.25, 2.3, 1.45, 0.8, "Activity\nobserved"),
        (2.05, 2.3, 1.45, 0.8, "Evidence\ncollected"),
        (3.85, 2.3, 1.45, 0.8, "Indicator\nlisted"),
        (5.65, 2.3, 1.45, 0.8, "Feed or DNSBL\ndistribution"),
        (7.45, 2.3, 1.45, 0.8, "Local filter\ndecision"),
        (9.25, 2.3, 1.45, 0.8, "Expiry or\ndelisting"),
    ]
    for x, y, w, h, t in boxes:
        rounded_box(ax, (x, y), w, h, t, fontsize=9)
    for i in range(len(boxes) - 1):
        x, y, w, h, _ = boxes[i]
        nx, ny, nw, nh, _ = boxes[i + 1]
        arrow(ax, (x + w + 0.05, y + h / 2), (nx - 0.05, ny + nh / 2))
    arrow(ax, (10.0, 2.25), (0.95, 1.5), color="#9C2F2F")
    ax.text(5.5, 1.57, "new reports, refreshed evidence, or changed ownership can restart the cycle",
            ha="center", va="center", fontsize=9, color="#9C2F2F")
    ax.text(5.5, 0.62,
            "The study observes the public states and documented procedures. It does not generate malicious traffic.",
            ha="center", fontsize=9, color=GREY)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def make_data_model():
    path = FIG_DIR / "figure_3_data_model.png"
    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=220)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    ax.text(0.2, 4.85, "Minimum reproducible data model", fontsize=16, weight="bold", color=BLUE)
    entities = [
        (0.35, 2.9, 2.0, 1.0, "Source\nname, URL, policy"),
        (3.0, 2.9, 2.0, 1.0, "Snapshot\nUTC time, hash"),
        (5.65, 2.9, 2.0, 1.0, "Indicator\nIP, CIDR, domain"),
        (8.3, 2.9, 2.25, 1.0, "Observation\nlisted, added, removed"),
        (3.0, 0.9, 2.0, 1.0, "Location\nDK evidence and source"),
        (5.65, 0.9, 2.0, 1.0, "Enrichment\nASN, DNS, reputation"),
    ]
    for x, y, w, h, t in entities:
        rounded_box(ax, (x, y), w, h, t, fill="#F6F8FA", edge=BLUE, fontsize=9)
    for a, b in [
        ((2.35, 3.4), (2.95, 3.4)),
        ((5.0, 3.4), (5.6, 3.4)),
        ((7.65, 3.4), (8.25, 3.4)),
        ((4.0, 2.85), (4.0, 1.95)),
        ((6.65, 2.85), (6.65, 1.95)),
    ]:
        arrow(ax, a, b)
    ax.text(2.63, 3.62, "contains", fontsize=8, color=GREY, ha="center")
    ax.text(5.3, 3.62, "normalizes", fontsize=8, color=GREY, ha="center")
    ax.text(7.95, 3.62, "creates", fontsize=8, color=GREY, ha="center")
    ax.text(4.2, 2.35, "classified by", fontsize=8, color=GREY, rotation=90, va="center")
    ax.text(6.85, 2.35, "enriched with", fontsize=8, color=GREY, rotation=90, va="center")
    ax.text(5.5, 0.25,
            "Keep raw observations separate from interpretation so later corrections do not erase the evidence trail.",
            ha="center", fontsize=9, color=GREY)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def make_timeline():
    path = FIG_DIR / "figure_4_collection_timeline.png"
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=220)
    ax.set_xlim(0, 31)
    ax.set_ylim(0, 4.5)
    ax.axis("off")
    ax.text(0.3, 4.1, "Thirty-day collection plan", fontsize=16, weight="bold", color=BLUE)
    ax.plot([1, 30], [2.5, 2.5], color=BLUE, linewidth=2)
    for d in [1, 7, 14, 21, 30]:
        ax.plot([d, d], [2.25, 2.75], color=BLUE, linewidth=1.4)
        ax.text(d, 1.95, f"Day {d}", ha="center", fontsize=9)
    ax.scatter([1, 7, 14, 21, 30], [2.5] * 5, color=BLUE, s=38, zorder=3)
    labels = [
        (1, 3.15, "Baseline\nand parser test"),
        (7, 3.15, "Quality check\nand schema review"),
        (14, 3.15, "Midpoint\nanalysis"),
        (21, 3.15, "Policy review\ncompletion"),
        (30, 3.15, "Freeze data\nand final analysis"),
    ]
    for x, y, t in labels:
        ax.text(x, y, t, ha="center", va="bottom", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="#EAF2F8", edgecolor=MID_BLUE))
    ax.text(15.5, 0.78,
            "Daily snapshots: download -> timestamp -> hash -> normalize -> log status",
            ha="center", fontsize=9, color=GREY)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill.replace("#", ""))


def set_cell_border(cell, color=BORDER, size="6"):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color.replace("#", ""))


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn("w:" + m))
        if node is None:
            node = OxmlElement("w:" + m)
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def style_table(table, header=True, compact=False):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for r_idx, row in enumerate(table.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_border(cell)
            set_cell_margins(cell, top=80 if compact else 110, bottom=80 if compact else 110)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.05
                for run in p.runs:
                    run.font.name = "Liberation Serif"
                    run._element.rPr.rFonts.set(qn("w:ascii"), "Liberation Serif")
                    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Liberation Serif")
                    run.font.size = Pt(9.3 if compact else 9.8)
        if header and r_idx == 0:
            set_repeat_table_header(row)
            for cell in row.cells:
                set_cell_shading(cell, BLUE)
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
        elif r_idx % 2 == 0:
            for cell in row.cells:
                set_cell_shading(cell, "F6F8FA")


def add_page_field(paragraph):
    run = paragraph.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)


def add_bookmark(paragraph, name, bookmark_id):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bookmark_id))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bookmark_id))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def add_internal_hyperlink(paragraph, text, anchor, color=BLUE, underline=True, bold=False):
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("w:anchor"), anchor)
    hyperlink.set(qn("w:history"), "1")
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    if color:
        c = OxmlElement("w:color")
        c.set(qn("w:val"), color.replace("#", ""))
        r_pr.append(c)
    if underline:
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        r_pr.append(u)
    if bold:
        b = OxmlElement("w:b")
        r_pr.append(b)
    new_run.append(r_pr)
    text_node = OxmlElement("w:t")
    text_node.text = text
    new_run.append(text_node)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_external_hyperlink(paragraph, text, url, color=BLUE):
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), add_relationship(paragraph.part, url))
    new_run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color.replace("#", ""))
    r_pr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    r_pr.append(u)
    new_run.append(r_pr)
    text_node = OxmlElement("w:t")
    text_node.text = text
    new_run.append(text_node)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_relationship(part, url):
    return part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)


def add_toc_entry(doc, title, level, anchor):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5 * (level - 1))
    p.paragraph_format.first_line_indent = Cm(-0.5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    add_internal_hyperlink(p, title, anchor, bold=(level == 1))
    return p


def add_text(doc, text, style="Normal", bold_lead=None):
    p = doc.add_paragraph(style=style)
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        r.bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def add_bullets(doc, items, level=0):
    for item in items:
        p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
        p.add_run(item)


def add_numbered(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Number")
        p.add_run(item)


def add_table(doc, headers, rows, widths=None, compact=False):
    table = doc.add_table(rows=1, cols=len(headers))
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
    if widths:
        for row in table.rows:
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    style_table(table, compact=compact)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_caption(doc, label, text):
    p = doc.add_paragraph(style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{label}. {text}")
    r.italic = True
    r.font.size = Pt(9.5)
    return p


def add_figure(doc, path, label, caption, width=6.35):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = add_caption(doc, label, caption)
    return cap


class ReportBuilder:
    def __init__(self):
        self.doc = Document()
        self.headings = []
        self.bookmark_counter = 100
        self.figures = []
        self.tables = []
        self._configure()

    def _configure(self):
        sec = self.doc.sections[0]
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        sec.top_margin = Cm(2.2)
        sec.bottom_margin = Cm(2.0)
        sec.left_margin = Cm(2.2)
        sec.right_margin = Cm(2.0)
        sec.header_distance = Cm(0.8)
        sec.footer_distance = Cm(1.0)
        styles = self.doc.styles
        normal = styles["Normal"]
        normal.font.name = "Liberation Serif"
        normal._element.rPr.rFonts.set(qn("w:ascii"), "Liberation Serif")
        normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Liberation Serif")
        normal.font.size = Pt(11.2)
        normal.font.color.rgb = RGBColor(0, 0, 0)
        normal.paragraph_format.line_spacing = 1.2
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for name, size, space_before, space_after in [
            ("Heading 1", 15, 18, 8),
            ("Heading 2", 12.5, 12, 5),
            ("Heading 3", 11.2, 8, 3),
        ]:
            st = styles[name]
            st.font.name = "Liberation Serif"
            st._element.rPr.rFonts.set(qn("w:ascii"), "Liberation Serif")
            st._element.rPr.rFonts.set(qn("w:hAnsi"), "Liberation Serif")
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = RGBColor(0, 0, 0)
            st.paragraph_format.space_before = Pt(space_before)
            st.paragraph_format.space_after = Pt(space_after)
            st.paragraph_format.keep_with_next = True
            st.paragraph_format.page_break_before = name == "Heading 1"
        if "Caption" in styles:
            styles["Caption"].font.name = "Liberation Serif"
            styles["Caption"].font.size = Pt(9.5)
            styles["Caption"].font.italic = True
            styles["Caption"].font.color.rgb = RGBColor(70, 70, 70)
        for style_name in ("List Bullet", "List Bullet 2", "List Number"):
            st = styles[style_name]
            st.font.name = "Liberation Serif"
            st._element.rPr.rFonts.set(qn("w:ascii"), "Liberation Serif")
            st._element.rPr.rFonts.set(qn("w:hAnsi"), "Liberation Serif")
            st.font.size = Pt(11.0)
            st.paragraph_format.line_spacing = 1.15
            st.paragraph_format.space_after = Pt(3)
        footer = sec.footer
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("Analysis of Public Blocklists from a Danish Perspective  |  ")
        r.font.name = "Liberation Serif"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(90, 90, 90)
        add_page_field(p)
        for run in p.runs:
            run.font.name = "Liberation Serif"
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(90, 90, 90)

    def heading(self, title, level=1, bookmark=None):
        p = self.doc.add_paragraph(style=f"Heading {level}")
        p.add_run(title)
        if bookmark is None:
            key = "h" + str(level) + "_" + "_".join(ch.lower() if ch.isalnum() else "_" for ch in title).strip("_")
        else:
            key = bookmark
        add_bookmark(p, key, self.bookmark_counter)
        self.bookmark_counter += 1
        self.headings.append((title, level, key))
        return key

    def paragraph(self, text, **kwargs):
        return add_text(self.doc, text, **kwargs)

    def table(self, headers, rows, **kwargs):
        t = add_table(self.doc, headers, rows, **kwargs)
        self.tables.append((headers, rows))
        return t

    def figure(self, path, label, caption, width=6.35):
        self.figures.append((label, caption))
        return add_figure(self.doc, path, label, caption, width)

    def page_break(self):
        self.doc.add_page_break()

    def save(self, path):
        self.doc.save(path)


def add_cover(builder):
    doc = builder.doc
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(75)
    r = p.add_run("Analysis of Public Blocklists from a Danish Perspective")
    r.bold = True
    r.font.name = "Liberation Serif"
    r._element.rPr.rFonts.set(qn("w:ascii"), "Liberation Serif")
    r._element.rPr.rFonts.set(qn("w:hAnsi"), "Liberation Serif")
    r.font.size = Pt(24)
    r.font.color.rgb = RGBColor(31, 78, 121)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(18)
    r = p2.add_run("Empirical Study of Listing Dynamics Transparency and Delisting Procedures")
    r.font.name = "Liberation Serif"
    r.font.size = Pt(14)
    r.italic = True
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_before = Pt(55)
    p3.add_run("Semester project in Distributed Systems Security\n").bold = True
    p3.add_run("MSc in Engineering Cyber Security\n")
    p3.add_run("Aalborg University Copenhagen\n")
    p3.add_run(f"Submission period: Autumn 2026\n")
    p3.add_run(f"Prepared by: Member 1 | Member 2 | Member 3 | Member 4 | Member 5 | Member 6\n")
    p3.add_run("Supervisor: To be confirmed with the semester coordinator")
    for run in p3.runs:
        run.font.name = "Liberation Serif"
        run.font.size = Pt(12)
    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p4.paragraph_format.space_before = Pt(100)
    r = p4.add_run("Project report framework and data collection plan")
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(90, 90, 90)
    doc.add_page_break()


def add_summary_and_preface(builder):
    builder.heading("Summary", 1, "summary")
    builder.paragraph(
        "Public blocklists are used by network operators, mail systems, firewalls and security tools to identify IP addresses, networks and domains associated with unwanted or malicious activity. Their practical value depends not only on whether an indicator is listed, but also on the quality of the evidence, the clarity of the list policy, the speed of updates and the possibility of correcting an inaccurate listing. This project examines those issues from a Danish perspective."
    )
    builder.paragraph(
        "The study will collect timestamped snapshots of selected public feeds for at least thirty consecutive days. The dataset will be normalized and filtered for Danish-related IP addresses and domains using documented country and allocation evidence. The analysis will compare list size, update activity, persistence, overlap and metadata completeness. A separate policy analysis will examine how the selected operators describe listing, expiry, false positives and removal. Any practical test of a removal process will be limited to assets owned by the group and will be conducted only when the operator explicitly allows it."
    )
    builder.paragraph(
        "The expected contribution is a reproducible comparison of how different public blocklists represent and maintain indicators that may affect Danish networks. The project will distinguish between observation and interpretation: a listing will be reported as a public data state, while claims about maliciousness, false positives or operational impact will require supporting evidence. The final conclusion will be written after the collection period and will answer the research questions using the measured results."
    )
    builder.heading("Preface", 1, "preface")
    builder.paragraph(
        "This report has been prepared as a group project by six students. The group is responsible for the problem formulation, data collection, analysis, source selection and final conclusions. Individual work packages are used to coordinate the work, but the report must be read and discussed collectively before submission so that the methods and arguments are consistent."
    )
    builder.paragraph(
        "The project follows the problem-based learning orientation of Aalborg University. The practical problem is the use of public blocklists in network defence; the academic task is to investigate that problem systematically, document the choices made and connect the findings to scientific literature."
    )
    builder.paragraph(
        "Generative AI use declaration: the group must complete this statement before submission in accordance with the current AAU rules. If generative AI has been used for planning, language improvement or coding support, state what was used, for which tasks, and how the group verified the content. The group must not present unverified generated text, data or references as original research."
    )
    builder.paragraph(
        "Page and format note: the current AAU general project guidance states that project reports use A4, at least 1.2 line spacing, at least 11-point font and margins of at least 2 cm. It also states that the normal maximum for a first- or second-semester master's project is 80 normal pages, calculated from the first report page through the conclusion, unless the relevant study board or module description provides a different rule. The group must confirm the exact local requirement with the semester coordinator before submission."
    )
    builder.page_break()
    builder.heading("Table of Contents", 1, "toc")
    builder.paragraph("Select a linked entry to jump directly to the corresponding section.")
    toc_placeholder = builder.doc.add_paragraph("[[TOC]]")
    toc_placeholder.paragraph_format.space_after = Pt(12)
    builder.page_break()
    builder.heading("List of Figures", 1, "list_of_figures")
    builder.paragraph("The figure list is linked to the figure captions in the report.")
    fig_placeholder = builder.doc.add_paragraph("[[FIGURES]]")
    builder.page_break()
    builder.heading("List of Tables", 1, "list_of_tables")
    builder.paragraph("The table list is linked to the tables in the report.")
    tbl_placeholder = builder.doc.add_paragraph("[[TABLES]]")
    builder.page_break()
    builder.heading("List of Abbreviations", 1, "abbreviations")
    builder.table(
        ["Abbreviation", "Meaning"],
        [
            ("API", "Application Programming Interface"),
            ("ASN", "Autonomous System Number"),
            ("CIDR", "Classless Inter-Domain Routing"),
            ("DNSBL", "Domain Name System Blocklist"),
            ("EDR", "Endpoint Detection and Response"),
            ("IOC", "Indicator of Compromise"),
            ("IP", "Internet Protocol"),
            ("RBL", "Real-time Blackhole List"),
            ("RIR", "Regional Internet Registry"),
            ("RQ", "Research Question"),
            ("TTL", "Time to Live"),
        ], compact=True
    )
    builder.page_break()


def add_introduction(builder):
    builder.heading("Introduction", 1, "ch1_introduction")
    builder.paragraph(
        "A public blocklist is a shared security signal. It may contain an individual IP address, a network prefix, a domain name or a URL that a maintainer has associated with abuse or malicious activity. Network defenders can use such signals to reject traffic, increase a risk score, alert an analyst or prevent a connection. The decision is attractive because it is simple: if an indicator appears in a trusted source, a local system can act on it. The decision is also risky because a public listing is not the same as a complete investigation of the current user of an IP address or domain."
    )
    builder.paragraph(
        "The risk is particularly visible when addresses are reassigned, when a domain changes ownership or hosting, or when an aggregated feed combines sources with different purposes. A list can therefore be useful for reducing exposure while still creating a possibility of false positives. The technical format of the feed does not reveal the full meaning of the entry. A CIDR range may represent a small set of investigated addresses, an entire network controlled by a criminal operation, or a category that is unsuitable for permanent blocking."
    )
    builder.heading("Problem Context", 2, "problem_context")
    builder.paragraph(
        "The project brief identifies three connected problems. First, blocklists are maintained by different organizations and use different collection, verification and update practices. Second, a Danish IP address can appear in a public list even though the current user is unrelated to the activity that caused the original listing. Third, the owner of a benign asset may not have a clear, fast or transparent way to request removal. These problems make it difficult to judge the operational quality of a blocklist from a single lookup."
    )
    builder.paragraph(
        "The study therefore treats a blocklist as a changing socio-technical system. The analysis covers the feed itself, the policy that explains it, the metadata that makes an entry interpretable and the practical process by which an entry can disappear. The Danish perspective is used as a bounded case: the same global feeds will be observed, but the analysis will focus on Danish-related indicators and the implications for organizations operating in Denmark."
    )
    builder.heading("Problem Statement", 2, "problem_statement")
    builder.paragraph(
        "Public blocklists are widely used as security controls, but their transparency, update dynamics and correction mechanisms differ. This creates uncertainty about how reliably a listing represents current risk, how long a Danish address or domain remains listed, how much different lists agree, and how feasible it is for an asset owner to correct an inaccurate entry."
    )
    builder.heading("Aim", 2, "aim")
    builder.paragraph(
        "The aim of the project is to analyse how selected public blocklists identify, distribute, update and remove indicators that are associated with Denmark, and to evaluate what the observed behaviour means for responsible use in network defence."
    )
    builder.heading("Research Questions", 2, "research_questions")
    builder.table(
        ["Question", "Evidence", "Method", "Expected output"],
        [
            ("RQ1. How do the selected public blocklists describe and implement their listing, update, expiry and removal processes?", "Feed documentation, policy pages, metadata, historical snapshots", "Structured document analysis and feed inspection", "Comparison of transparency, update and removal characteristics"),
            ("RQ2. What patterns of listing, persistence, turnover and cross-list overlap are observed for Danish-related IP addresses and domains during the collection period?", "At least 30 days of raw snapshots and normalized observations", "Set analysis, time-series analysis, persistence measures and overlap metrics", "Tables and figures showing measured Danish-related patterns"),
            ("RQ3. What practical and procedural barriers affect the correction or delisting of a benign owned asset?", "Published removal instructions and, only where authorized, a controlled owned-asset case", "Policy coding and process tracing", "Evidence-based assessment of delisting accessibility and limitations"),
        ], widths=[1.55, 1.7, 1.6, 1.65], compact=True
    )
    builder.heading("Scope and Delimitations", 2, "scope_and_delimitations")
    builder.paragraph(
        "The primary unit of analysis is a timestamped observation of an IP address, network prefix, domain or URL in a publicly accessible feed. The project will begin with IPv4 because it is easier to compare across feeds and because the brief specifically emphasizes IP addresses. IPv6 will be included when a selected feed exposes it in a consistent format; otherwise the exclusion will be documented. Domains and URLs will be treated separately from IP networks because a domain can resolve to different addresses and a URL can contain a path that is more specific than the host."
    )
    builder.add_bullets = lambda items, level=0: add_bullets(builder.doc, items, level)
    builder.add_bullets([
        "The study is observational. It does not generate malware, brute-force traffic, scanning activity or false reports in order to obtain a listing.",
        "Active network scanning is allowed only against a lab host owned or explicitly authorized by the group. Public indicators will be enriched with passive lookups and provider APIs where permitted.",
        "A country label is not treated as proof that a current user is Danish. Registration country, geolocation, ASN and DNS evidence will be stored separately and disagreements will be reported.",
        "The project does not claim that an indicator is malicious solely because it appears in one list. It measures list membership and compares supporting evidence.",
        "The project does not measure the complete Internet or every Danish IP address. It studies the selected sources and the Danish-related observations visible through those sources during the defined period.",
    ])
    builder.heading("Expected Contribution", 2, "expected_contribution")
    builder.paragraph(
        "The contribution is a documented, reproducible comparison of selected blocklist systems. It will show which properties can be observed directly from public data, which properties require interpretation, and where a defender should avoid treating a feed as an automatic ground-truth decision. The output will include a cleaned dataset schema, collection scripts, a policy comparison matrix and recommendations for cautious deployment."
    )
    builder.heading("Report Structure", 2, "report_structure")
    builder.paragraph(
        "Chapter 2 explains the technical context and dissects the selected feed types. Chapter 3 reviews the literature and defines the analytical framework. Chapter 4 describes the research design, data collection, analysis, ethics and reproducibility procedures. Chapter 5 will present the measured findings. Chapter 6 will discuss what the findings mean in relation to the literature and operational use. Chapter 7 will answer the research questions and identify limitations and future work."
    )


def add_context(builder):
    builder.heading("Technical Context and Blocklist Dissection", 1, "ch2_technical_context")
    builder.paragraph(
        "This chapter separates the technical mechanism from the policy decision. A list can be distributed as a text file, JSON document, DNS zone, DNS response policy zone, API response or a version-controlled repository. The same IP address may be represented as an individual address in one feed and as part of a CIDR range in another. Before comparing lists, the group must preserve the original representation and then create a normalized form for analysis."
    )
    builder.heading("What a Blocklist Entry Represents", 2, "what_entry_represents")
    builder.paragraph(
        "An entry represents a decision by the list operator to publish an indicator for a stated purpose. It does not automatically identify the person currently using the resource. For example, an IP-based DNSBL may associate an address with spam or a policy category, while a network-level DROP list may describe a range as controlled by a professional cybercrime operation. A domain or URL feed may identify a location used to distribute malware. Those meanings are not interchangeable and should remain visible in the dataset."
    )
    builder.heading("Selected Sources", 2, "selected_sources")
    builder.paragraph(
        "The initial comparison uses three IP-oriented sources and one domain/URL-oriented source. The selection is deliberately heterogeneous: it includes a derived aggregation, a curated network-range list, a short-retention attack-report list and a malware URL feed. The final selection must be frozen before the collection period starts and any changes must be recorded in the method log."
    )
    builder.table(
        ["Source", "Primary object", "Why it is included", "Important limitation"],
        [
            ("FireHOL Level 2 or a documented individual FireHOL ipset", "IP addresses and/or network ranges", "Shows how a public aggregation or normalized ipset combines multiple sources and exposes update information", "A derivative list may inherit the strengths and weaknesses of its source lists; removal may require action at the original source or waiting for retention to expire"),
            ("Spamhaus DROP v4", "IPv4 network ranges in JSON", "Provides a high-confidence network-level comparison with documented criteria, daily review and a defined relationship to SBL removal", "It is a conservative network list and is not comparable to a short-lived individual-IP attack list"),
            ("blocklist.de all.txt", "Individual IPv4 addresses", "Provides a short-retention view of reported attacks and a published 48-hour policy with frequent generation", "The list is based on reported attacks against participating systems and should not be treated as a universal reputation score"),
            ("URLhaus recent or documented API dataset", "Malware URLs, hosts and domains", "Adds the domain/URL dimension and allows a separate comparison of active or recent malware indicators", "URLhaus explicitly distinguishes its country/TLD feeds from blocklists; the group must use the correct dataset and respect authentication and fair-use limits"),
        ], widths=[1.25, 1.25, 2.0, 2.0], compact=True
    )
    builder.heading("Feed Anatomy", 2, "feed_anatomy")
    builder.paragraph(
        "Each raw snapshot should be treated as evidence. The collection record should include the retrieval time in UTC, the source URL, HTTP status, content type, response headers when available, file size, SHA-256 hash and any timestamp embedded by the provider. The parser must not overwrite the raw file. A normalized record may include one indicator per row, but the original line or JSON object should remain available in the raw snapshot or a linked evidence file."
    )
    builder.heading("Blocklist Lifecycle", 2, "blocklist_lifecycle")
    lifecycle = make_lifecycle()
    builder.figure(lifecycle, "Figure 1", "Blocklist entry lifecycle used as the conceptual model for the study.")
    builder.paragraph(
        "The lifecycle in Figure 1 is a model rather than an assumption that every operator follows the same steps. Some sources publish a listing after automated detection, while others require investigation or reports from participating networks. Some entries expire automatically; others remain until the operator or an upstream source removes them. The purpose of the model is to identify which stages are visible in public documentation and which stages can be measured from snapshots."
    )
    builder.heading("Danish Classification", 2, "danish_classification")
    builder.paragraph(
        "The study will not collapse all country signals into one field. For each IP or network, the dataset will store at least: allocation country, geolocation country, origin ASN, reverse DNS name, and the evidence source and retrieval time. A primary Danish candidate can be defined when two independent country signals support Denmark. A conflicting case is retained but marked as uncertain. For domains and URLs, the group will record both the top-level domain and the country associated with the resolved host when the resolution is available."
    )
    builder.table(
        ["Classification", "Rule", "Use in analysis"],
        [
            ("DK-supported", "At least two independent, timestamped signals support Denmark", "Included in primary Danish results"),
            ("DK-weak", "Only one signal supports Denmark, or the source uses a broad/indirect location field", "Reported separately and used in sensitivity analysis"),
            ("Conflicting", "Country signals disagree", "Not included in the primary count; examined as an attribution limitation"),
            ("Unknown", "No reliable country evidence is available", "Retained in the global dataset but excluded from Danish conclusions"),
        ], widths=[1.3, 3.1, 2.1], compact=True
    )
    builder.heading("Operational Meaning", 2, "operational_meaning")
    builder.paragraph(
        "The same observation can lead to different local actions. A defender may block a high-confidence network range at a perimeter router, add a short-lived alert rule for a reported address, or require analyst review before rejecting traffic. The report will therefore avoid a binary question such as whether a list is good or bad. Instead, it will relate the list's stated purpose, evidence and retention behaviour to an appropriate operational use."
    )


def add_literature(builder):
    builder.heading("Literature Review and Theoretical Framework", 1, "ch3_literature")
    builder.paragraph(
        "The literature review is organized around the properties needed to interpret a public blocklist: technical distribution, transparency, dynamics, attribution and contestability. The review should establish what is already known, identify the gap addressed by the Danish case and show how each concept is used in the analysis."
    )
    builder.heading("Search Strategy", 2, "search_strategy")
    builder.paragraph(
        "The group will search IEEE Xplore, ACM Digital Library, Scopus or Web of Science, Google Scholar and the official documentation of the selected list operators. Example search strings are: blocklist transparency; IP blacklist dynamics; DNSBL false positives; IP address reassignment blocklist; blocklist delisting; threat intelligence feed evaluation; and open source blocklist overlap. The search date, database, exact query, inclusion decision and reason for exclusion should be recorded in an appendix."
    )
    builder.table(
        ["Source type", "Purpose", "Quality check"],
        [
            ("Peer-reviewed research", "Concepts, prior measurements and identified limitations", "Venue, authors, method, data period and relevance to the research questions"),
            ("RFCs and standards", "Technical definitions and interoperability details", "Status, scope and whether the document describes or recommends policy"),
            ("Operator documentation", "Current feed format, stated purpose, update and removal procedures", "Official origin, access date, version or timestamp and terms of use"),
            ("Industry or community documentation", "Operational context and implementation examples", "Provenance, independence, date and whether claims are supported by data"),
        ], widths=[1.5, 3.0, 2.0], compact=True
    )
    builder.heading("Blocklist Transparency", 2, "blocklist_transparency")
    builder.paragraph(
        "Feal and co-authors show why open-source blocklists should not be treated as a uniform category. Transparency includes more than making a file downloadable. A useful source can explain its collection process, inclusion criteria, update frequency, retention behaviour, reasons for listing and correction procedure. The present project uses those dimensions as a guide for coding the documentation and then tests which of them are visible in the data."
    )
    builder.paragraph(
        "Transparency is also linked to reproducibility. If a feed changes without a version or timestamp, a later analyst may not be able to reconstruct what a defender saw at the time. The project therefore stores snapshots and hashes rather than relying on the current state of a URL."
    )
    builder.heading("Dynamics and Persistence", 2, "dynamics_and_persistence")
    builder.paragraph(
        "Deri and Fusco evaluate IP blacklists as changing data rather than static lists. This supports the project's decision to measure additions, removals, persistence and overlap over time. A list with many entries can still be highly dynamic, while a smaller list may contain long-lived network ranges. List size alone is therefore not a quality measure."
    )
    builder.paragraph(
        "RFC 5782 explains that DNS blacklist caching and refresh intervals should reflect the expected rate of change of a list. It also distinguishes IP-based and domain-based DNSxLs and notes that policies for adding and removing entries are outside the technical protocol description. This distinction is central to the report: protocol format can be documented objectively, while policy quality must be examined separately."
    )
    builder.heading("Attribution and False-Positive Risk", 2, "attribution_false_positive")
    builder.paragraph(
        "An IP address is an identifier for a network resource, not a permanent identity for a person or organization. Dynamic allocation, hosting changes, NAT and reassignment can separate the current user from the activity that originally produced a listing. A network-range listing introduces a further distinction between the address that was observed and the range selected by the list operator. The analysis will therefore describe evidence and uncertainty instead of using the word malicious as an automatic synonym for listed."
    )
    builder.heading("Contestability and Delisting", 2, "contestability_delisting")
    builder.paragraph(
        "A listing has operational consequences for the asset owner and for users whose traffic is filtered. Contestability refers here to the extent to which an owner can understand the reason for a listing, submit relevant evidence, receive a response and obtain a correction when the original condition no longer applies. This is not a legal judgement about a provider's process. It is an empirical description of the procedure that a benign owner can observe."
    )
    builder.heading("Analytical Framework", 2, "analytical_framework")
    builder.paragraph(
        "The framework combines five dimensions. Each dimension is measured only where the data permits, and the report will distinguish direct observation from interpretation."
    )
    builder.table(
        ["Dimension", "Question asked", "Possible measures"],
        [
            ("Purpose and scope", "What type of behaviour or resource does the source claim to represent?", "Indicator type, individual IP versus CIDR, domain versus URL, stated use"),
            ("Transparency", "Can an independent reader understand how entries are produced and maintained?", "Presence of criteria, source attribution, timestamps, retention and removal information"),
            ("Dynamics", "How does the list change during the observation period?", "Additions, removals, turnover, persistence and update cadence"),
            ("Agreement and provenance", "Do sources agree, and can the origin of an entry be traced?", "Intersection, Jaccard similarity, source links, reason metadata"),
            ("Contestability", "Can a benign owner understand and challenge a listing?", "Delisting channel, evidence requirements, authentication, status and response information"),
        ], widths=[1.5, 3.0, 2.0], compact=True
    )
    builder.heading("Research Gap", 2, "research_gap")
    builder.paragraph(
        "The supplied literature motivates measurement of public blocklists, but the project applies the problem to a bounded Danish case and combines three levels of evidence: the raw feed state, supporting context for Danish classification and the operator's own policy documentation. This combination makes it possible to discuss both measurable list behaviour and the practical uncertainty that remains when an address changes user or location."
    )


def add_methodology(builder):
    builder.heading("Methodology", 1, "ch4_methodology")
    builder.paragraph(
        "The project uses a mixed-methods, observational design. Quantitative analysis is used to measure feed size, Danish-related observations, persistence, turnover and overlap. Qualitative document analysis is used to interpret the operators' stated purpose, evidence requirements, update rules and delisting procedures. The two strands are joined during the discussion rather than being treated as competing explanations."
    )
    builder.heading("Research Design", 2, "research_design")
    builder.paragraph(
        "The study is a comparative longitudinal case study of public blocklist systems as observed during a fixed collection period. The case is Denmark, and the unit of observation is an indicator-source-time combination. The design is suitable because the problem concerns change over time and differences between sources. It also limits the conclusions to the selected feeds, dates and country-classification procedure."
    )
    builder.heading("Data Sources and Inclusion Criteria", 2, "data_sources_inclusion")
    builder.add_bullets([
        "Include only sources with a public, documented access route that the group is permitted to use.",
        "Include the original feed content, not only a third-party summary, whenever the source permits downloading.",
        "Record the source's stated purpose and do not combine lists with incompatible semantics without preserving the source label.",
        "Include an IP or network as Danish-related only after applying the documented classification rules in Chapter 2.",
        "Include domains and URLs as separate indicator types and do not infer a Danish location solely from a .dk suffix.",
        "Exclude private, leaked, credentialed or personally identifying data that is not needed to answer the research questions.",
    ])
    builder.heading("Collection Period and Cadence", 2, "collection_period")
    builder.paragraph(
        "The group should collect a minimum of thirty consecutive days. A daily snapshot at a fixed UTC time is sufficient for the main comparison, provided that the provider's terms allow it. If a source publishes update timestamps more frequently, the group may record those timestamps without increasing the download frequency beyond the provider's documented limit. Each run must record success, failure or partial retrieval. A missing snapshot is data about collection reliability and must not be silently replaced with the current file."
    )
    timeline = make_timeline()
    builder.figure(timeline, "Figure 2", "Recommended 30-day collection checkpoints and quality gates.")
    builder.heading("Run Records and Day to Day Comparison", 2, "run_records_comparison")
    builder.paragraph(
        "The daily pipeline creates a unique run record before collection begins. The record contains UTC start and end times, the executed commands, exit codes, a timestamped event log, the per-run collection log, parser notes, command output logs and a copy of the cumulative analysis produced at that point. This preserves the audit trail when the normalized table or cumulative results are regenerated later."
    )
    builder.paragraph(
        "Day-to-day comparisons are written to a separate comparisons directory and never overwrite the results directory. For each source, the comparison selects the latest snapshot on each of two distinct calendar dates, records the exact snapshot identifiers and SHA-256 hashes, and reports additions, removals, unchanged indicators and percentage change by indicator type. A repeated run on the same date is retained as evidence but is not silently counted as another study day."
    )
    builder.add_bullets([
        "run_manifest.json records the run scope, timestamps, statuses, row counts, hashes and output paths.",
        "run_events.csv records the order and time of collection, normalization, analysis and comparison events.",
        "comparison_manifest.json and snapshot_index.csv identify the exact two input states used for a comparison.",
        "Source-specific change files allow an individual comparison to be reviewed without changing the main analysis.",
    ])
    builder.heading("Data Model and Normalization", 2, "data_model_normalization")
    model = make_data_model()
    builder.figure(model, "Figure 3", "Minimum data model for preserving the relationship between source, snapshot, indicator and interpretation.")
    builder.paragraph(
        "Normalization converts different feed formats into a common observation table while keeping the source representation. For text feeds, comments and explanatory fields should be stored separately before the address or CIDR value is parsed. For JSON feeds, the complete object should be retained and selected fields copied into the normalized table. Network prefixes should be represented with canonical CIDR notation. Domains should be lower-cased, converted to a consistent Unicode representation where necessary and stored with the original value."
    )
    builder.table(
        ["Field", "Description", "Example or allowed value"],
        [
            ("snapshot_id", "Stable identifier for the retrieval", "spamhaus_drop_2026-09-16T03:00:00Z"),
            ("source_name", "Human-readable feed name", "Spamhaus DROP v4"),
            ("retrieved_at_utc", "Time at which the file was retrieved", "2026-09-16T03:00:12Z"),
            ("source_url", "Exact URL used for retrieval", "HTTPS URL"),
            ("sha256", "Hash of the raw file", "64 hexadecimal characters"),
            ("indicator_type", "Semantic type", "ip, cidr, domain, url"),
            ("indicator", "Canonical indicator value", "203.0.113.10 or example.dk"),
            ("source_value", "Original value or line/object reference", "Original raw representation"),
            ("country_class", "Result of Danish classification", "DK-supported, DK-weak, Conflicting, Unknown"),
            ("first_seen", "First snapshot in which the indicator appears", "UTC date"),
            ("last_seen", "Last snapshot in which the indicator appears", "UTC date or null"),
            ("status", "Observation state", "listed, absent, added, removed"),
            ("notes", "Parser or evidence note", "CIDR overlap; country sources disagree"),
        ], widths=[1.45, 3.3, 1.75], compact=True
    )
    builder.heading("Danish Scope Resolution", 2, "danish_scope_resolution")
    builder.paragraph(
        "The group should maintain a separate table of Danish allocation or geolocation evidence. If a feed contains a network prefix, the classifier should test overlap with documented Danish prefixes rather than expanding the entire range into individual addresses. For an individual IP, membership in a Danish prefix can be tested directly. If a prefix covers both Danish and non-Danish address space, the observation should be marked as a range-level case and discussed separately."
    )
    builder.heading("Enrichment", 2, "enrichment")
    builder.paragraph(
        "Enrichment is used to add context, not to create a second unverified verdict. The preferred order is passive and low-impact: RIPEstat or RIR registration data, RDAP, reverse DNS, DNS resolution, and provider APIs used within their terms. AbuseIPDB, GreyNoise and VirusTotal should be queried only for the small Danish-related candidate set or a sampled subset, because free tiers and fair-use limits may apply. API keys must be stored in environment variables and never committed to the project repository."
    )
    builder.heading("Quantitative Analysis", 2, "quantitative_analysis")
    builder.paragraph(
        "The primary analysis will be descriptive. For each source and day, report the total number of unique indicators, the number of Danish-supported and Danish-weak indicators, the number of additions and removals compared with the previous snapshot, and the number of observations with supporting reason or timestamp metadata."
    )
    builder.paragraph(
        "The independent comparison output should be used as a traceable day-pair view of the same evidence. Its source summary reports counts by source and indicator type, while its indicator-change files preserve the canonical value and the previous/current snapshot paths and hashes. This separation allows a comparison to be corrected without changing the cumulative tables used for the main findings."
    )
    builder.paragraph(
        "For an indicator i, persistence during the study window is calculated as the number of snapshots in which i is present divided by the total number of successful snapshots for that source. For two sources A and B, Jaccard similarity is |A intersection B| divided by |A union B|. The report should state whether overlap is calculated on exact IPs, canonical CIDRs, or expanded address membership; exact and network-level comparisons must not be mixed."
    )
    builder.table(
        ["Metric", "Definition", "Interpretation"],
        [
            ("Unique indicators", "Number of distinct canonical entries in a snapshot", "Describes feed size in its own representation"),
            ("Danish candidate count", "Distinct indicators classified DK-supported or DK-weak", "Shows the observed Danish-related subset, not the prevalence of malicious activity in Denmark"),
            ("Additions", "Indicators present today and absent in the preceding successful snapshot", "Shows incoming change"),
            ("Removals", "Indicators absent today and present in the preceding successful snapshot", "Shows outgoing change or feed retrieval effects"),
            ("Persistence", "Observed listed snapshots divided by successful snapshots", "Shows how long an indicator remained visible in the study window"),
            ("Jaccard overlap", "Intersection divided by union for two comparable sets", "Shows exact-set agreement; it does not prove shared evidence"),
            ("Metadata completeness", "Required metadata fields present divided by expected fields", "Shows how interpretable the public entry is"),
        ], widths=[1.55, 3.1, 1.85], compact=True
    )
    builder.heading("Qualitative Policy Analysis", 2, "qualitative_policy_analysis")
    builder.paragraph(
        "The policy analysis will use a coding sheet applied to the same version of each operator's documentation. The group should save a PDF or HTML capture, record the access date and quote only short passages where necessary. Coding should describe what is stated, not what the group wishes the policy said."
    )
    builder.table(
        ["Code", "0", "1", "2"],
        [
            ("Listing criteria", "Not found", "General description", "Specific criteria or evidence described"),
            ("Update information", "Not found", "Approximate cadence", "Cadence and/or timestamps are documented"),
            ("Retention or expiry", "Not found", "General statement", "Duration or removal trigger is documented"),
            ("Reason visibility", "No reason or case reference", "Category only", "Entry-level reason or traceable case reference"),
            ("Delisting channel", "Not found", "Contact channel only", "Clear procedure or self-service route"),
            ("Owner verification", "Not described", "Some identity check", "Clear ownership or authentication requirement"),
            ("Status feedback", "No status information", "Response is possible but unclear", "Status, decision or expected time is described"),
        ], widths=[1.65, 1.5, 1.5, 2.0], compact=True
    )
    builder.paragraph(
        "The ordinal values are a transparent coding device for comparison, not a universal quality score. The final report should include the underlying evidence and explain any disagreement between coders. Two group members should independently code a sample of the policies and resolve differences through discussion."
    )
    builder.heading("Safe Delisting Study", 2, "safe_delisting_study")
    builder.paragraph(
        "The project must not create malicious traffic, submit false reports or intentionally pollute a public reputation service. The delisting question can still be studied through published policies, screenshots of public forms and a controlled case involving an asset owned by the group, but only when the operator's rules allow such contact. A benign asset must never be submitted as malicious merely to obtain a listing. If no safe controlled test is available, RQ3 will be answered from policy evidence and clearly labelled as a procedural analysis rather than a measured response-time experiment."
    )
    builder.heading("Ethics Legal and Privacy Considerations", 2, "ethics_legal_privacy")
    builder.add_bullets([
        "Use only public feeds, public documentation and accounts authorized by the group.",
        "Do not expose API keys, personal email addresses, internal logs or private network details in the repository or report.",
        "Do not scan or connect to public IP addresses merely because they appear in a list. Public listing is not permission to probe a host.",
        "Use reserved documentation ranges such as 192.0.2.0/24 for parser examples, and use an isolated lab host for active testing.",
        "Minimize retention of third-party data and cite the provider's terms. Store only fields needed for the research questions.",
        "If a provider requests contact information in a delisting case, use a group-controlled address and record the process without publishing personal correspondence unless permission is obtained.",
    ])
    builder.heading("Validity Reliability and Limitations", 2, "validity_reliability_limitations")
    builder.paragraph(
        "Internal validity is supported by immutable raw snapshots, hashes, deterministic parsing and an explicit classification rule. Reliability is supported by running the same scripts against each snapshot, testing the parser with known formats and retaining run logs. Construct validity remains limited because list membership measures a provider's published decision, not ground-truth maliciousness. External validity is limited because the sample is restricted to selected public sources and a one-month window. The report must state these limitations rather than presenting the dataset as a complete view of Danish cyber abuse."
    )
    builder.heading("Reproducibility", 2, "reproducibility")
    builder.paragraph(
        "The repository should contain the scripts, a requirements file, a README, the data dictionary, a source register, run logs, file hashes and a redacted sample of normalized output. Full raw feeds may be too large or subject to provider terms; in that case the group should preserve them locally, publish hashes and include a reproducibility note that explains how an examiner can reproduce the retrieval at the documented URL."
    )


def add_findings(builder):
    builder.heading("Findings", 1, "ch5_findings")
    builder.paragraph(
        "This chapter must be completed from the collected dataset. It should report what was observed without explaining why the pattern matters until the discussion chapter. The group should replace bracketed fields with measured values and cite the relevant tables and figures. No number should be entered from an estimate or from a current web lookup after the collection window has closed."
    )
    builder.heading("Dataset Coverage and Quality", 2, "dataset_coverage")
    builder.table(
        ["Source", "Planned snapshots", "Successful snapshots", "Failed or partial", "Raw data hash register", "Notes"],
        [
            ("FireHOL", "[30]", "[insert]", "[insert]", "[file or appendix reference]", "[cadence and format]"),
            ("Spamhaus DROP v4", "[30]", "[insert]", "[insert]", "[file or appendix reference]", "[respect documented download limit]"),
            ("blocklist.de all", "[30]", "[insert]", "[insert]", "[file or appendix reference]", "[generated every 30 minutes; daily sample]"),
            ("URLhaus", "[30]", "[insert]", "[insert]", "[file or appendix reference]", "[dataset and authentication route]"),
        ], widths=[1.2, 1.0, 1.2, 1.0, 1.65, 1.3], compact=True
    )
    builder.paragraph(
        "Describe any missing days, HTTP errors, provider changes, parser corrections or source-format changes here. If a source could not be collected for the full period, do not silently compare it with sources that have complete coverage."
    )
    builder.heading("Feed Size and Update Activity", 2, "feed_size_update_activity")
    builder.paragraph("Insert a time-series figure showing the number of unique canonical indicators per successful snapshot for each source. Keep each source in its own panel when the scales differ substantially.")
    builder.table(
        ["Source", "Minimum", "Maximum", "Median", "Total additions", "Total removals", "Observed update pattern"],
        [
            ("FireHOL", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("Spamhaus DROP v4", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("blocklist.de all", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("URLhaus", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
        ], widths=[1.2, 0.85, 0.85, 0.85, 1.05, 1.05, 1.85], compact=True
    )
    builder.heading("Danish-Related Indicators", 2, "danish_related_findings")
    builder.paragraph(
        "Report DK-supported and DK-weak cases separately. For network ranges, report whether the Danish evidence refers to the whole range or only to an overlapping subrange. Explain how many cases were marked conflicting or unknown, because those categories show the uncertainty of country classification."
    )
    builder.table(
        ["Source", "DK-supported unique", "DK-weak unique", "Conflicting", "Unknown", "Most common indicator type"],
        [
            ("FireHOL", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("Spamhaus DROP v4", "[insert]", "[insert]", "[insert]", "[insert]", "CIDR / [insert]"),
            ("blocklist.de all", "[insert]", "[insert]", "[insert]", "[insert]", "IP / [insert]"),
            ("URLhaus", "[insert]", "[insert]", "[insert]", "[insert]", "domain or URL / [insert]"),
        ], widths=[1.2, 1.2, 1.1, 0.95, 0.85, 1.7], compact=True
    )
    builder.heading("Persistence and Turnover", 2, "persistence_turnover")
    builder.paragraph(
        "Report the distribution of persistence values for Danish-supported indicators. A short observation window can censor long-lived entries: if an indicator is present on day 1 and day 30, the study can say it was present throughout the observed window, but it cannot prove when it was first listed or when it will be removed. Use the term right-censored where appropriate."
    )
    builder.table(
        ["Source", "Median persistence", "75th percentile", "Present on first day", "Present on last day", "Right-censored cases"],
        [
            ("FireHOL", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("Spamhaus DROP v4", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("blocklist.de all", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("URLhaus", "[insert]", "[insert]", "[insert]", "[insert]", "[insert]"),
        ], widths=[1.2, 1.3, 1.25, 1.15, 1.15, 1.55], compact=True
    )
    builder.heading("Cross-List Overlap", 2, "cross_list_overlap")
    builder.paragraph(
        "Present overlap only for comparable indicator types and representation levels. An exact IP intersection is not equivalent to a CIDR-overlap result. Include a matrix of Jaccard values and list the number of indicators that appeared in two or more sources."
    )
    builder.table(
        ["Pair", "Comparison level", "Intersection", "Union", "Jaccard", "Interpretation note"],
        [
            ("FireHOL / Spamhaus", "[exact or network]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("FireHOL / blocklist.de", "[exact IP]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("Spamhaus / blocklist.de", "[not directly comparable or method]", "[insert]", "[insert]", "[insert]", "[insert]"),
            ("URLhaus / IP sources", "[host resolution, if used]", "[insert]", "[insert]", "[insert]", "[insert]"),
        ], widths=[1.35, 1.3, 0.85, 0.85, 0.8, 2.0], compact=True
    )
    builder.heading("Enrichment and Evidence Completeness", 2, "enrichment_findings")
    builder.paragraph(
        "Summarize how often the observed indicator had an identifiable ASN, reverse DNS, country evidence, list reason, source reference or reputation context. Do not convert an AbuseIPDB score, GreyNoise classification or VirusTotal detection count into ground truth. Report the source and timestamp of every enrichment result."
    )
    builder.heading("Policy and Delisting Findings", 2, "policy_delisting_findings")
    builder.table(
        ["Source", "Listing criteria documented", "Update/retention documented", "Reason visible", "Delisting route", "Evidence/authentication", "Status feedback"],
        [
            ("FireHOL", "[0/1/2]", "[0/1/2]", "[0/1/2]", "[text]", "[text]", "[0/1/2]"),
            ("Spamhaus", "[0/1/2]", "[0/1/2]", "[0/1/2]", "[text]", "[text]", "[0/1/2]"),
            ("blocklist.de", "[0/1/2]", "[0/1/2]", "[0/1/2]", "[text]", "[text]", "[0/1/2]"),
            ("URLhaus", "[0/1/2]", "[0/1/2]", "[0/1/2]", "[text]", "[text]", "[0/1/2]"),
        ], widths=[1.1, 1.05, 1.15, 0.85, 1.45, 1.4, 1.0], compact=True
    )
    builder.paragraph(
        "If a controlled owned-asset case was performed, report the steps, dates and response exactly. If it was not performed, state that the delisting results are based on public procedures and explain why a live test was not ethically or technically justified."
    )
    builder.heading("Findings Summary by Research Question", 2, "findings_summary")
    builder.table(
        ["Research question", "Measured answer in one or two sentences", "Evidence"],
        [
            ("RQ1", "[insert concise result based on policy and feed evidence]", "[table/figure/appendix]"),
            ("RQ2", "[insert concise result based on the 30-day dataset]", "[table/figure/appendix]"),
            ("RQ3", "[insert concise result based on delisting procedure evidence]", "[table/figure/appendix]"),
        ], widths=[1.0, 4.5, 1.5], compact=True
    )


def add_discussion(builder):
    builder.heading("Discussion and Analysis", 1, "ch6_discussion")
    builder.paragraph(
        "The discussion must explain the findings in relation to the literature and the problem statement. It should not repeat every number from Chapter 5. Start with the strongest pattern, test whether the evidence supports the interpretation and state where the data is insufficient."
    )
    builder.heading("Meaning of the Main Patterns", 2, "meaning_main_patterns")
    builder.paragraph(
        "Compare the observed behaviour with the stated purpose of each source. If a short-retention list changes rapidly, that may be consistent with its purpose, while a curated network-range list may change more slowly by design. The group should avoid ranking sources without considering these different purposes."
    )
    builder.heading("Transparency and Reproducibility", 2, "discussion_transparency")
    builder.paragraph(
        "Discuss whether the public documentation allowed the group to explain why a source changed, how an entry could be interpreted and how a later analyst could reproduce the snapshot. A source can be technically easy to download but still difficult to audit if reasons, timestamps or provenance are missing."
    )
    builder.heading("Attribution and False-Positive Risk", 2, "discussion_false_positive")
    builder.paragraph(
        "Use the DK-weak and conflicting cases to discuss the limits of country attribution. Relate network-level listings to address reuse, hosting changes and the difference between a range and an individual host. The discussion should distinguish a demonstrated false positive from a plausible false-positive risk. A plausible risk is not proof that the entry is wrong."
    )
    builder.heading("Operational Tradeoffs", 2, "operational_tradeoffs")
    builder.paragraph(
        "A perimeter operator may prefer a conservative high-confidence range list for an immediate drop decision, while an analyst may prefer a broader list as a triage signal. The findings can support a layered recommendation: use purpose-specific feeds, preserve source and reason metadata, apply expiry or revalidation, maintain an allowlist for critical partners and require analyst review for ambiguous entries. The exact recommendation must follow the observed evidence."
    )
    builder.heading("Delisting and Contestability", 2, "discussion_delisting")
    builder.paragraph(
        "Discuss what the policy analysis shows about the path from a listing to a correction. The important distinction is between automatic expiry, removal by the original reporter, provider review and a self-service delisting mechanism. The analysis should also identify whether the process requires proof of ownership, remediation evidence or communication with an upstream provider."
    )
    builder.heading("Comparison with Prior Studies", 2, "comparison_prior_studies")
    builder.paragraph(
        "Return to the findings of Feal et al. and Deri and Fusco. Explain whether the Danish observations support the idea that open blocklists differ substantially in transparency and dynamics, and identify what the case study adds. If the collection period is too short to compare retention reliably, say so instead of forcing a conclusion."
    )
    builder.heading("Limitations and Threats to Validity", 2, "discussion_limitations")
    builder.paragraph(
        "The main limitations are source selection, the one-month observation window, incomplete historical data, country-classification uncertainty, representation differences between IPs and CIDRs, rate limits or access restrictions, and the inability to measure maliciousness directly. Acknowledge that enrichment services have their own collection bias and that a list overlap may reflect shared upstream data rather than independent confirmation."
    )
    builder.heading("Recommendations", 2, "recommendations")
    builder.table(
        ["Recommendation", "Evidence required", "Intended operational effect"],
        [
            ("Use blocklists according to their stated purpose", "Source policy and observed indicator semantics", "Reduce inappropriate blocking"),
            ("Keep the source, timestamp and reason with every local decision", "Raw snapshot, hash and normalized record", "Support investigation and rollback"),
            ("Revalidate dynamic or ambiguous indicators", "Persistence, country conflicts and reassignment evidence", "Reduce stale-list impact"),
            ("Use layered decisions instead of one automatic verdict", "Comparison of confidence and retention characteristics", "Balance protection with availability"),
            ("Document a correction and delisting playbook", "Provider procedures and ownership evidence", "Shorten recovery time after a false positive"),
        ], widths=[2.25, 2.45, 1.8], compact=True
    )


def add_conclusion(builder):
    builder.heading("Conclusion", 1, "ch7_conclusion")
    builder.paragraph(
        "This project investigates public blocklists as changing security systems rather than static lists of bad addresses. The final conclusion must be written after the data collection and should answer the three research questions directly. It should state what was measured, what remained uncertain and what a responsible network defender can take from the evidence."
    )
    builder.heading("Answer to RQ1", 2, "answer_rq1")
    builder.paragraph("[Write the answer in two or three sentences. Compare the selected sources' stated listing, update, expiry and removal processes.]")
    builder.heading("Answer to RQ2", 2, "answer_rq2")
    builder.paragraph("[Write the answer in two or three sentences. Report the strongest Danish-related pattern in persistence, turnover or overlap, supported by the results.]")
    builder.heading("Answer to RQ3", 2, "answer_rq3")
    builder.paragraph("[Write the answer in two or three sentences. State whether the procedures were clear, what evidence was required and whether any practical test was performed safely.]")
    builder.heading("Contribution", 2, "contribution")
    builder.paragraph(
        "The report contributes a reproducible collection method, a normalized dataset structure and a Danish case analysis that keeps feed membership separate from ground-truth attribution. It also provides a practical policy comparison that can help a defender decide when a public feed should trigger an automatic block, an alert or a manual review."
    )
    builder.heading("Future Work", 2, "future_work")
    builder.add_bullets([
        "Extend the collection beyond one month so that longer retention and seasonal changes can be measured.",
        "Compare additional European country cases using the same classification and normalization rules.",
        "Study historical IP reassignment events with a controlled and legally approved dataset.",
        "Evaluate how local firewall, DNS and mail systems behave when the same indicator is represented as an IP, CIDR, domain or URL.",
        "Develop an uncertainty-aware decision model that preserves the original source semantics rather than collapsing all feeds into one score.",
    ])


def add_references(builder):
    builder.heading("References", 1, "references")
    refs = [
        "[1] A. Feal et al., \"Blocklist Babel: On the Transparency and Dynamics of Open Source Blocklisting,\" IEEE Transactions on Network and Service Management, vol. 18, no. 2, pp. 1334-1349, Jun. 2021, doi: 10.1109/TNSM.2021.3075552.",
        "[2] L. Deri and F. Fusco, \"Evaluating IP Blacklists,\" arXiv preprint arXiv:2308.08356, 2023, doi: 10.48550/arXiv.2308.08356.",
        "[3] J. Levine, \"DNS Blacklists and Whitelists,\" RFC 5782, Internet Research Task Force, Feb. 2010. [Online]. Available: https://www.rfc-editor.org/rfc/rfc5782. [Accessed: Sep. 16, 2026].",
        "[4] Aalborg University, \"Curriculum for the Master's Programme in Cyber Security, 2022,\" 2026/2027. [Online]. Available: https://studieordninger.aau.dk/2026/59/6377?lang=en-GB. [Accessed: Sep. 16, 2026].",
        "[5] Aalborg University, \"Distributed Systems Security,\" module description 2026/2027, ESNCYSK1P1. [Online]. Available: https://moduler.aau.dk/course/2026-2027/ESNCYSK1P1. [Accessed: Sep. 16, 2026].",
        "[6] T. Prætorius, \"How to Write (Even) Better Academic Student Reports and Papers: Some Advices to Students,\" 4th ed., Aalborg University Copenhagen, 2017. [Online]. Available: https://doi.org/10.13140/RG.2.2.19116.97921/2. [Accessed: Sep. 16, 2026].",
        "[7] FireHOL, \"FireHOL IP Lists,\" [Online]. Available: https://iplists.firehol.org/. [Accessed: Sep. 16, 2026].",
        "[8] FireHOL, \"blocklist-ipsets,\" GitHub repository, [Online]. Available: https://github.com/firehol/blocklist-ipsets/. [Accessed: Sep. 16, 2026].",
        "[9] The Spamhaus Project, \"Don't Route Or Peer Lists (DROP),\" [Online]. Available: https://www.spamhaus.org/blocklists/do-not-route-or-peer/. [Accessed: Sep. 16, 2026].",
        "[10] blocklist.de, \"Export all blocked IPs,\" [Online]. Available: https://www.blocklist.de/en/export.html. [Accessed: Sep. 16, 2026].",
        "[11] abuse.ch, \"URLhaus Community API,\" [Online]. Available: https://urlhaus.abuse.ch/api/. [Accessed: Sep. 16, 2026].",
        "[12] abuse.ch, \"URLhaus Feeds,\" [Online]. Available: https://urlhaus.abuse.ch/feeds/. [Accessed: Sep. 16, 2026].",
        "[13] AbuseIPDB, \"AbuseIPDB APIv2 Documentation,\" [Online]. Available: https://docs.abuseipdb.com/. [Accessed: Sep. 16, 2026].",
        "[14] GreyNoise, \"Using the GreyNoise v3 API,\" [Online]. Available: https://docs.greynoise.io/docs/using-the-greynoise-api. [Accessed: Sep. 16, 2026].",
        "[15] VirusTotal, \"API v3 Overview,\" [Online]. Available: https://docs.virustotal.com/reference/overview. [Accessed: Sep. 16, 2026].",
        "[16] RIPE NCC, \"What is RIPEstat?\" [Online]. Available: https://stat.ripe.net/docs/getting-started/what-is-ripestat. [Accessed: Sep. 16, 2026].",
    ]
    for ref in refs:
        p = builder.doc.add_paragraph(style="Normal")
        p.paragraph_format.left_indent = Cm(0.4)
        p.paragraph_format.first_line_indent = Cm(-0.4)
        p.paragraph_format.space_after = Pt(6)
        p.add_run(ref)


def add_index(builder):
    builder.heading("Index", 1, "index")
    builder.paragraph("The index is intentionally compact and linked to the first relevant discussion point. Add further terms after the final report text is stable.")
    terms = [
        ("AbuseIPDB", "enrichment"),
        ("Attribution", "attribution_false_positive"),
        ("CIDR", "feed_anatomy"),
        ("Country classification", "danish_classification"),
        ("Delisting", "safe_delisting_study"),
        ("DNSBL", "what_entry_represents"),
        ("False-positive risk", "discussion_false_positive"),
        ("FireHOL", "selected_sources"),
        ("GreyNoise", "enrichment"),
        ("Jaccard similarity", "quantitative_analysis"),
        ("Persistence", "persistence_turnover"),
        ("RIPEstat", "danish_scope_resolution"),
        ("Spamhaus DROP", "selected_sources"),
        ("URLhaus", "selected_sources"),
    ]
    table = builder.doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Term"
    table.rows[0].cells[1].text = "Linked location"
    for term, anchor in terms:
        cells = table.add_row().cells
        cells[0].text = term
        p = cells[1].paragraphs[0]
        p.text = ""
        add_internal_hyperlink(p, anchor.replace("_", " ").title(), anchor)
    style_table(table, compact=True)


def add_appendices(builder):
    builder.heading("Appendices", 1, "appendices")
    builder.heading("Appendix A Data Dictionary", 2, "appendix_a_data_dictionary")
    builder.paragraph("Copy the final data dictionary from the repository here or cite the repository path. Keep it synchronized with the parser and analysis code.")
    builder.heading("Appendix B Source and Policy Register", 2, "appendix_b_source_register")
    builder.table(
        ["Source", "Feed URL", "Policy URL", "Access date", "Terms or rate limit", "Local file pattern"],
        [
            ("FireHOL", "[insert]", "[insert]", "[insert]", "[insert]", "raw/firehol_*.txt"),
            ("Spamhaus", "[insert]", "[insert]", "[insert]", "[insert]", "raw/spamhaus_*.json"),
            ("blocklist.de", "[insert]", "[insert]", "[insert]", "[insert]", "raw/blocklist_de_*.txt"),
            ("URLhaus", "[insert]", "[insert]", "[insert]", "[insert]", "raw/urlhaus_*.csv"),
        ], widths=[1.0, 1.35, 1.35, 0.85, 1.3, 1.25], compact=True
    )
    builder.heading("Appendix C Collection Log", 2, "appendix_c_collection_log")
    builder.table(
        ["UTC timestamp", "Source", "HTTP status", "File size", "SHA-256", "Parser status", "Notes"],
        [
            ("[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[ok/fail]", "[insert]"),
            ("[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[ok/fail]", "[insert]"),
            ("[insert]", "[insert]", "[insert]", "[insert]", "[insert]", "[ok/fail]", "[insert]"),
        ], widths=[1.25, 1.0, 0.85, 0.8, 1.75, 0.85, 1.1], compact=True
    )
    builder.heading("Appendix D Practice Commands", 2, "appendix_d_practice_commands")
    builder.paragraph("The companion runbook contains the exact setup and collection commands. Only use the active scanning commands against an owned or explicitly authorized lab host.")
    builder.heading("Appendix E Reproducibility and Integrity", 2, "appendix_e_reproducibility")
    builder.paragraph("Include the repository commit identifier, Python version, dependency lock or requirements file, operating system, collection dates, parser version and hash register used for the final analysis.")
    builder.heading("Appendix F Group Contribution Log", 2, "appendix_f_contribution")
    builder.table(
        ["Member", "Primary work package", "Secondary review", "Evidence delivered", "Final sign-off"],
        [
            ("Member 1", "Project coordination and introduction", "[insert]", "[insert]", "[insert]"),
            ("Member 2", "Literature review and source register", "[insert]", "[insert]", "[insert]"),
            ("Member 3", "Feed collection and normalization", "[insert]", "[insert]", "[insert]"),
            ("Member 4", "Danish classification and enrichment", "[insert]", "[insert]", "[insert]"),
            ("Member 5", "Quantitative analysis and visualizations", "[insert]", "[insert]", "[insert]"),
            ("Member 6", "Policy, ethics, delisting and conclusion", "[insert]", "[insert]", "[insert]"),
        ], widths=[1.0, 2.45, 1.35, 1.45, 0.95], compact=True
    )


def replace_placeholder_paragraph(doc, token, paragraphs):
    target = None
    for p in doc.paragraphs:
        if p.text.strip() == token:
            target = p
            break
    if target is None:
        return
    parent = target._p.getparent()
    index = parent.index(target._p)
    parent.remove(target._p)
    for offset, (text_value, level, anchor) in enumerate(paragraphs):
        p = OxmlElement("w:p")
        p_pr = OxmlElement("w:pPr")
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:after"), "80")
        p_pr.append(spacing)
        if level > 1:
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), str(360 * (level - 1)))
            p_pr.append(ind)
        p.append(p_pr)
        run_parent = OxmlElement("w:hyperlink")
        run_parent.set(qn("w:anchor"), anchor)
        run_parent.set(qn("w:history"), "1")
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), BLUE.replace("#", ""))
        rpr.append(color)
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rpr.append(u)
        if level == 1:
            b = OxmlElement("w:b")
            rpr.append(b)
        r.append(rpr)
        t = OxmlElement("w:t")
        t.text = text_value
        r.append(t)
        run_parent.append(r)
        p.append(run_parent)
        parent.insert(index + offset, p)


def replace_simple_list(doc, token, entries):
    target = None
    for p in doc.paragraphs:
        if p.text.strip() == token:
            target = p
            break
    if target is None:
        return
    parent = target._p.getparent()
    index = parent.index(target._p)
    parent.remove(target._p)
    for offset, (label, anchor) in enumerate(entries):
        p = OxmlElement("w:p")
        p_pr = OxmlElement("w:pPr")
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:after"), "80")
        p_pr.append(spacing)
        p.append(p_pr)
        link = OxmlElement("w:hyperlink")
        link.set(qn("w:anchor"), anchor)
        link.set(qn("w:history"), "1")
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        c = OxmlElement("w:color")
        c.set(qn("w:val"), BLUE.replace("#", ""))
        rpr.append(c)
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rpr.append(u)
        r.append(rpr)
        t = OxmlElement("w:t")
        t.text = label
        r.append(t)
        link.append(r)
        p.append(link)
        parent.insert(index + offset, p)


def main():
    make_pipeline()
    make_lifecycle()
    make_data_model()
    make_timeline()
    builder = ReportBuilder()
    add_cover(builder)
    add_summary_and_preface(builder)
    add_introduction(builder)
    add_context(builder)
    add_literature(builder)
    add_methodology(builder)
    add_findings(builder)
    add_discussion(builder)
    add_conclusion(builder)
    add_references(builder)
    add_index(builder)
    add_appendices(builder)
    # Replace navigation placeholders after all heading bookmarks are known.
    toc_entries = [(title, level, anchor) for title, level, anchor in builder.headings if title != "Table of Contents"]
    replace_placeholder_paragraph(builder.doc, "[[TOC]]", toc_entries)
    figure_entries = []
    for label, caption in builder.figures:
        anchor = "fig_" + label.lower().replace(" ", "_")
        # Add a bookmark to the first matching caption paragraph.
        for p in builder.doc.paragraphs:
            if p.text.startswith(label + "."):
                add_bookmark(p, anchor, builder.bookmark_counter)
                builder.bookmark_counter += 1
                break
        figure_entries.append((f"{label}. {caption}", anchor))
    replace_simple_list(builder.doc, "[[FIGURES]]", figure_entries)
    # Keep the list deterministic and unique.  Paragraphs inside tables can also
    # appear in the document traversal, so discovering table titles by scanning
    # every paragraph can duplicate entries.
    table_titles = [
        ("Table 1. Research Questions", "research_questions"),
        ("Table 2. Selected Sources", "selected_sources"),
        ("Table 3. Danish Classification", "danish_classification"),
        ("Table 4. Dataset Coverage and Quality", "dataset_coverage"),
        ("Table 5. Feed Size and Update Activity", "feed_size_update_activity"),
        ("Table 6. Danish-Related Indicators", "danish_related_findings"),
        ("Table 7. Persistence and Turnover", "persistence_turnover"),
        ("Table 8. Cross-List Overlap", "cross_list_overlap"),
        ("Table 9. Policy and Delisting Findings", "policy_delisting_findings"),
        ("Table 10. Recommendations", "recommendations"),
        ("Table 11. Appendix B Source and Policy Register", "appendix_b_source_register"),
        ("Table 12. Appendix C Collection Log", "appendix_c_collection_log"),
        ("Table 13. Appendix F Group Contribution Log", "appendix_f_contribution"),
    ]
    table_entries = table_titles
    replace_simple_list(builder.doc, "[[TABLES]]", table_entries)
    output = REPORT_DIR / "Blocklist_Danish_Project_Report_Framework.docx"
    builder.save(output)
    print(output)


if __name__ == "__main__":
    main()

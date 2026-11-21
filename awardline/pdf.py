"""Generate a styled PDF committee note using ReportLab."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.platypus.flowables import Flowable

# ── Colours ──────────────────────────────────────────────────────────────────
BLUE       = colors.HexColor("#1a56db")
BLUE_LIGHT = colors.HexColor("#eff6ff")
RED        = colors.HexColor("#991b1b")
RED_BG     = colors.HexColor("#fff5f5")
RED_BORDER = colors.HexColor("#fca5a5")
GREEN      = colors.HexColor("#065f46")
GREEN_BG   = colors.HexColor("#ecfdf5")
GREEN_BDR  = colors.HexColor("#86efac")
AMBER      = colors.HexColor("#92400e")
AMBER_BG   = colors.HexColor("#fffbeb")
AMBER_BDR  = colors.HexColor("#fcd34d")
MUTED      = colors.HexColor("#6b7280")
BORDER     = colors.HexColor("#e2e5ea")
TEXT       = colors.HexColor("#1a1d23")
WHITE      = colors.white
SOURCE_BG  = colors.HexColor("#f8fafc")
SOURCE_BDR = colors.HexColor("#e2e5ea")

# ── Page margins ─────────────────────────────────────────────────────────────
LEFT_M = RIGHT_M = 20 * mm
TOP_M  = 18 * mm
BOT_M  = 22 * mm
PAGE_W = A4[0] - LEFT_M - RIGHT_M   # usable width


# ── Coloured banner flowable ──────────────────────────────────────────────────
class BannerBox(Flowable):
    def __init__(self, text: str, sub: str, bg: Any, border: Any, text_color: Any, width: float = PAGE_W):
        super().__init__()
        self.text = text
        self.sub = sub
        self.bg = bg
        self.border = border
        self.text_color = text_color
        self.width = width
        self._height = 52

    def wrap(self, aW, aH):
        return self.width, self._height

    def draw(self):
        c = self.canv
        # Background rect
        c.setFillColor(self.bg)
        c.setStrokeColor(self.border)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, self.width, self._height, 4, fill=1, stroke=1)
        # Left accent bar
        c.setFillColor(self.border)
        c.rect(0, 0, 4, self._height, fill=1, stroke=0)
        # Heading
        c.setFillColor(self.text_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(14, self._height - 18, self.text)
        # Sub-text
        c.setFont("Helvetica", 9)
        c.setFillColor(TEXT)
        # Wrap sub text manually
        max_w = self.width - 20
        words = self.sub.split()
        line, lines = "", []
        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, "Helvetica", 9) < max_w:
                line = test
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        y = self._height - 32
        for ln in lines[:2]:
            c.drawString(14, y, ln)
            y -= 13


class HeaderBox(Flowable):
    """Blue header block at the top of the document."""
    def __init__(self, title: str, meta_rows: list[tuple[str, str]], width: float = PAGE_W):
        super().__init__()
        self.title = title
        self.meta_rows = meta_rows
        self.width = width
        self._height = 68 + len(meta_rows) * 14

    def wrap(self, aW, aH):
        return self.width, self._height

    def draw(self):
        c = self.canv
        h = self._height
        c.setFillColor(BLUE)
        c.roundRect(0, 0, self.width, h, 5, fill=1, stroke=0)
        # Org label
        c.setFillColor(colors.HexColor("#bfdbfe"))
        c.setFont("Helvetica", 7.5)
        c.drawString(16, h - 16, "KENYA PUBLIC PROCUREMENT · VALUE-FOR-MONEY COMMITTEE NOTE")
        # Title
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 14)
        # Truncate if too long
        title = self.title if len(self.title) < 70 else self.title[:67] + "…"
        c.drawString(16, h - 34, title)
        # Meta rows
        c.setFont("Helvetica", 8.5)
        y = h - 50
        for label, value in self.meta_rows:
            c.setFillColor(colors.HexColor("#93c5fd"))
            c.drawString(16, y, label + ":")
            c.setFillColor(WHITE)
            lw = c.stringWidth(label + ": ", "Helvetica", 8.5)
            c.drawString(16 + lw, y, value)
            y -= 14


def _style(name: str, **kwargs) -> ParagraphStyle:
    base = getSampleStyleSheet()["Normal"]
    return ParagraphStyle(name, parent=base, **kwargs)


def _fmt(amount: float, currency: str = "KES") -> str:
    return f"{currency} {amount:,.2f}"


def build_pdf(draft: dict, approval: dict | None) -> bytes:
    """Return PDF bytes for the given draft + approval."""
    finding = draft.get("finding") or {}
    note_id = draft.get("note_id", "")
    officer = draft.get("officer") or (approval.get("officer") if approval else "") or ""
    approved_at = (approval.get("approved_at", "") if approval else "")[:10]
    generated = (draft.get("drafted_at") or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    buyer       = finding.get("buyer") or "—"
    query       = finding.get("query") or "—"
    amount      = finding.get("amount") or 0
    currency    = finding.get("currency") or "KES"
    supplier    = finding.get("supplier") or ""
    flagged     = finding.get("flagged")
    median      = finding.get("median")
    ratio       = finding.get("ratio")
    comp_count  = finding.get("comparable_count") or 0
    sources     = finding.get("sources") or []
    history     = finding.get("supplier_history") or {}
    snapshot    = finding.get("snapshot") or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LEFT_M, rightMargin=RIGHT_M,
        topMargin=TOP_M, bottomMargin=BOT_M,
        title=f"Committee Note — {query[:60]}",
        author=officer or "Awardline",
        subject="Value-for-Money Note",
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────
    meta = [("Buyer", buyer)]
    if supplier:
        meta.append(("Supplier", supplier))
    meta.append(("Amount", _fmt(amount, currency)))
    meta.append(("Note ID", note_id))
    if generated:
        meta.append(("Generated", generated))

    story.append(HeaderBox(query, meta))
    story.append(Spacer(1, 6 * mm))

    # ── Verdict banner ────────────────────────────────────────────────────
    if flagged and median is not None:
        sub = (f"The quoted amount of {_fmt(amount, currency)} is {ratio}× the median of "
               f"{comp_count} comparable past contracts (median {_fmt(median, currency)}). "
               "The committee should request justification or seek alternative quotes before award.")
        story.append(BannerBox("🚩  PRICE FLAG RAISED", sub, RED_BG, RED_BORDER, RED))
    elif median is not None:
        sub = (f"The quoted amount of {_fmt(amount, currency)} is {ratio}× the median of "
               f"{comp_count} comparable past contracts (median {_fmt(median, currency)}). "
               "The quote is within reasonable range.")
        story.append(BannerBox("✅  NO PRICE FLAG", sub, GREEN_BG, GREEN_BDR, GREEN))
    else:
        sub = (f"Only {comp_count} comparable contract(s) found. At least 4 are needed to "
               "calculate a reliable median. Proceed with standard due diligence.")
        story.append(BannerBox("⚠   INSUFFICIENT DATA", sub, AMBER_BG, AMBER_BDR, AMBER))

    story.append(Spacer(1, 5 * mm))

    # ── Helper styles ─────────────────────────────────────────────────────
    sec_style = _style("SecHead",
        fontSize=8, fontName="Helvetica-Bold", textColor=MUTED,
        spaceBefore=14, spaceAfter=5, leading=10,
        borderPadding=(0, 0, 4, 0),
    )
    body_style = _style("Body", fontSize=10, leading=14, textColor=TEXT)
    small_style = _style("Small", fontSize=8.5, leading=12, textColor=MUTED)
    label_style = _style("Label", fontSize=9, fontName="Helvetica-Bold", textColor=MUTED, leading=13)
    value_style = _style("Value", fontSize=9.5, leading=13, textColor=TEXT)
    mono_style  = _style("Mono",  fontSize=8.5, fontName="Courier", leading=12, textColor=BLUE)

    def section_rule(title: str):
        return [
            Paragraph(title.upper(), sec_style),
            HRFlowable(width=PAGE_W, thickness=0.5, color=BORDER, spaceAfter=6),
        ]

    # ── Quote details ─────────────────────────────────────────────────────
    story += section_rule("Quote Details")

    detail_rows = [
        ("Procuring Entity", buyer),
        ("Purchase Description", query),
    ]
    if supplier:
        detail_rows.append(("Quoting Supplier", supplier))
    detail_rows.append(("Quoted Amount", _fmt(amount, currency)))
    if median is not None:
        detail_rows.append(("Median (comparable)", _fmt(median, currency)))
        detail_rows.append(("Ratio to Median", f"{ratio}×"))
        detail_rows.append(("Comparable Contracts", str(comp_count)))

    tdata = [[Paragraph(k, label_style), Paragraph(v, value_style)] for k, v in detail_rows]
    t = Table(tdata, colWidths=[45 * mm, PAGE_W - 45 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, colors.HexColor("#f9fafb")]),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    # ── Comparable contracts ──────────────────────────────────────────────
    story += section_rule(f"Comparable PPIP Contracts ({len(sources)})")

    if not sources:
        story.append(Paragraph("No comparable contracts found in the PPIP snapshot.", small_style))
    else:
        for i, src in enumerate(sources, 1):
            same = src.get("same_supplier", False)
            bg = colors.HexColor("#fff7ed") if same else SOURCE_BG
            bdr = colors.HexColor("#fdba74") if same else SOURCE_BDR

            header_text = f"[{i}]  {src.get('ocid', '')}"
            if same:
                header_text += "  ★ SAME SUPPLIER"

            rows = [
                [Paragraph(header_text, mono_style), ""],
                [Paragraph("Buyer", label_style),    Paragraph(src.get("buyer") or "—", value_style)],
                [Paragraph("Title", label_style),    Paragraph(src.get("title") or "—", value_style)],
                [Paragraph("Supplier", label_style), Paragraph(src.get("supplier") or "(not recorded)", value_style)],
                [Paragraph("Amount", label_style),   Paragraph(_fmt(src.get("amount", 0), src.get("currency", "KES")), value_style)],
                [Paragraph("Date", label_style),     Paragraph((src.get("date") or "—")[:10], value_style)],
            ]
            if src.get("matched_words"):
                rows.append([
                    Paragraph("Matched on", label_style),
                    Paragraph(", ".join(src["matched_words"]), value_style),
                ])

            tbl = Table(rows, colWidths=[30 * mm, PAGE_W - 30 * mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  bg),
                ("BACKGROUND",    (0, 1), (-1, -1), bg),
                ("SPAN",          (0, 0), (1, 0)),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("BOX",           (0, 0), (-1, -1), 0.5, bdr),
                ("LINEBELOW",     (0, 0), (-1, 0),  0.5, bdr),
            ]))
            story.append(KeepTogether([tbl, Spacer(1, 3 * mm)]))

    # ── Supplier history ──────────────────────────────────────────────────
    if history and history.get("award_count", 0) > 0:
        story += section_rule(f"Supplier History — {history.get('supplier', '')}")

        summary = (f"{history['supplier']} has {history['award_count']} past PPIP award(s), "
                   f"total value {_fmt(history.get('total_amount', 0), currency)}.")
        story.append(Paragraph(summary, body_style))
        story.append(Spacer(1, 3 * mm))

        for i, award in enumerate(history.get("awards") or [], 1):
            rows = [
                [Paragraph(f"[{i}]  {award.get('ocid', '')}", mono_style), ""],
                [Paragraph("Buyer",  label_style), Paragraph(award.get("buyer") or "—",  value_style)],
                [Paragraph("Title",  label_style), Paragraph(award.get("title") or "—",  value_style)],
                [Paragraph("Amount", label_style), Paragraph(_fmt(award.get("amount", 0), award.get("currency", "KES")), value_style)],
                [Paragraph("Date",   label_style), Paragraph((award.get("date") or "—")[:10], value_style)],
            ]
            tbl = Table(rows, colWidths=[30 * mm, PAGE_W - 30 * mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), SOURCE_BG),
                ("SPAN",          (0, 0), (1, 0)),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("BOX",           (0, 0), (-1, -1), 0.5, SOURCE_BDR),
                ("LINEBELOW",     (0, 0), (-1, 0),  0.5, SOURCE_BDR),
            ]))
            story.append(KeepTogether([tbl, Spacer(1, 3 * mm)]))

    # ── Data source ───────────────────────────────────────────────────────
    if snapshot:
        story += section_rule("Data Source")
        snap_text = f"Kenya PPIP, {snapshot.get('award_count', 0):,} awards"
        if snapshot.get("retrieved_at"):
            snap_text += f" — downloaded {snapshot['retrieved_at'][:10]}"
        story.append(Paragraph(snap_text, small_style))
        story.append(Spacer(1, 2 * mm))

    # ── Caveats ───────────────────────────────────────────────────────────
    story += section_rule("Important Caveats")
    caveats = [
        ("Contract totals, not unit prices",
         "PPIP awards show contract totals only. Verify that each comparable source "
         "represents the same scale of purchase before relying on the median."),
        ("Past awards may be overpriced",
         "A past PPIP award may itself have been inflated. The median is a reference "
         "point for reasonableness, not a certified fair price."),
        ("Human judgement required",
         "This note is a decision-support tool. The committee retains full responsibility "
         "for the award decision."),
    ]
    for title, body in caveats:
        story.append(Paragraph(f"<b>{title}:</b> {body}", small_style))
        story.append(Spacer(1, 2 * mm))

    # ── Signature block ───────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story += section_rule("Authorisation")

    sig_label = _style("SigLabel", fontSize=7.5, fontName="Helvetica-Bold",
                        textColor=MUTED, spaceAfter=16, leading=10)
    sig_name  = _style("SigName",  fontSize=10, fontName="Helvetica-Bold",
                        textColor=TEXT, leading=14)
    sig_date  = _style("SigDate",  fontSize=8.5, textColor=MUTED, leading=12)

    officer_name  = officer or "________________________"
    officer_date  = approved_at or "_______________"
    chair_name    = "________________________"
    chair_date    = "_______________"

    sig_data = [
        [Paragraph("APPROVING OFFICER", sig_label),  Paragraph("COMMITTEE CHAIRPERSON", sig_label)],
        [HRFlowable(width=75*mm, thickness=0.8, color=TEXT), HRFlowable(width=75*mm, thickness=0.8, color=TEXT)],
        [Paragraph(officer_name, sig_name),           Paragraph(chair_name, sig_name)],
        [Paragraph(officer_date, sig_date),            Paragraph(f"Date: {chair_date}", sig_date)],
    ]
    sig_tbl = Table(sig_data, colWidths=[PAGE_W / 2, PAGE_W / 2])
    sig_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(KeepTogether([sig_tbl]))

    # ── Page footer via onPage callback ───────────────────────────────────
    def _footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(LEFT_M, 12 * mm,
                          f"Awardline · Kenya PPIP Value-for-Money Tool · Note {note_id}")
        canvas.drawRightString(A4[0] - RIGHT_M, 12 * mm,
                               f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

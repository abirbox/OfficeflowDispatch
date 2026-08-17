"""CSV + PDF builders for Dispatch reports (permission-aware)."""
import csv
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def build_csv(rows: list, columns: list) -> bytes:
    """columns: list of (header, key)"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for h, _ in columns])
    for r in rows:
        w.writerow([r.get(k, "") if r.get(k) is not None else "" for _, k in columns])
    return buf.getvalue().encode("utf-8")


def build_pdf(title: str, subtitle: str, rows: list, columns: list) -> bytes:
    """Simple tabular PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.2*cm, rightMargin=1.2*cm,
                            topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(title, ParagraphStyle('t', parent=styles['Title'], fontSize=16)))
    story.append(Paragraph(subtitle, ParagraphStyle('s', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
    story.append(Spacer(1, 0.4*cm))

    header = [h for h, _ in columns]
    body = [[str(r.get(k, "") if r.get(k) is not None else "") for _, k in columns] for r in rows]
    tbl = Table([header] + body, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                           ParagraphStyle('f', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))
    doc.build(story)
    return buf.getvalue()

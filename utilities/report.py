import os
import tempfile
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def generate_comprehensive_pdf(all_errors):
    """Generate a well-formatted PDF validation report."""
    try:
        # Temporary file path
        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(temp_dir, f"ADF_Report_{timestamp}.pdf")

        # Set up document
        doc = SimpleDocTemplate(report_file, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()

        # Define custom styles
        custom_styles = {
            'Title': ParagraphStyle(name='Title', parent=styles['Title'], fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=20),
            'SectionHeader': ParagraphStyle(name='SectionHeader', fontSize=14, leading=16, textColor=colors.darkblue, spaceAfter=10),
            'Error': ParagraphStyle(name='Error', fontSize=11, leading=13, textColor=colors.red, leftIndent=20, spaceAfter=5, alignment=TA_LEFT),
            'Success': ParagraphStyle(name='Success', fontSize=11, leading=13, textColor=colors.green, leftIndent=20, spaceAfter=5, alignment=TA_LEFT),
            'Info': ParagraphStyle(name='Info', fontSize=11, leading=13, leftIndent=20, spaceAfter=5, alignment=TA_LEFT),
            'Summary': ParagraphStyle(name='Summary', fontSize=12, leading=14, textColor=colors.purple, spaceAfter=10)
        }

        for name, style in custom_styles.items():
            if name in styles.byName:
                existing = styles[name]
                existing.fontSize = style.fontSize
                existing.leading = style.leading
                existing.textColor = style.textColor
                existing.leftIndent = style.leftIndent
                existing.spaceAfter = style.spaceAfter
                existing.alignment = style.alignment
            else:
                styles.add(style)

        story = []
        story.append(Paragraph("ADF Document Validation Report", styles['Title']))
        story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Info']))
        story.append(Spacer(1, 20))

        # Organize errors
        section_titles = [
            "Font Size Errors", "Font Style Errors", "Table & Figure Caption Errors",
            "Heading Style Errors", "Line Spacing Errors", "Header & Footer Errors",
            "Margin Errors", "Reference Errors"
        ]
        sections = {title: [] for title in section_titles}
        current_section = None

        for entry in all_errors:
            entry_clean = entry.strip()
            if entry_clean in section_titles:
                current_section = entry_clean
            elif entry_clean:
                if "Margins not set" in entry_clean:
                    sections["Margin Errors"].append(entry_clean)
                elif entry_clean.startswith("❌ Reference") or "is not in APA format" in entry_clean:
                    sections["Reference Errors"].append(entry_clean)
                elif current_section and not (current_section == "Header & Footer Errors" and "Reference" in entry_clean):
                    sections[current_section].append(entry_clean)

        sections = {k: v for k, v in sections.items() if v}

        for section_title, contents in sections.items():
            story.append(Paragraph(section_title, styles['SectionHeader']))
            table_data = [["Error Type", "Details"]]
            for content in contents:
                if content.startswith("❌") or "Error:" in content:
                    error_type = "Error"
                elif content.startswith("•") or content.startswith("■"):
                    error_type = "Location"
                else:
                    error_type = "Info"
                table_data.append([error_type, content])

            table = Table(table_data, colWidths=[100, 400])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
            ]))
            story.append(table)
            story.append(Spacer(1, 20))

        # Summary
        story.append(PageBreak())
        story.append(Paragraph("SUMMARY OF FINDINGS", styles['Title']))
        summary_data = [["Check Type", "Errors Found"]]
        total_errors = 0

        for section_title, contents in sections.items():
            count = sum(1 for content in contents if content.startswith("❌") or "Error:" in content)
            summary_data.append([section_title, str(count)])
            total_errors += count

        summary_data.append(["TOTAL ERRORS", str(total_errors)])
        summary_table = Table(summary_data, colWidths=[350, 100])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#D9E1F2")),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))

        # Final Result
        if total_errors == 0:
            story.append(Paragraph("✅ The document meets all ADF formatting requirements.", styles['Success']))
        else:
            story.append(Paragraph("❌ The document requires corrections to meet ADF formatting standards.", styles['Error']))

        doc.build(story)
        print(f"✅ PDF report saved at: {report_file}")
        return report_file

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

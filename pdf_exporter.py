"""
Phone Number OSINT PDF Report Generator
Generates styled PDF reports with monospace hacker-style formatting.
"""

import io
import os
from fpdf import FPDF

# Load branding from config
try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME = "OSINT Bot"
    BRAND_TAGLINE = "Phone Number OSINT Report"


def safe_str(val, default="N/A") -> str:
    if val is None or val == "":
        return default
    return str(val)


class OSINTReportPDF(FPDF):
    """Custom PDF class for OSINT reports."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        # Use built-in monospace font
        self.set_font("Courier", size=10)

    def header(self):
        self.set_font("Courier", "B", 14)
        self.set_text_color(0, 200, 83)
        self.cell(0, 10, "PHONE NUMBER OSINT REPORT", ln=True, align="C")
        self.set_draw_color(0, 200, 83)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Courier", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Powered by {BRAND_NAME} | {BRAND_TAGLINE}", align="C")

    def section_header(self, title: str):
        self.set_font("Courier", "B", 11)
        self.set_text_color(0, 255, 65)
        self.set_fill_color(30, 30, 42)
        self.cell(0, 8, f"  {title}", ln=True, fill=True)
        self.set_draw_color(60, 60, 80)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def label_value(self, label: str, value: str, label_width: int = 45):
        self.set_font("Courier", "B", 9)
        self.set_text_color(160, 160, 180)
        self.cell(label_width, 6, f"  {label}:", align="L")
        self.set_font("Courier", "", 9)
        self.set_text_color(230, 230, 240)
        # Truncate long values
        max_val_len = 130
        if len(value) > max_val_len:
            value = value[:max_val_len] + "..."
        self.cell(0, 6, value, ln=True)

    def record_header(self, num: int):
        self.set_font("Courier", "B", 10)
        self.set_text_color(255, 200, 50)
        self.cell(0, 7, f"  --- Record #{num} ---", ln=True)
        self.ln(1)

    def divider(self):
        self.set_draw_color(60, 60, 80)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)


def generate_osint_pdf(data: dict) -> io.BytesIO:
    """
    Generate a styled PDF of the OSINT report.

    Args:
        data: Combined data dict with number_data and numleak_data.

    Returns:
        io.BytesIO object containing the PDF.
    """
    number = data.get("number", "N/A")
    number_data = data.get("number_data", {})
    numleak_data = data.get("numleak_data", {})

    pdf = OSINTReportPDF()
    pdf.add_page()

    # Target info
    pdf.set_font("Courier", "", 10)
    pdf.set_text_color(160, 160, 180)
    pdf.cell(0, 6, f"  Target: {number}", ln=True)
    pdf.ln(3)

    # === NUMBER DATA SECTION ===
    results = number_data.get("results", [])
    total = number_data.get("total", 0)

    pdf.section_header("PHONE NUMBER INFO")
    pdf.label_value("Number", number)
    pdf.label_value("Total Records", str(total))
    pdf.label_value("Status", "DATA FOUND" if results else "NO DATA")
    pdf.label_value("Source", safe_str(number_data.get("by", "Unknown")))
    pdf.label_value("Channel", safe_str(number_data.get("channel", "N/A")))
    pdf.ln(2)
    pdf.divider()

    if results:
        pdf.section_header("RECORD DETAILS")

        for i, record in enumerate(results[:5], 1):
            pdf.record_header(i)
            pdf.label_value("Owner Name", safe_str(record.get("name")))
            pdf.label_value("Father Name", safe_str(record.get("fname")))
            pdf.label_value("Mobile No", safe_str(record.get("mobile")))
            if record.get("alt") and record["alt"] != "N/A":
                pdf.label_value("Alt Mobile", safe_str(record.get("alt")))
            if record.get("email") and record["email"] != "N/A":
                pdf.label_value("Email", safe_str(record.get("email")))
            pdf.label_value("Circle", safe_str(record.get("circle")))
            pdf.label_value("Address", safe_str(record.get("address")))
            pdf.label_value("Record ID", safe_str(record.get("id")))
            pdf.ln(2)

        if len(results) > 5:
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(128, 128, 128)
            pdf.cell(0, 6, f"  ... and {len(results) - 5} more records", ln=True)
            pdf.ln(2)

    # === NUMLEAK DATA SECTION ===
    chain = numleak_data.get("chain", {})
    calltracer = numleak_data.get("calltracer", {})

    if chain:
        pdf.divider()
        pdf.section_header("DATA LEAK DETAILS")
        pdf.label_value("Title", safe_str(chain.get("title")))
        pdf.label_value("Description", safe_str(chain.get("description", ""))[:100])
        pdf.ln(2)

        leak_records = chain.get("records", [])
        if leak_records:
            for i, record in enumerate(leak_records[:5], 1):
                pdf.record_header(i)
                pdf.label_value("Full Name", safe_str(record.get("FullName")))
                pdf.label_value("Father Name", safe_str(record.get("FatherName")))
                pdf.label_value("Phone", safe_str(record.get("Phone")))
                if record.get("Phone2"):
                    pdf.label_value("Phone 2", safe_str(record.get("Phone2")))
                if record.get("Phone3"):
                    pdf.label_value("Phone 3", safe_str(record.get("Phone3")))
                pdf.label_value("Doc ID", safe_str(record.get("DocumentNumber")))
                pdf.label_value("Address", safe_str(record.get("Adres"))[:80])
                pdf.label_value("Region", safe_str(record.get("Region")))
                pdf.ln(2)

            if len(leak_records) > 5:
                pdf.set_font("Courier", "", 9)
                pdf.set_text_color(128, 128, 128)
                pdf.cell(0, 6, f"  ... and {len(leak_records) - 5} more records", ln=True)
                pdf.ln(2)

    if calltracer:
        pdf.divider()
        pdf.section_header("SIM & DEVICE INFO")
        pdf.label_value("Number", safe_str(calltracer.get("Number")))
        pdf.label_value("SIM Card", safe_str(calltracer.get("SIM card")))
        pdf.label_value("Mobile State", safe_str(calltracer.get("Mobile State")))
        pdf.label_value("Connection", safe_str(calltracer.get("Connection")))
        pdf.label_value("Hometown", safe_str(calltracer.get("Hometown")))
        pdf.label_value("Language", safe_str(calltracer.get("Language")))
        if calltracer.get("IMEI number"):
            pdf.label_value("IMEI", safe_str(calltracer.get("IMEI number")))
        if calltracer.get("MAC address"):
            pdf.label_value("MAC Address", safe_str(calltracer.get("MAC address")))
        if calltracer.get("IP address"):
            pdf.label_value("IP Address", safe_str(calltracer.get("IP address")))
        if calltracer.get("Owner Address"):
            pdf.label_value("Owner Address", safe_str(calltracer.get("Owner Address")))
        if calltracer.get("Refrence City"):
            pdf.label_value("Reference City", safe_str(calltracer.get("Refrence City")))
        if calltracer.get("Mobile Locations"):
            pdf.label_value("Mobile Locations", safe_str(calltracer.get("Mobile Locations"))[:80])
        if calltracer.get("Tower Locations"):
            pdf.label_value("Tower Locations", safe_str(calltracer.get("Tower Locations"))[:80])
        if calltracer.get("Tracking History"):
            pdf.label_value("Tracking History", safe_str(calltracer.get("Tracking History")))
        if calltracer.get("Helpline"):
            pdf.label_value("Helpline", safe_str(calltracer.get("Helpline")))
        if calltracer.get("info"):
            pdf.set_font("Courier", "I", 8)
            pdf.set_text_color(255, 80, 80)
            pdf.cell(0, 6, f"  Note: {safe_str(calltracer.get('info'))}", ln=True)
        pdf.ln(2)

    # Footer divider
    pdf.divider()
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 5, f"  Powered by @{BRAND_NAME}", ln=True)
    pdf.cell(0, 5, f"  Developed by @shadowxdeveloper", ln=True)

    # Save to BytesIO
    buffer = io.BytesIO()
    pdf_bytes = pdf.output()
    buffer.write(pdf_bytes)
    buffer.seek(0)

    return buffer


def generate_text_report(data: dict) -> str:
    """
    Generate a hacker-style monospace text report.

    Args:
        data: Combined data dict with number_data and numleak_data.

    Returns:
        Formatted text string.
    """
    number = data.get("number", "N/A")
    number_data = data.get("number_data", {})
    numleak_data = data.get("numleak_data", {})

    lines = []

    # Header
    lines.append("MOBILE_INFO INTELLIGENCE REPORT")
    lines.append("=" * 50)
    lines.append(f"Target: {number}")
    lines.append("")

    # Number data records
    results = number_data.get("results", [])
    if results:
        for i, record in enumerate(results[:5], 1):
            lines.append(f"RECORD #{i}")
            lines.append("-" * 30)
            lines.append(f"OWNER NAME     : {safe_str(record.get('name'))}")
            lines.append(f"FATHER NAME    : {safe_str(record.get('fname'))}")
            lines.append(f"MOBILE NO      : {safe_str(record.get('mobile'))}")
            if record.get("alt") and record["alt"] != "N/A":
                lines.append(f"ALT MOBILE     : {safe_str(record.get('alt'))}")
            if record.get("email") and record["email"] != "N/A":
                lines.append(f"EMAIL          : {safe_str(record.get('email'))}")
            lines.append(f"CIRCLE         : {safe_str(record.get('circle'))}")
            lines.append(f"ADDRESS        : {safe_str(record.get('address'))}")
            lines.append(f"RECORD ID      : {safe_str(record.get('id'))}")
            lines.append("")

        if len(results) > 5:
            lines.append(f"... and {len(results) - 5} more records")
            lines.append("")

    # Numleak chain data
    chain = numleak_data.get("chain", {})
    if chain:
        lines.append("=" * 50)
        lines.append("DATA LEAK DETAILS")
        lines.append("-" * 30)
        lines.append(f"TITLE          : {safe_str(chain.get('title'))}")
        lines.append(f"DESCRIPTION    : {safe_str(chain.get('description', ''))[:100]}")
        lines.append("")

        leak_records = chain.get("records", [])
        for i, record in enumerate(leak_records[:5], 1):
            lines.append(f"LEAK RECORD #{i}")
            lines.append("-" * 30)
            lines.append(f"FULL NAME      : {safe_str(record.get('FullName'))}")
            lines.append(f"FATHER NAME    : {safe_str(record.get('FatherName'))}")
            lines.append(f"PHONE          : {safe_str(record.get('Phone'))}")
            if record.get("Phone2"):
                lines.append(f"PHONE 2        : {safe_str(record.get('Phone2'))}")
            if record.get("Phone3"):
                lines.append(f"PHONE 3        : {safe_str(record.get('Phone3'))}")
            lines.append(f"DOC ID         : {safe_str(record.get('DocumentNumber'))}")
            lines.append(f"ADDRESS        : {safe_str(record.get('Adres'))[:80]}")
            lines.append(f"REGION         : {safe_str(record.get('Region'))}")
            lines.append("")

        if len(leak_records) > 5:
            lines.append(f"... and {len(leak_records) - 5} more records")
            lines.append("")

    # Calltracer data
    calltracer = numleak_data.get("calltracer", {})
    if calltracer:
        lines.append("=" * 50)
        lines.append("SIM & DEVICE INFO")
        lines.append("-" * 30)
        lines.append(f"NUMBER         : {safe_str(calltracer.get('Number'))}")
        lines.append(f"SIM CARD       : {safe_str(calltracer.get('SIM card'))}")
        lines.append(f"MOBILE STATE   : {safe_str(calltracer.get('Mobile State'))}")
        lines.append(f"CONNECTION     : {safe_str(calltracer.get('Connection'))}")
        lines.append(f"HOMETOWN       : {safe_str(calltracer.get('Hometown'))}")
        lines.append(f"LANGUAGE       : {safe_str(calltracer.get('Language'))}")
        if calltracer.get("IMEI number"):
            lines.append(f"IMEI           : {safe_str(calltracer.get('IMEI number'))}")
        if calltracer.get("MAC address"):
            lines.append(f"MAC ADDRESS    : {safe_str(calltracer.get('MAC address'))}")
        if calltracer.get("IP address"):
            lines.append(f"IP ADDRESS     : {safe_str(calltracer.get('IP address'))}")
        if calltracer.get("Owner Address"):
            lines.append(f"OWNER ADDRESS  : {safe_str(calltracer.get('Owner Address'))}")
        if calltracer.get("Refrence City"):
            lines.append(f"REFERENCE CITY : {safe_str(calltracer.get('Refrence City'))}")
        if calltracer.get("Mobile Locations"):
            lines.append(f"MOB LOCATIONS  : {safe_str(calltracer.get('Mobile Locations'))[:80]}")
        if calltracer.get("Tower Locations"):
            lines.append(f"TOWER LOCS     : {safe_str(calltracer.get('Tower Locations'))[:80]}")
        if calltracer.get("Tracking History"):
            lines.append(f"TRACKING       : {safe_str(calltracer.get('Tracking History'))}")
        if calltracer.get("Helpline"):
            lines.append(f"HELPLINE       : {safe_str(calltracer.get('Helpline'))}")
        lines.append("")

    # Footer
    lines.append("=" * 50)
    lines.append(f"Powered by @{BRAND_NAME}")
    lines.append(f"Developed by @shadowxdeveloper")

    return "\n".join(lines)

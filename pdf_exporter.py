"""
Phone Number OSINT PDF Report Generator
Dark hacker-themed PDF with colored sections and neon accents.
"""

import io
import os
from fpdf import FPDF

# Load branding from config
try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME = "HATHI02"
    BRAND_TAGLINE = "Phone Number OSINT Report"

# Dark hacker color palette
DARK_BG = (18, 18, 24)
SECTION_BG = (28, 28, 40)
HEADER_BG = (35, 35, 50)
NEON_GREEN = (0, 255, 65)
NEON_CYAN = (0, 200, 255)
NEON_PURPLE = (180, 80, 255)
NEON_YELLOW = (255, 220, 50)
NEON_RED = (255, 70, 70)
TEXT_WHITE = (230, 230, 240)
TEXT_GRAY = (140, 140, 160)
TEXT_DIM = (80, 80, 100)
BORDER_COLOR = (50, 50, 70)
DIVIDER_COLOR = (45, 45, 65)


def safe_str(val, default="N/A") -> str:
    if val is None or val == "":
        return default
    return str(val)


class OSINTReportPDF(FPDF):
    """Dark hacker-themed PDF for OSINT reports."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.set_font("Courier", size=9)

    def _draw_dark_bg(self):
        """Fill entire page with dark background."""
        self.set_fill_color(*DARK_BG)
        self.rect(0, 0, 210, 297, "F")

    def header(self):
        self._draw_dark_bg()
        # Top accent bar
        self.set_fill_color(*NEON_GREEN)
        self.rect(0, 0, 210, 3, "F")
        # Title
        self.set_y(10)
        self.set_font("Courier", "B", 18)
        self.set_text_color(*NEON_GREEN)
        self.cell(0, 12, "PHONE NUMBER OSINT", ln=True, align="C")
        self.set_font("Courier", "B", 14)
        self.set_text_color(*NEON_CYAN)
        self.cell(0, 10, "INTELLIGENCE REPORT", ln=True, align="C")
        # Subtitle line
        self.set_draw_color(*NEON_GREEN)
        self.line(30, self.get_y() + 2, 180, self.get_y() + 2)
        self.ln(8)

    def footer(self):
        self.set_y(-20)
        # Bottom accent bar
        self.set_fill_color(*NEON_GREEN)
        self.rect(0, 294, 210, 3, "F")
        # Footer text
        self.set_font("Courier", "", 7)
        self.set_text_color(*TEXT_DIM)
        self.cell(0, 5, f"Powered by @{BRAND_NAME} | {BRAND_TAGLINE}", align="C")
        self.ln(4)
        self.set_text_color(60, 60, 80)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_header(self, title: str, color=None):
        """Draw a colored section header with dark background."""
        if color is None:
            color = NEON_GREEN
        # Background bar
        self.set_fill_color(*SECTION_BG)
        self.rect(10, self.get_y(), 190, 10, "F")
        # Left accent
        self.set_fill_color(*color)
        self.rect(10, self.get_y(), 3, 10, "F")
        # Text
        self.set_font("Courier", "B", 10)
        self.set_text_color(*color)
        self.set_x(16)
        self.cell(0, 10, f"// {title}", ln=True)
        # Bottom line
        self.set_draw_color(*DIVIDER_COLOR)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def label_value(self, label: str, value: str, label_width: int = 42, value_color=None):
        """Draw a label: value pair with colors."""
        if value_color is None:
            value_color = TEXT_WHITE
        self.set_font("Courier", "B", 8)
        self.set_text_color(*TEXT_GRAY)
        self.cell(label_width, 5, f"  {label}:", align="L")
        self.set_font("Courier", "", 8)
        self.set_text_color(*value_color)
        max_len = 135
        if len(value) > max_len:
            value = value[:max_len] + "..."
        self.cell(0, 5, value, ln=True)

    def record_header(self, num: int, color=None):
        """Draw a record separator."""
        if color is None:
            color = NEON_YELLOW
        self.set_fill_color(25, 25, 35)
        self.rect(12, self.get_y(), 186, 7, "F")
        self.set_font("Courier", "B", 9)
        self.set_text_color(*color)
        self.set_x(14)
        self.cell(0, 7, f">>> Record #{num} <<<", ln=True)
        self.ln(1)

    def divider(self):
        """Draw a horizontal divider."""
        y = self.get_y()
        self.set_draw_color(*DIVIDER_COLOR)
        self.line(12, y, 198, y)
        self.ln(4)

    def info_box(self, text: str, color=None):
        """Draw an info box with colored border."""
        if color is None:
            color = NEON_CYAN
        self.set_fill_color(22, 22, 32)
        self.set_draw_color(*color)
        y = self.get_y()
        self.rect(12, y, 186, 8, "DF")
        self.set_font("Courier", "B", 8)
        self.set_text_color(*color)
        self.set_x(14)
        self.cell(0, 8, f"  {text}", ln=True)
        self.ln(2)


def generate_osint_pdf(data: dict) -> io.BytesIO:
    """Generate a dark hacker-themed PDF of the OSINT report."""
    number = data.get("number", "N/A")
    number_data = data.get("number_data", {})
    numleak_data = data.get("numleak_data", {})

    pdf = OSINTReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Target info box
    pdf.info_box(f"TARGET: {number}", NEON_CYAN)
    pdf.ln(2)

    # === NUMBER DATA SECTION ===
    results = number_data.get("results", [])
    total = number_data.get("total", 0)

    pdf.section_header("PHONE NUMBER INFO", NEON_GREEN)
    pdf.label_value("Number", number)
    pdf.label_value("Total Records", str(total), value_color=NEON_YELLOW if results else NEON_RED)
    pdf.label_value("Status", "DATA FOUND" if results else "NO DATA",
                    value_color=NEON_GREEN if results else NEON_RED)
    pdf.label_value("Source", safe_str(number_data.get("by", "Unknown")))
    pdf.label_value("Channel", safe_str(number_data.get("channel", "N/A")))
    pdf.ln(2)
    pdf.divider()

    if results:
        pdf.section_header("RECORD DETAILS", NEON_PURPLE)

        for i, record in enumerate(results[:5], 1):
            pdf.record_header(i, NEON_YELLOW)
            pdf.label_value("Owner Name", safe_str(record.get("name")), value_color=NEON_GREEN)
            pdf.label_value("Father Name", safe_str(record.get("fname")))
            pdf.label_value("Mobile No", safe_str(record.get("mobile")), value_color=NEON_CYAN)
            if record.get("alt") and record["alt"] != "N/A":
                pdf.label_value("Alt Mobile", safe_str(record.get("alt")))
            if record.get("email") and record["email"] != "N/A":
                pdf.label_value("Email", safe_str(record.get("email")))
            pdf.label_value("Circle", safe_str(record.get("circle")))
            addr = safe_str(record.get("address"))
            if len(addr) > 80:
                addr = addr[:80] + "..."
            pdf.label_value("Address", addr)
            pdf.label_value("Record ID", safe_str(record.get("id")), value_color=TEXT_DIM)
            pdf.ln(2)

        if len(results) > 5:
            pdf.set_font("Courier", "", 8)
            pdf.set_text_color(*TEXT_DIM)
            pdf.cell(0, 5, f"  ... and {len(results) - 5} more records", ln=True)
            pdf.ln(2)

    # === NUMLEAK DATA SECTION ===
    chain = numleak_data.get("chain", {})
    calltracer = numleak_data.get("calltracer", {})

    if chain:
        pdf.divider()
        pdf.section_header("DATA LEAK DETAILS", NEON_RED)
        pdf.label_value("Title", safe_str(chain.get("title")), value_color=NEON_YELLOW)
        desc = safe_str(chain.get("description", ""))[:100]
        pdf.label_value("Description", desc)
        pdf.ln(2)

        leak_records = chain.get("records", [])
        if leak_records:
            pdf.section_header("LEAKED RECORDS", NEON_RED)
            for i, record in enumerate(leak_records[:5], 1):
                pdf.record_header(i, NEON_RED)
                pdf.label_value("Full Name", safe_str(record.get("FullName")), value_color=NEON_GREEN)
                pdf.label_value("Father Name", safe_str(record.get("FatherName")))
                pdf.label_value("Phone", safe_str(record.get("Phone")), value_color=NEON_CYAN)
                if record.get("Phone2"):
                    pdf.label_value("Phone 2", safe_str(record.get("Phone2")))
                if record.get("Phone3"):
                    pdf.label_value("Phone 3", safe_str(record.get("Phone3")))
                pdf.label_value("Doc ID", safe_str(record.get("DocumentNumber")))
                pdf.label_value("Address", safe_str(record.get("Adres"))[:80])
                pdf.label_value("Region", safe_str(record.get("Region")))
                pdf.ln(2)

            if len(leak_records) > 5:
                pdf.set_font("Courier", "", 8)
                pdf.set_text_color(*TEXT_DIM)
                pdf.cell(0, 5, f"  ... and {len(leak_records) - 5} more records", ln=True)
                pdf.ln(2)

    if calltracer:
        pdf.divider()
        pdf.section_header("SIM & DEVICE INFO", NEON_CYAN)
        pdf.label_value("Number", safe_str(calltracer.get("Number")))
        pdf.label_value("SIM Card", safe_str(calltracer.get("SIM card")), value_color=NEON_GREEN)
        pdf.label_value("Mobile State", safe_str(calltracer.get("Mobile State")))
        pdf.label_value("Connection", safe_str(calltracer.get("Connection")), value_color=NEON_CYAN)
        pdf.label_value("Hometown", safe_str(calltracer.get("Hometown")))
        pdf.label_value("Language", safe_str(calltracer.get("Language")))
        if calltracer.get("IMEI number"):
            pdf.label_value("IMEI", safe_str(calltracer.get("IMEI number")), value_color=NEON_YELLOW)
        if calltracer.get("MAC address"):
            pdf.label_value("MAC Address", safe_str(calltracer.get("MAC address")))
        if calltracer.get("IP address"):
            pdf.label_value("IP Address", safe_str(calltracer.get("IP address")), value_color=NEON_RED)
        if calltracer.get("Owner Address"):
            pdf.label_value("Owner Address", safe_str(calltracer.get("Owner Address"))[:80])
        if calltracer.get("Refrence City"):
            pdf.label_value("Reference City", safe_str(calltracer.get("Refrence City")))
        if calltracer.get("Mobile Locations"):
            pdf.label_value("Mobile Locs", safe_str(calltracer.get("Mobile Locations"))[:70])
        if calltracer.get("Tower Locations"):
            pdf.label_value("Tower Locs", safe_str(calltracer.get("Tower Locations"))[:70])
        if calltracer.get("Tracking History"):
            pdf.label_value("Tracking", safe_str(calltracer.get("Tracking History")), value_color=NEON_YELLOW)
        if calltracer.get("Helpline"):
            pdf.label_value("Helpline", safe_str(calltracer.get("Helpline")))
        if calltracer.get("info"):
            pdf.info_box(f"NOTE: {safe_str(calltracer.get('info'))}", NEON_RED)
        pdf.ln(2)

    # Footer branding
    pdf.divider()
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(*TEXT_DIM)
    pdf.cell(0, 4, f"  Powered by @HATHI02", ln=True)
    pdf.cell(0, 4, f"  Developed by @shadowxdeveloper", ln=True)

    # Save to BytesIO
    buffer = io.BytesIO()
    pdf_bytes = pdf.output()
    buffer.write(pdf_bytes)
    buffer.seek(0)

    return buffer


def generate_text_report(data: dict) -> str:
    """Generate a hacker-style monospace text report."""
    number = data.get("number", "N/A")
    number_data = data.get("number_data", {})
    numleak_data = data.get("numleak_data", {})

    lines = []

    # Header
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║       MOBILE_INFO INTELLIGENCE REPORT           ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append(f"  Target: {number}")
    lines.append("")

    # Number data records
    results = number_data.get("results", [])
    if results:
        for i, record in enumerate(results[:5], 1):
            lines.append(f"  ┌── RECORD #{i} ──")
            lines.append(f"  │ OWNER NAME     : {safe_str(record.get('name'))}")
            lines.append(f"  │ FATHER NAME    : {safe_str(record.get('fname'))}")
            lines.append(f"  │ MOBILE NO      : {safe_str(record.get('mobile'))}")
            if record.get("alt") and record["alt"] != "N/A":
                lines.append(f"  │ ALT MOBILE     : {safe_str(record.get('alt'))}")
            if record.get("email") and record["email"] != "N/A":
                lines.append(f"  │ EMAIL          : {safe_str(record.get('email'))}")
            lines.append(f"  │ CIRCLE         : {safe_str(record.get('circle'))}")
            lines.append(f"  │ ADDRESS        : {safe_str(record.get('address'))}")
            lines.append(f"  │ RECORD ID      : {safe_str(record.get('id'))}")
            lines.append(f"  └{'─' * 40}")
            lines.append("")

        if len(results) > 5:
            lines.append(f"  ... and {len(results) - 5} more records")
            lines.append("")

    # Numleak chain data
    chain = numleak_data.get("chain", {})
    if chain:
        lines.append("=" * 50)
        lines.append("  DATA LEAK DETAILS")
        lines.append("-" * 50)
        lines.append(f"  TITLE          : {safe_str(chain.get('title'))}")
        lines.append(f"  DESCRIPTION    : {safe_str(chain.get('description', ''))[:100]}")
        lines.append("")

        leak_records = chain.get("records", [])
        for i, record in enumerate(leak_records[:5], 1):
            lines.append(f"  ┌── LEAK RECORD #{i} ──")
            lines.append(f"  │ FULL NAME      : {safe_str(record.get('FullName'))}")
            lines.append(f"  │ FATHER NAME    : {safe_str(record.get('FatherName'))}")
            lines.append(f"  │ PHONE          : {safe_str(record.get('Phone'))}")
            if record.get("Phone2"):
                lines.append(f"  │ PHONE 2        : {safe_str(record.get('Phone2'))}")
            if record.get("Phone3"):
                lines.append(f"  │ PHONE 3        : {safe_str(record.get('Phone3'))}")
            lines.append(f"  │ DOC ID         : {safe_str(record.get('DocumentNumber'))}")
            lines.append(f"  │ ADDRESS        : {safe_str(record.get('Adres'))[:80]}")
            lines.append(f"  │ REGION         : {safe_str(record.get('Region'))}")
            lines.append(f"  └{'─' * 40}")
            lines.append("")

        if len(leak_records) > 5:
            lines.append(f"  ... and {len(leak_records) - 5} more records")
            lines.append("")

    # Calltracer data
    calltracer = numleak_data.get("calltracer", {})
    if calltracer:
        lines.append("=" * 50)
        lines.append("  SIM & DEVICE INFO")
        lines.append("-" * 50)
        lines.append(f"  NUMBER         : {safe_str(calltracer.get('Number'))}")
        lines.append(f"  SIM CARD       : {safe_str(calltracer.get('SIM card'))}")
        lines.append(f"  MOBILE STATE   : {safe_str(calltracer.get('Mobile State'))}")
        lines.append(f"  CONNECTION     : {safe_str(calltracer.get('Connection'))}")
        lines.append(f"  HOMETOWN       : {safe_str(calltracer.get('Hometown'))}")
        lines.append(f"  LANGUAGE       : {safe_str(calltracer.get('Language'))}")
        if calltracer.get("IMEI number"):
            lines.append(f"  IMEI           : {safe_str(calltracer.get('IMEI number'))}")
        if calltracer.get("MAC address"):
            lines.append(f"  MAC ADDRESS    : {safe_str(calltracer.get('MAC address'))}")
        if calltracer.get("IP address"):
            lines.append(f"  IP ADDRESS     : {safe_str(calltracer.get('IP address'))}")
        if calltracer.get("Owner Address"):
            lines.append(f"  OWNER ADDRESS  : {safe_str(calltracer.get('Owner Address'))}")
        if calltracer.get("Refrence City"):
            lines.append(f"  REFERENCE CITY : {safe_str(calltracer.get('Refrence City'))}")
        if calltracer.get("Mobile Locations"):
            lines.append(f"  MOB LOCATIONS  : {safe_str(calltracer.get('Mobile Locations'))[:80]}")
        if calltracer.get("Tower Locations"):
            lines.append(f"  TOWER LOCS     : {safe_str(calltracer.get('Tower Locations'))[:80]}")
        if calltracer.get("Tracking History"):
            lines.append(f"  TRACKING       : {safe_str(calltracer.get('Tracking History'))}")
        if calltracer.get("Helpline"):
            lines.append(f"  HELPLINE       : {safe_str(calltracer.get('Helpline'))}")
        lines.append("")

    # Footer
    lines.append("═" * 50)
    lines.append(f"  Powered by @HATHI02")
    lines.append(f"  Developed by @shadowxdeveloper")

    return "\n".join(lines)

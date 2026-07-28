"""
Phone Number OSINT PDF Report Generator
Dark hacker-themed PDF with colored sections and neon accents.
"""

import io
import os
import re
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


# Regex to strip emoji and other non-ASCII characters not supported by Courier font
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Misc symbols & pictographs
    "\U0001F680-\U0001F6FF"  # Transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # Flags
    "\U00002702-\U000027B0"  # Dingbats
    "\U000024C2-\U0001F251"  # Enclosed characters
    "\U0001F900-\U0001F9FF"  # Supplemental symbols & pictographs
    "\U0001FA00-\U0001FA6F"  # Chess symbols
    "\U0001FA70-\U0001FAFF"  # Symbols extended-A
    "\U00002600-\U000026FF"  # Misc symbols
    "\U00002B50\U00002764\U0000FE0F\U0000203C\U00002049\U000020A0-\U000020CF"  # Common emoji ranges
    "]+", flags=re.UNICODE
)


def safe_str(val, default="N/A") -> str:
    """Safely convert a value to string, stripping emoji that Courier font cannot render."""
    if val is None or val == "":
        return default
    result = str(val)
    # Strip emoji characters not supported by Courier font
    result = _EMOJI_PATTERN.sub("", result)
    return result if result else default


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
    pdf.cell(0, 4, f"  Owner: @HATHI02 | Developer: @shadowxdeveloper", ln=True)

    # Save to BytesIO
    buffer = io.BytesIO()
    pdf_bytes = pdf.output()
    buffer.write(pdf_bytes)
    buffer.seek(0)

    return buffer


def generate_text_report(data: dict) -> str:
    """Generate a text report showing ALL available phone lookup data."""
    number = data.get("number", "N/A")
    number_data = data.get("number_data", {})
    numleak_data = data.get("numleak_data", {})

    lines = []

    # Header
    lines.append("📱 Phone Lookup Result")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📞 Number: {number}")
    lines.append("")

    # === NUMBER DATA RECORDS ===
    results = number_data.get("results", [])
    if results:
        for i, record in enumerate(results[:5], 1):
            lines.append(f"━━ Record #{i} ━━")
            # Show ALL fields from the record
            if record.get("name"): lines.append(f"👤 Name: {safe_str(record.get('name'))}")
            if record.get("fname"): lines.append(f"👨 Father: {safe_str(record.get('fname'))}")
            if record.get("mobile"): lines.append(f"📞 Phone: {safe_str(record.get('mobile'))}")
            if record.get("alt"): lines.append(f"📱 Alt: {safe_str(record.get('alt'))}")
            if record.get("email"): lines.append(f"✉️ Email: {safe_str(record.get('email'))}")
            if record.get("circle"): lines.append(f"📎 Circle: {safe_str(record.get('circle'))}")
            if record.get("operator"): lines.append(f"📡 Operator: {safe_str(record.get('operator'))}")
            if record.get("state"): lines.append(f"🗺 State: {safe_str(record.get('state'))}")
            if record.get("address"): lines.append(f"📍 Address: {safe_str(record.get('address'))}")
            if record.get("id"): lines.append(f"🔢 ID: {safe_str(record.get('id'))}")
            # Show any other fields we might have missed
            for key, value in record.items():
                if key in ["name","fname","mobile","alt","email","circle","operator","state","address","id"]:
                    continue
                if value and str(value) not in ["", "N/A", "None"]:
                    lines.append(f"🔹 {key.replace('_',' ').title()}: {safe_str(value)}")
            lines.append("")

        if len(results) > 5:
            lines.append(f"... and {len(results) - 5} more records")
            lines.append("")

    # === LEAK DATA ===
    chain = numleak_data.get("chain", {})
    if chain:
        lines.append("━━ LEAK DATA ━━")
        if chain.get("title"): lines.append(f"📛 Source: {safe_str(chain.get('title'))}")
        desc = safe_str(chain.get("description", ""))[:120]
        if desc and desc != "N/A": lines.append(f"📝 Info: {desc}")
        lines.append("")

        leak_records = chain.get("records", [])
        for i, record in enumerate(leak_records[:10], 1):
            lines.append(f"━━ Leak Record #{i} ━━")
            if record.get("FullName"): lines.append(f"👤 Name: {safe_str(record.get('FullName'))}")
            if record.get("FatherName"): lines.append(f"👨 Father: {safe_str(record.get('FatherName'))}")
            if record.get("Phone"): lines.append(f"📞 Phone: {safe_str(record.get('Phone'))}")
            if record.get("Phone2"): lines.append(f"📱 Alt: {safe_str(record.get('Phone2'))}")
            if record.get("Phone3"): lines.append(f"📱 Alt2: {safe_str(record.get('Phone3'))}")
            if record.get("DocumentNumber"): lines.append(f"🆔 Doc ID: {safe_str(record.get('DocumentNumber'))}")
            if record.get("Adres"): lines.append(f"📍 Address: {safe_str(record.get('Adres'))[:80]}")
            if record.get("Region"): lines.append(f"🗺 Region: {safe_str(record.get('Region'))}")
            # Show any other fields
            for key, value in record.items():
                if key in ["FullName","FatherName","Phone","Phone2","Phone3","DocumentNumber","Adres","Region"]:
                    continue
                if value and str(value) not in ["", "N/A", "None"]:
                    lines.append(f"🔹 {key.replace('_',' ').title()}: {safe_str(value)}")
            lines.append("")

        if len(leak_records) > 10:
            lines.append(f"... and {len(leak_records) - 10} more records")
            lines.append("")

    # === SIM / CALLTRACER DATA - ALL FIELDS ===
    calltracer = numleak_data.get("calltracer", {})
    if calltracer:
        lines.append("━━ SIM INFO ━━")
        mapped = set()
        # Core fields
        if calltracer.get("Number"): 
            lines.append(f"📞 Number: {safe_str(calltracer.get('Number'))}")
            mapped.add("Number")
        if calltracer.get("SIM card") or calltracer.get("SIM"): 
            v = calltracer.get("SIM card") or calltracer.get("SIM")
            lines.append(f"💳 SIM: {safe_str(v)}")
            mapped.update(["SIM card","SIM"])
        if calltracer.get("Mobile State") or calltracer.get("state"): 
            v = calltracer.get("Mobile State") or calltracer.get("state")
            lines.append(f"🗺 State: {safe_str(v)}")
            mapped.update(["Mobile State","state"])
        if calltracer.get("Connection") or calltracer.get("connection"): 
            v = calltracer.get("Connection") or calltracer.get("connection")
            lines.append(f"🔗 Connection: {safe_str(v)}")
            mapped.update(["Connection","connection"])
        if calltracer.get("Hometown") or calltracer.get("hometown"): 
            v = calltracer.get("Hometown") or calltracer.get("hometown")
            lines.append(f"🏠 Hometown: {safe_str(v)}")
            mapped.update(["Hometown","hometown"])
        if calltracer.get("Language") or calltracer.get("language"):
            v = calltracer.get("Language") or calltracer.get("language") 
            lines.append(f"🗣 Language: {safe_str(v)}")
            mapped.update(["Language","language"])
        if calltracer.get("IMEI number") or calltracer.get("imei"):
            v = calltracer.get("IMEI number") or calltracer.get("imei")
            lines.append(f"🔢 IMEI: {safe_str(v)}")
            mapped.update(["IMEI number","imei"])
        if calltracer.get("MAC address") or calltracer.get("mac"):
            v = calltracer.get("MAC address") or calltracer.get("mac")
            lines.append(f"💻 MAC: {safe_str(v)}")
            mapped.update(["MAC address","mac"])
        if calltracer.get("IP address") or calltracer.get("ip"):
            v = calltracer.get("IP address") or calltracer.get("ip")
            lines.append(f"🌐 IP: {safe_str(v)}")
            mapped.update(["IP address","ip"])
        if calltracer.get("Owner Address"):
            lines.append(f"👤 Owner Addr: {safe_str(calltracer.get('Owner Address'))[:80]}")
            mapped.add("Owner Address")
        if calltracer.get("Refrence City") or calltracer.get("reference_city"):
            v = calltracer.get("Refrence City") or calltracer.get("reference_city")
            lines.append(f"🏙 City: {safe_str(v)}")
            mapped.update(["Refrence City","reference_city"])
        if calltracer.get("Mobile Locations"):
            lines.append(f"📍 Mobile Locs: {safe_str(calltracer.get('Mobile Locations'))[:80]}")
            mapped.add("Mobile Locations")
        if calltracer.get("Tower Locations"):
            lines.append(f"📡 Tower Locs: {safe_str(calltracer.get('Tower Locations'))[:80]}")
            mapped.add("Tower Locations")
        if calltracer.get("Tracking History"):
            lines.append(f"📍 Tracking: {safe_str(calltracer.get('Tracking History'))}")
            mapped.add("Tracking History")
        if calltracer.get("Helpline"):
            lines.append(f"📞 Helpline: {safe_str(calltracer.get('Helpline'))}")
            mapped.add("Helpline")
        if calltracer.get("info"):
            lines.append(f"ℹ️ Info: {safe_str(calltracer.get('info'))}")
            mapped.add("info")
        # Show any OTHER calltracer fields we haven't covered
        for key, value in calltracer.items():
            if key in mapped:
                continue
            if value and str(value) not in ["", "N/A", "None"]:
                lines.append(f"🔹 {key.replace('_',' ').title()}: {safe_str(value)}")
        lines.append("")

    if not results and not chain and not calltracer:
        lines.append("No data found for this number.")
        lines.append("")

    lines.append("⚡ Owner: @HATHI02 | Developer: @shadowxdeveloper")
    return "\n".join(lines)




# === NUMLEAK TEXT REPORT ===
def generate_numleak_text_report(data: dict) -> str:
    """Generate a text report for numleak data (breach/leak details)."""
    number = data.get("number", "N/A")
    numleak_data = data.get("numleak_data", {})

    lines = []
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║       DATA LEAK INTELLIGENCE REPORT             ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append(f"  Target: {number}")
    lines.append("")

    chain = numleak_data.get("chain", {})
    calltracer = numleak_data.get("calltracer", {})

    # Chain / breach source data
    if chain:
        lines.append("=" * 50)
        lines.append("  BREACH SOURCE")
        lines.append("-" * 50)
        lines.append(f"  TITLE          : {safe_str(chain.get('title'))}")
        lines.append(f"  DESCRIPTION    : {safe_str(chain.get('description', ''))[:120]}")
        lines.append("")

        leak_records = chain.get("records", [])
        for i, record in enumerate(leak_records[:10], 1):
            lines.append(f"  ┌── LEAK RECORD #{i} ──")
            lines.append(f"  │ FULL NAME      : {safe_str(record.get('FullName'))}")
            lines.append(f"  │ FATHER NAME    : {safe_str(record.get('FatherName'))}")
            lines.append(f"  │ DOCUMENT       : {safe_str(record.get('DocumentNumber'))}")
            lines.append(f"  │ PHONE          : {safe_str(record.get('Phone'))}")
            if record.get("Phone2"):
                lines.append(f"  │ PHONE 2        : {safe_str(record.get('Phone2'))}")
            if record.get("Phone3"):
                lines.append(f"  │ PHONE 3        : {safe_str(record.get('Phone3'))}")
            lines.append(f"  │ ADDRESS        : {safe_str(record.get('Adres'))[:80]}")
            lines.append(f"  │ REGION         : {safe_str(record.get('Region'))}")
            lines.append(f"  └{'─' * 40}")
            lines.append("")

        if len(leak_records) > 10:
            lines.append(f"  ... and {len(leak_records) - 10} more records")
            lines.append("")

    # Calltracer data
    if calltracer:
        lines.append("=" * 50)
        lines.append("  CARRIER / SIM INFO")
        lines.append("-" * 50)
        lines.append(f"  NUMBER         : {safe_str(calltracer.get('Number'))}")
        lines.append(f"  SIM CARD       : {safe_str(calltracer.get('SIM card'))}")
        lines.append(f"  MOBILE STATE   : {safe_str(calltracer.get('Mobile State'))}")
        lines.append(f"  CONNECTION     : {safe_str(calltracer.get('Connection'))}")
        if calltracer.get("Hometown"):
            lines.append(f"  HOMETOWN       : {safe_str(calltracer.get('Hometown'))}")
        if calltracer.get("Language"):
            lines.append(f"  LANGUAGE       : {safe_str(calltracer.get('Language'))}")
        if calltracer.get("IMEI number"):
            lines.append(f"  IMEI           : {safe_str(calltracer.get('IMEI number'))}")
        if calltracer.get("Tracking History"):
            lines.append(f"  TRACKING       : {safe_str(calltracer.get('Tracking History'))}")
        lines.append("")

    if not chain and not calltracer:
        lines.append("  No leak or carrier data found for this number.")
        lines.append("")

    lines.append("═" * 50)
    lines.append(f"  Owner: @HATHI02 | Developer: @shadowxdeveloper")
    return "\n".join(lines)


# === UPI TEXT REPORT ===
def generate_upi_text_report(data: dict) -> str:
    """Generate a clean emoji-style text report for UPI lookup."""
    number = data.get("number", "N/A")
    upi_data = data.get("upi_data", {})

    lines = []
    lines.append("💳 UPI Lookup Result")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📞 Number: {number}")
    lines.append("")

    # Handle the actual API format: {success, phone, vpas, details, upi_details, by, owner}
    # Also handle legacy nested formats
    accounts = upi_data.get("accounts", [])
    transactions = upi_data.get("transactions", [])
    vpas = upi_data.get("vpas", [])
    details = upi_data.get("details", [])
    upi_details = upi_data.get("upi_details", [])

    # Top-level scalar fields (phone, success, by, owner, etc.)
    for key, value in upi_data.items():
        if key in ["accounts", "transactions", "vpas", "details", "upi_details", "data"]:
            continue
        if isinstance(value, (dict, list)):
            continue
        if value and str(value) not in ["", "N/A", "None", "false", "true"]:
            # Replace API owner name with our branding
            if key in ["by", "owner"]:
                continue
            emoji_map = {
                "phone": "📞", "num": "📞", "number": "📞",
                "success": "✅", "response_time_ms": "⏱",
            }
            emoji = emoji_map.get(key, "🔹")
            label = key.replace("_", " ").title()
            lines.append(f"{emoji} {label}: {safe_str(value)}")

    # VPA / UPI IDs section
    if vpas:
        lines.append("")
        lines.append("💳 LINKED UPI IDs")
        lines.append("-" * 44)
        for i, vpa in enumerate(vpas[:10], 1):
            if isinstance(vpa, dict):
                lines.append(f"  >> VPA #{i} <<")
                for key, value in vpa.items():
                    if isinstance(value, (dict, list)):
                        continue
                    emoji = "💳" if "vpa" in key.lower() or "upi" in key.lower() else "🔹"
                    lines.append(f"    {emoji} {key.replace('_', ' ').title()}: {safe_str(value)}")
            else:
                lines.append(f"  💳 VPA: {safe_str(vpa)}")
        lines.append("")

    # UPI Details section
    if upi_details:
        lines.append("📊 UPI DETAILS")
        lines.append("-" * 44)
        for i, detail in enumerate(upi_details[:10], 1):
            if isinstance(detail, dict):
                lines.append(f"  >> Detail #{i} <<")
                for key, value in detail.items():
                    if isinstance(value, (dict, list)):
                        continue
                    lines.append(f"    {key.replace('_', ' ').title()}: {safe_str(value)}")
            else:
                lines.append(f"  📋 {safe_str(detail)}")
        lines.append("")

    # Details / accounts section
    if details:
        lines.append("🔍 ACCOUNT DETAILS")
        lines.append("-" * 44)
        for i, acc in enumerate(details[:10], 1):
            if isinstance(acc, dict):
                lines.append(f"  >> Account #{i} <<")
                for key, value in acc.items():
                    if isinstance(value, (dict, list)):
                        continue
                    lines.append(f"    {key.replace('_', ' ').title()}: {safe_str(value)}")
            else:
                lines.append(f"    Detail: {safe_str(acc)}")
        lines.append("")

    # Legacy accounts format
    if accounts and not details:
        lines.append("💳 LINKED UPI ACCOUNTS")
        lines.append("-" * 44)
        for i, acc in enumerate(accounts[:10], 1):
            if isinstance(acc, dict):
                lines.append(f"  >> Account #{i} <<")
                for key, value in acc.items():
                    if isinstance(value, (dict, list)):
                        continue
                    lines.append(f"    {key.replace('_', ' ').title()}: {safe_str(value)}")
            else:
                lines.append(f"    UPI ID: {safe_str(acc)}")
        lines.append("")

    # Transactions
    if transactions:
        lines.append("📊 TRANSACTION HISTORY")
        lines.append("-" * 44)
        for i, tx in enumerate(transactions[:10], 1):
            if isinstance(tx, dict):
                lines.append(f"  >> Transaction #{i} <<")
                for key, value in tx.items():
                    if isinstance(value, (dict, list)):
                        continue
                    lines.append(f"    {key.replace('_', ' ').title()}: {safe_str(value)}")
            else:
                lines.append(f"    TXN: {safe_str(tx)}")
        lines.append("")

    # Fallback: dump all raw data if nothing was displayed
    has_displayed = any(upi_data.get(k) for k in ["vpas", "details", "upi_details", "accounts", "transactions"])
    has_scalars = any(
        v and str(v) not in ["", "N/A", "None", "false", "true"]
        for k, v in upi_data.items()
        if k not in ["vpas", "details", "upi_details", "accounts", "transactions", "data"] and not isinstance(v, (dict, list))
    )
    if not has_displayed and not has_scalars:
        lines.append("📊 Raw UPI Data")
        lines.append("-" * 44)
        for key, value in upi_data.items():
            if isinstance(value, dict):
                lines.append(f"  {key.replace('_', ' ').title()}:")
                for k2, v2 in value.items():
                    if isinstance(v2, (dict, list)):
                        continue
                    lines.append(f"    {k2.replace('_', ' ').title()}: {safe_str(v2)}")
            elif isinstance(value, list):
                if value:
                    lines.append(f"  {key.replace('_', ' ').title()}: ({len(value)} items)")
            else:
                lines.append(f"  {key.replace('_', ' ').title()}: {safe_str(value)}")
        lines.append("")

    lines.append("⚡ Owner: @HATHI02 | Developer: @shadowxdeveloper")
    return "\n".join(lines)



# === VEHICLE TEXT REPORT ===
def _normalize_vehicle_data(vehicle_data: dict) -> dict:
    """Unwrap nested 'data' key from APIs like vh-num.vercel.app and merge into top level."""
    if isinstance(vehicle_data.get("data"), dict):
        merged = dict(vehicle_data)
        for k, v in vehicle_data["data"].items():
            if k not in merged or merged[k] is None or merged[k] == "":
                merged[k] = v
        return merged
    return vehicle_data


def generate_vehicle_text_report(data: dict) -> str:
    """Generate a clean emoji-style text report for vehicle lookup matching the screenshot format."""
    plate = data.get("vehicle_plate", "N/A")
    vehicle_data = _normalize_vehicle_data(data.get("vehicle_data", {}))

    # _normalize_vehicle_data already merges nested 'data' key into top level
    vd = vehicle_data

    lines = []
    lines.append("📋 VEHICLE SEARCH REPORT")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🔢 Plate: {plate}")
    lines.append("")

    has_any_data = False

    # === OWNER DETAILS ===
    owner_name = vd.get("owner") or vd.get("ownerName")
    address = vd.get("presentAddress") or vd.get("permAddress") or vd.get("address")
    mobile = vd.get("mobileNumber")
    father = vd.get("ownerFatherName") or vd.get("fatherName")

    if owner_name or address:
        has_any_data = True
        lines.append('👤 OWNER DETAILS ”')
        lines.append("-" * 40)
        if owner_name:
            lines.append(f"👤 Owner Name: {safe_str(owner_name)}")
        if father:
            lines.append(f"👨 Father Name: {safe_str(father)}")
        if address:
            lines.append(f"🏠 Address: {safe_str(address)}")
        if mobile:
            lines.append(f"📞 Mobile: {safe_str(mobile)}")
        lines.append("")

    # === VEHICLE DETAILS ===
    reg_no = vd.get("regNo") or vd.get("reg_no") or plate
    model = vd.get("vehicle") or vd.get("model")
    manufacturer = vd.get("manufacturer") or vd.get("maker")
    variant = vd.get("variant")
    fuel_type = vd.get("fuelType") or vd.get("fuel_type")
    vehicle_class = vd.get("vehicleClass") or vd.get("class")
    reg_date = vd.get("regDate") or vd.get("reg_date")
    reg_authority = vd.get("regAuthority") or vd.get("registeredAt")
    rto_code = vd.get("rtoCode") or vd.get("rto_code")
    mfg_year = vd.get("manufacturerYear") or vd.get("mfg_year")
    mfg_month = vd.get("manufacturerMonthYear")
    color = vd.get("color")
    seat_capacity = vd.get("seatCapacity")
    vehicle_type = vd.get("vehicleType")
    is_commercial = vd.get("isCommercial")
    insurance_expired = vd.get("insuranceExpired")

    lines.append('🚗 VEHICLE DETAILS ”')
    lines.append("-" * 40)
    lines.append(f"🔢 Vehicle No: {safe_str(reg_no)}")
    has_any_data = True

    # RC Status
    if insurance_expired is not None:
        rc_status = "INACTIVE" if insurance_expired else "ACTIVE"
        status_icon = "🔴" if insurance_expired else "🟢"
        lines.append(f"{status_icon} RC Status: {rc_status}")

    # Model
    model_str = safe_str(model)
    if variant:
        model_str += f" ({safe_str(variant)})"
    if manufacturer:
        model_str = f"{safe_str(manufacturer)} {model_str}"
    lines.append(f"🚗 Model: {model_str}")

    if reg_date:
        lines.append(f"📅 Reg Date: {safe_str(reg_date)}")
    if reg_authority:
        lines.append(f"🏛 Registered At: {safe_str(reg_authority)}")
    elif rto_code:
        lines.append(f"🏛 RTO: {safe_str(rto_code)}")
    if fuel_type:
        lines.append(f"⛽ Fuel Type: {safe_str(fuel_type)}")
    if mfg_year:
        mfg_str = safe_str(mfg_year)
        if mfg_month:
            mfg_str = f"{safe_str(mfg_month)}"
        lines.append(f"📅 Mfg Date: {mfg_str}")
    if color:
        lines.append(f"🎨 Color: {safe_str(color)}")
    if vehicle_class:
        lines.append(f"🚗 Class: {safe_str(vehicle_class)}")
    if vehicle_type:
        lines.append(f"🏷 Type: {safe_str(vehicle_type)}")
    if is_commercial is not None:
        comm = "Commercial" if is_commercial else "Private"
        lines.append(f"📋 Category: {comm}")
    lines.append("")

    # === INSURANCE & FINANCE ===
    ins_co = vd.get("insuranceCompanyName") or vd.get("insurer")
    ins_policy = vd.get("insurancePolicyNumber") or vd.get("policy")
    ins_upto = vd.get("insuranceUpto") or vd.get("valid_upto")
    financer = vd.get("financerName") or vd.get("financier")

    if ins_co or ins_policy or ins_upto or financer:
        has_any_data = True
        lines.append('🛡 INSURANCE & FINANCE ”')
        lines.append("-" * 40)
        if ins_co:
            lines.append(f"🛡 Insurance Co: {safe_str(ins_co)}")
        if ins_policy:
            lines.append(f"📋 Policy No: {safe_str(ins_policy)}")
        if ins_upto:
            lines.append(f"📅 Insurance Valid: {safe_str(ins_upto)}")
        if financer:
            lines.append(f"💰 Financer: {safe_str(financer)}")
        lines.append("")

    # === VALIDITY & TAX ===
    pucc_no = vd.get("puccNumber") or vd.get("pucc_no")
    pucc_upto = vd.get("puccValidUpto") or vd.get("pucc_upto")
    fitness_upto = vd.get("fitnessUpto") or vd.get("fitness_upto")
    tax_upto = vd.get("mvTaxUpto") or vd.get("tax_upto")

    if pucc_no or pucc_upto or fitness_upto or tax_upto:
        has_any_data = True
        lines.append('📋 VALIDITY & TAX ”')
        lines.append("-" * 40)
        if pucc_no:
            lines.append(f"📄 PUCC No: {safe_str(pucc_no)}")
        if pucc_upto:
            lines.append(f"📅 PUCC Upto: {safe_str(pucc_upto)}")
        if fitness_upto:
            lines.append(f"📅 Fitness Upto: {safe_str(fitness_upto)}")
        if tax_upto:
            lines.append(f"📅 Tax Upto: {safe_str(tax_upto)}")
        lines.append("")

    # === TECHNICAL DETAILS ===
    chassis = vd.get("chassisNumber") or vd.get("chassis")
    engine = vd.get("engineNumber") or vd.get("engine")
    cc = vd.get("cubicCapacity") or vd.get("engine_cc")
    seats = vd.get("seatCapacity") or seat_capacity

    if chassis or engine or cc or seats:
        has_any_data = True
        lines.append('⚙️ TECHNICAL DETAILS ”')
        lines.append("-" * 40)
        if chassis:
            lines.append(f"⚙️ Chassis No: {safe_str(chassis)}")
        if engine:
            lines.append(f"⚙️ Engine No: {safe_str(engine)}")
        if vehicle_class:
            lines.append(f"🚗 Category: {safe_str(vehicle_class)}")
        if cc:
            lines.append(f"⚙️ Engine CC: {safe_str(cc)} cc")
        if seats:
            lines.append(f"💺 Seating: {safe_str(seats)} Seats")
        lines.append("")

    if not has_any_data:
        # Fallback: dump all raw data
        lines.append("📊 Raw Data")
        lines.append("-" * 40)
        for key, value in vd.items():
            if key == "data":
                continue
            if isinstance(value, dict):
                continue
            elif isinstance(value, list):
                if value:
                    lines.append(f"  {key.replace('_', ' ').title()}: ({len(value)} items)")
            else:
                lines.append(f"  {key.replace('_', ' ').title()}: {safe_str(value)}")
        lines.append("")

    lines.append("⚡ Owner: @HATHI02 | Developer: @shadowxdeveloper")
    return "\n".join(lines)



# === NUMLEAK PDF ===

class NumleakReportPDF(OSINTReportPDF):
    """PDF for numleak-only reports."""

    def header(self):
        self._draw_dark_bg()
        self.set_fill_color(*NEON_RED)
        self.rect(0, 0, 210, 3, "F")
        self.set_y(10)
        self.set_font("Courier", "B", 18)
        self.set_text_color(*NEON_RED)
        self.cell(0, 12, "DATA LEAK REPORT", ln=True, align="C")
        self.set_font("Courier", "B", 14)
        self.set_text_color(*NEON_CYAN)
        self.cell(0, 10, "BREACH INTELLIGENCE", ln=True, align="C")
        self.set_draw_color(*NEON_RED)
        self.line(30, self.get_y() + 2, 180, self.get_y() + 2)
        self.ln(8)

    def footer(self):
        self.set_y(-20)
        self.set_fill_color(*NEON_RED)
        self.rect(0, 294, 210, 3, "F")
        self.set_font("Courier", "", 7)
        self.set_text_color(*TEXT_DIM)
        self.cell(0, 5, f"Powered by @{BRAND_NAME} | Data Leak Intelligence", align="C")
        self.ln(4)
        self.set_text_color(60, 60, 80)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_numleak_pdf(data: dict) -> io.BytesIO:
    """Generate PDF for numleak data."""
    number = data.get("number", "N/A")
    numleak_data = data.get("numleak_data", {})

    pdf = NumleakReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.info_box(f"TARGET: {number}", NEON_RED)
    pdf.ln(2)

    chain = numleak_data.get("chain", {})
    calltracer = numleak_data.get("calltracer", {})

    # Chain / breach source
    if chain:
        pdf.section_header("BREACH SOURCE", NEON_RED)
        pdf.label_value("Title", safe_str(chain.get("title")), value_color=NEON_YELLOW)
        desc = safe_str(chain.get("description", ""))[:120]
        pdf.label_value("Description", desc)
        pdf.ln(2)

        leak_records = chain.get("records", [])
        if leak_records:
            pdf.section_header(f"LEAKED RECORDS ({len(leak_records)} total)", NEON_RED)
            for i, record in enumerate(leak_records[:10], 1):
                pdf.record_header(i, NEON_RED)
                pdf.label_value("Full Name", safe_str(record.get("FullName")), value_color=NEON_GREEN)
                pdf.label_value("Father Name", safe_str(record.get("FatherName")))
                pdf.label_value("Document", safe_str(record.get("DocumentNumber")), value_color=NEON_YELLOW)
                pdf.label_value("Phone", safe_str(record.get("Phone")), value_color=NEON_CYAN)
                if record.get("Phone2"):
                    pdf.label_value("Phone 2", safe_str(record.get("Phone2")))
                if record.get("Phone3"):
                    pdf.label_value("Phone 3", safe_str(record.get("Phone3")))
                pdf.label_value("Address", safe_str(record.get("Adres"))[:80])
                pdf.label_value("Region", safe_str(record.get("Region")))
                pdf.ln(2)

            if len(leak_records) > 10:
                pdf.set_font("Courier", "", 8)
                pdf.set_text_color(*TEXT_DIM)
                pdf.cell(0, 5, f"  ... and {len(leak_records) - 10} more records", ln=True)
                pdf.ln(2)

    # Calltracer
    if calltracer:
        pdf.divider()
        pdf.section_header("CARRIER / SIM INFO", NEON_CYAN)
        pdf.label_value("Number", safe_str(calltracer.get("Number")))
        pdf.label_value("SIM Card", safe_str(calltracer.get("SIM card")), value_color=NEON_GREEN)
        pdf.label_value("Mobile State", safe_str(calltracer.get("Mobile State")))
        pdf.label_value("Connection", safe_str(calltracer.get("Connection")), value_color=NEON_CYAN)
        if calltracer.get("Hometown"):
            pdf.label_value("Hometown", safe_str(calltracer.get("Hometown")))
        if calltracer.get("Language"):
            pdf.label_value("Language", safe_str(calltracer.get("Language")))
        if calltracer.get("IMEI number"):
            pdf.label_value("IMEI", safe_str(calltracer.get("IMEI number")), value_color=NEON_YELLOW)
        if calltracer.get("Tracking History"):
            pdf.label_value("Tracking", safe_str(calltracer.get("Tracking History")), value_color=NEON_YELLOW)
        pdf.ln(2)

    if not chain and not calltracer:
        pdf.section_header("NO DATA", NEON_RED)
        pdf.set_font("Courier", "", 9)
        pdf.set_text_color(*NEON_RED)
        pdf.cell(0, 6, "  No leak or carrier data found for this number.", ln=True)

    pdf.divider()
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(*TEXT_DIM)
    pdf.cell(0, 4, f"  Owner: @HATHI02 | Developer: @shadowxdeveloper", ln=True)

    buffer = io.BytesIO()
    buffer.write(pdf.output())
    buffer.seek(0)
    return buffer


# === UPI PDF ===

class UPIReportPDF(OSINTReportPDF):
    """PDF for UPI lookup reports."""

    def header(self):
        self._draw_dark_bg()
        self.set_fill_color(*NEON_PURPLE)
        self.rect(0, 0, 210, 3, "F")
        self.set_y(10)
        self.set_font("Courier", "B", 18)
        self.set_text_color(*NEON_PURPLE)
        self.cell(0, 12, "UPI INTEL REPORT", ln=True, align="C")
        self.set_font("Courier", "B", 14)
        self.set_text_color(*NEON_CYAN)
        self.cell(0, 10, "PAYMENT INTELLIGENCE", ln=True, align="C")
        self.set_draw_color(*NEON_PURPLE)
        self.line(30, self.get_y() + 2, 180, self.get_y() + 2)
        self.ln(8)

    def footer(self):
        self.set_y(-20)
        self.set_fill_color(*NEON_PURPLE)
        self.rect(0, 294, 210, 3, "F")
        self.set_font("Courier", "", 7)
        self.set_text_color(*TEXT_DIM)
        self.cell(0, 5, f"Powered by @{BRAND_NAME} | UPI Intelligence", align="C")
        self.ln(4)
        self.set_text_color(60, 60, 80)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_upi_pdf(data: dict) -> io.BytesIO:
    """Generate PDF for UPI lookup data."""
    number = data.get("number", "N/A")
    upi_data = data.get("upi_data", {})

    pdf = UPIReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.info_box(f"TARGET: {number}", NEON_PURPLE)
    pdf.ln(2)

    # Handle different response formats
    accounts = upi_data.get("data", {}).get("accounts", []) if isinstance(upi_data.get("data"), dict) else []
    transactions = upi_data.get("data", {}).get("transactions", []) if isinstance(upi_data.get("data"), dict) else []
    
    if not accounts and not transactions:
        accounts = upi_data.get("accounts", [])
        transactions = upi_data.get("transactions", [])

    # Top-level fields
    pdf.section_header("UPI DETAILS", NEON_PURPLE)
    for key, value in upi_data.items():
        if key in ["accounts", "transactions", "data"]:
            continue
        if isinstance(value, (dict, list)):
            continue
        pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=NEON_CYAN)

    nested = upi_data.get("data", {})
    if isinstance(nested, dict):
        for key, value in nested.items():
            if key in ["accounts", "transactions"]:
                continue
            if isinstance(value, (dict, list)):
                continue
            pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=NEON_CYAN)
    pdf.ln(2)
    pdf.divider()

    # Accounts
    if accounts:
        pdf.section_header(f"LINKED UPI ACCOUNTS ({len(accounts)})", NEON_GREEN)
        for i, acc in enumerate(accounts[:10], 1):
            pdf.record_header(i, NEON_GREEN)
            if isinstance(acc, dict):
                for key, value in acc.items():
                    if isinstance(value, (dict, list)):
                        continue
                    color = NEON_YELLOW if key.lower() in ["upi_id", "vpa", "id"] else TEXT_WHITE
                    pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)
            else:
                pdf.label_value("UPI ID", safe_str(acc), value_color=NEON_YELLOW)
            pdf.ln(2)

    # Transactions
    if transactions:
        pdf.section_header(f"TRANSACTION HISTORY ({len(transactions)})", NEON_YELLOW)
        for i, tx in enumerate(transactions[:10], 1):
            pdf.record_header(i, NEON_YELLOW)
            if isinstance(tx, dict):
                for key, value in tx.items():
                    if isinstance(value, (dict, list)):
                        continue
                    color = NEON_GREEN if key.lower() in ["amount", "status"] else TEXT_WHITE
                    pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)
            else:
                pdf.label_value("Transaction", safe_str(tx))
            pdf.ln(2)

    if not accounts and not transactions and not upi_data:
        pdf.section_header("NO DATA", NEON_RED)
        pdf.set_font("Courier", "", 9)
        pdf.set_text_color(*NEON_RED)
        pdf.cell(0, 6, "  No UPI data found for this number.", ln=True)

    pdf.divider()
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(*TEXT_DIM)
    pdf.cell(0, 4, f"  Owner: @HATHI02 | Developer: @shadowxdeveloper", ln=True)

    buffer = io.BytesIO()
    buffer.write(pdf.output())
    buffer.seek(0)
    return buffer


# === VEHICLE PDF ===

class VehicleReportPDF(OSINTReportPDF):
    """PDF for vehicle registration reports."""

    def header(self):
        self._draw_dark_bg()
        self.set_fill_color(*NEON_YELLOW)
        self.rect(0, 0, 210, 3, "F")
        self.set_y(10)
        self.set_font("Courier", "B", 18)
        self.set_text_color(*NEON_YELLOW)
        self.cell(0, 12, "VEHICLE REGISTRY", ln=True, align="C")
        self.set_font("Courier", "B", 14)
        self.set_text_color(*NEON_CYAN)
        self.cell(0, 10, "REGISTRATION REPORT", ln=True, align="C")
        self.set_draw_color(*NEON_YELLOW)
        self.line(30, self.get_y() + 2, 180, self.get_y() + 2)
        self.ln(8)

    def footer(self):
        self.set_y(-20)
        self.set_fill_color(*NEON_YELLOW)
        self.rect(0, 294, 210, 3, "F")
        self.set_font("Courier", "", 7)
        self.set_text_color(*TEXT_DIM)
        self.cell(0, 5, f"Powered by @{BRAND_NAME} | Vehicle Intelligence", align="C")
        self.ln(4)
        self.set_text_color(60, 60, 80)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_vehicle_pdf(data: dict) -> io.BytesIO:
    """Generate PDF for vehicle registration data."""
    plate = data.get("vehicle_plate", "N/A")
    vehicle_data = _normalize_vehicle_data(data.get("vehicle_data", {}))

    pdf = VehicleReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.info_box(f"PLATE: {plate}", NEON_YELLOW)
    pdf.ln(2)

    owner = vehicle_data.get("owner", {})
    vehicle = vehicle_data.get("vehicle", {})
    insurance = vehicle_data.get("insurance", {})
    technical = vehicle_data.get("technical", {})

    # Flat API response support (actual API: regNo, owner, vehicle, etc.)
    # Need to check isinstance because normalization may leave owner/vehicle as strings
    if not isinstance(owner, dict) or not isinstance(vehicle, dict):
        if vehicle_data.get("regNo") or vehicle_data.get("owner"):
            owner = {
                "name": vehicle_data.get("owner"),
                "father_name": vehicle_data.get("fatherName"),
                "mobile": vehicle_data.get("mobileNumber"),
                "address": vehicle_data.get("presentAddress") or vehicle_data.get("permAddress"),
            }
            vehicle = {
                "reg_no": vehicle_data.get("regNo"),
                "vehicle": vehicle_data.get("vehicle"),
                "manufacturer": vehicle_data.get("manufacturer"),
                "variant": vehicle_data.get("variant"),
                "fuel_type": vehicle_data.get("fuelType"),
                "color": vehicle_data.get("color"),
                "class": vehicle_data.get("vehicleClass"),
                "mfg_year": vehicle_data.get("manufacturerYear"),
                "reg_date": vehicle_data.get("regDate"),
                "rto_code": vehicle_data.get("rtoCode"),
            }
            insurance = {
                "insurer": vehicle_data.get("insuranceCompanyName"),
                "policy_number": vehicle_data.get("insurancePolicyNumber"),
                "insurance_upto": vehicle_data.get("insuranceUpto"),
            }
            technical = {
                "chassis_no": vehicle_data.get("chassisNumber") or vehicle_data.get("chassis"),
                "engine_no": vehicle_data.get("engineNumber") or vehicle_data.get("engine"),
                "engine_cc": vehicle_data.get("cubicCapacity"),
                "financier": vehicle_data.get("financerName"),
                "tax_upto": vehicle_data.get("mvTaxUpto"),
                "fitness_upto": vehicle_data.get("fitnessUpto"),
            }
    # OWNER section
    if owner:
        pdf.section_header("OWNER DETAILS", NEON_GREEN)
        if isinstance(owner, dict):
            for key, value in owner.items():
                if value:
                    color = NEON_GREEN if key.lower() in ["name", "owner_name"] else TEXT_WHITE
                    pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)
        else:
            pdf.label_value("Owner", safe_str(owner), value_color=NEON_GREEN)
        pdf.ln(2)
        pdf.divider()

    # VEHICLE section
    if vehicle:
        pdf.section_header("VEHICLE DETAILS", NEON_CYAN)
        if isinstance(vehicle, dict):
            for key, value in vehicle.items():
                if value:
                    color = NEON_YELLOW if key.lower() in ["registration_number", "reg_no"] else TEXT_WHITE
                    pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)
        else:
            pdf.label_value("Vehicle", safe_str(vehicle), value_color=NEON_CYAN)
        pdf.ln(2)
        pdf.divider()

    # INSURANCE section
    if insurance:
        pdf.section_header("INSURANCE DETAILS", NEON_PURPLE)
        if isinstance(insurance, dict):
            for key, value in insurance.items():
                if value:
                    color = NEON_YELLOW if key.lower() in ["policy_number"] else TEXT_WHITE
                    pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)
        else:
            pdf.label_value("Insurance", safe_str(insurance), value_color=NEON_PURPLE)
        pdf.ln(2)
        pdf.divider()

    # TECHNICAL section
    if technical:
        pdf.section_header("TECHNICAL DETAILS", NEON_YELLOW)
        if isinstance(technical, dict):
            for key, value in technical.items():
                if value:
                    color = NEON_RED if "chassis" in key.lower() or "engine" in key.lower() else TEXT_WHITE
                    pdf.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)
        else:
            pdf.label_value("Technical", safe_str(technical), value_color=NEON_YELLOW)
        pdf.ln(2)
        pdf.divider()

    # Fallback: print all data (only if no data was displayed via sections above)
    owner_has_data = isinstance(owner, dict) and any(v for v in owner.values() if isinstance(v, str) and v)
    vehicle_has_data = isinstance(vehicle, dict) and any(v for v in vehicle.values() if isinstance(v, str) and v)
    insurance_has_data = isinstance(insurance, dict) and any(v for v in insurance.values() if isinstance(v, str) and v)
    technical_has_data = isinstance(technical, dict) and any(v for v in technical.values() if isinstance(v, str) and v)
    if not owner_has_data and not vehicle_has_data and not insurance_has_data and not technical_has_data:
        pdf.section_header("VEHICLE DATA", NEON_CYAN)
        for key, value in vehicle_data.items():
            if key == "data":
                continue
            if isinstance(value, dict):
                continue
            elif isinstance(value, list):
                pdf.label_value(key.replace("_", " ").title(), f"({len(value)} items)")
            else:
                pdf.label_value(key.replace("_", " ").title(), safe_str(value))
        pdf.ln(2)

    pdf.divider()
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(*TEXT_DIM)
    pdf.cell(0, 4, f"  Owner: @HATHI02 | Developer: @shadowxdeveloper", ln=True)

    buffer = io.BytesIO()
    buffer.write(pdf.output())
    buffer.seek(0)
    return buffer

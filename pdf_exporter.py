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
    pdf.cell(0, 4, f"  Powered by @HATHI02", ln=True)

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
    lines.append(f"  Powered by @HATHI02")
    return "\n".join(lines)


# === UPI TEXT REPORT ===
def generate_upi_text_report(data: dict) -> str:
    """Generate a text report for UPI lookup data."""
    number = data.get("number", "N/A")
    upi_data = data.get("upi_data", {})

    lines = []
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║       UPI INTELLIGENCE REPORT                   ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append(f"  Target Number: {number}")
    lines.append("")

    # Handle different response formats
    # The API may return data in different structures
    accounts = upi_data.get("data", {}).get("accounts", []) if isinstance(upi_data.get("data"), dict) else []
    transactions = upi_data.get("data", {}).get("transactions", []) if isinstance(upi_data.get("data"), dict) else []
    
    # Flat response format
    if not accounts and not transactions:
        accounts = upi_data.get("accounts", [])
        transactions = upi_data.get("transactions", [])

    # Display all key-value pairs from the response
    if upi_data:
        lines.append("=" * 50)
        lines.append("  UPI DETAILS")
        lines.append("-" * 50)
        
        # Print top-level fields
        for key, value in upi_data.items():
            if key in ["accounts", "transactions", "data"]:
                continue
            if isinstance(value, (dict, list)):
                continue
            lines.append(f"  {key.upper():<18}: {safe_str(value)}")
        
        # Print nested data fields
        nested = upi_data.get("data", {})
        if isinstance(nested, dict):
            for key, value in nested.items():
                if key in ["accounts", "transactions"]:
                    continue
                if isinstance(value, (dict, list)):
                    continue
                lines.append(f"  {key.upper():<18}: {safe_str(value)}")
        lines.append("")

    # Accounts
    if accounts:
        lines.append("=" * 50)
        lines.append("  LINKED UPI ACCOUNTS")
        lines.append("-" * 50)
        for i, acc in enumerate(accounts[:10], 1):
            lines.append(f"  ┌── ACCOUNT #{i} ──")
            if isinstance(acc, dict):
                for key, value in acc.items():
                    if isinstance(value, (dict, list)):
                        continue
                    lines.append(f"  │ {key.upper():<16}: {safe_str(value)}")
            else:
                lines.append(f"  │ UPI ID         : {safe_str(acc)}")
            lines.append(f"  └{'─' * 40}")
            lines.append("")

    # Transactions
    if transactions:
        lines.append("=" * 50)
        lines.append("  TRANSACTION HISTORY")
        lines.append("-" * 50)
        for i, tx in enumerate(transactions[:10], 1):
            lines.append(f"  ┌── TRANSACTION #{i} ──")
            if isinstance(tx, dict):
                for key, value in tx.items():
                    if isinstance(value, (dict, list)):
                        continue
                    lines.append(f"  │ {key.upper():<16}: {safe_str(value)}")
            else:
                lines.append(f"  │ TXN            : {safe_str(tx)}")
            lines.append(f"  └{'─' * 40}")
            lines.append("")

    lines.append("═" * 50)
    lines.append(f"  Powered by @HATHI02")
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
    """Generate a text report for vehicle registration data."""
    plate = data.get("vehicle_plate", "N/A")
    vehicle_data = _normalize_vehicle_data(data.get("vehicle_data", {}))

    lines = []
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║       VEHICLE REGISTRATION REPORT               ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append(f"  Plate Number: {plate}")
    lines.append("")

    # Flat API response support (vh-num.vercel.app returns flat keys)
    if vehicle_data.get("regNo") or vehicle_data.get("owner"):
        # Map flat keys to report sections
        lines.append("=" * 50)
        lines.append("  VEHICLE DETAILS")
        lines.append("-" * 50)
        for k, label in [("regNo", "REG NUMBER"), ("vehicle", "VEHICLE"), ("manufacturer", "MANUFACTURER"), ("variant", "VARIANT"), ("fuelType", "FUEL TYPE"), ("vehicleClass", "VEHICLE CLASS"), ("color", "COLOR"), ("manufacturerYear", "MFG YEAR"), ("seatCapacity", "SEAT CAPACITY")]:
            v = vehicle_data.get(k)
            if v: lines.append(f"  {label:<16}: {safe_str(v)}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("  OWNER DETAILS")
        lines.append("-" * 50)
        for k, label in [("owner", "OWNER NAME"), ("fatherName", "FATHER NAME"), ("mobileNumber", "MOBILE"), ("presentAddress", "ADDRESS"), ("permanentAddress", "PERM ADDRESS")]:
            v = vehicle_data.get(k)
            if v: lines.append(f"  {label:<16}: {safe_str(v)}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("  REGISTRATION")
        lines.append("-" * 50)
        for k, label in [("regDate", "REG DATE"), ("regAuthority", "REG AUTHORITY"), ("rtoCode", "RTO CODE"), ("chassisNumber", "CHASSIS NO"), ("engineNumber", "ENGINE NO"), ("cubicCapacity", "ENGINE CC")]:
            v = vehicle_data.get(k)
            # Also check for chassis/engine under different names in nested data
            if not v and k == "chassisNumber": v = vehicle_data.get("chassis")
            if not v and k == "engineNumber": v = vehicle_data.get("engine")
            if v: lines.append(f"  {label:<16}: {safe_str(v)}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("  TAX & INSURANCE")
        lines.append("-" * 50)
        for k, label in [("mvTaxUpto", "TAX UPTO"), ("fitnessUpto", "FITNESS UPTO"), ("insuranceCompanyName", "INSURER"), ("insurancePolicyNumber", "POLICY NO"), ("insuranceUpto", "INSURANCE UPTO")]:
            v = vehicle_data.get(k)
            if v: lines.append(f"  {label:<16}: {safe_str(v)}")
        if vehicle_data.get("financerName"):
            lines.append(f"  {'FINANCER':<16}: {safe_str(vehicle_data.get('financerName'))}")
        lines.append("")
    else:
        # Nested format fallback
        owner = vehicle_data.get("owner", {})
        vehicle = vehicle_data.get("vehicle", {})
        insurance = vehicle_data.get("insurance", {})
        technical = vehicle_data.get("technical", {})
        
        # Try fallback key mapping for flat format deeper in nested
        if not owner and not vehicle:
            owner = {
                "name": vehicle_data.get("owner"),
                "father_name": vehicle_data.get("fatherName"),
                "mobile": vehicle_data.get("mobileNumber"),
                "address": vehicle_data.get("presentAddress") or vehicle_data.get("permAddress"),
            }
            vehicle = {
                "reg_no": vehicle_data.get("regNo") or vehicle_data.get("vehicleNumber"),
                "manufacturer": vehicle_data.get("manufacturer"),
                "model": vehicle_data.get("vehicle"),
                "variant": vehicle_data.get("variant"),
                "fuel_type": vehicle_data.get("fuelType"),
                "class": vehicle_data.get("vehicleClass"),
                "color": vehicle_data.get("color"),
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
                "financier": vehicle_data.get("financerName"),
                "mv_tax_upto": vehicle_data.get("mvTaxUpto"),
                "fitness_upto": vehicle_data.get("fitnessUpto"),
            }

        # OWNER section
        if owner and any(owner.values()):
            lines.append("=" * 50)
            lines.append("  OWNER DETAILS")
            lines.append("-" * 50)
            if isinstance(owner, dict):
                for key, value in owner.items():
                    if value: lines.append(f"  {key.upper():<18}: {safe_str(value)}")
            else:
                lines.append(f"  OWNER           : {safe_str(owner)}")
            lines.append("")

        # VEHICLE section
        if vehicle and any(vehicle.values()):
            lines.append("=" * 50)
            lines.append("  VEHICLE DETAILS")
            lines.append("-" * 50)
            if isinstance(vehicle, dict):
                for key, value in vehicle.items():
                    if value: lines.append(f"  {key.upper():<18}: {safe_str(value)}")
            else:
                lines.append(f"  VEHICLE         : {safe_str(vehicle)}")
            lines.append("")

        # INSURANCE section
        if insurance and any(insurance.values()):
            lines.append("=" * 50)
            lines.append("  INSURANCE DETAILS")
            lines.append("-" * 50)
            if isinstance(insurance, dict):
                for key, value in insurance.items():
                    if value: lines.append(f"  {key.upper():<18}: {safe_str(value)}")
            else:
                lines.append(f"  INSURANCE       : {safe_str(insurance)}")
            lines.append("")

        # TECHNICAL section
        if technical and any(technical.values()):
            lines.append("=" * 50)
            lines.append("  TECHNICAL DETAILS")
            lines.append("-" * 50)
            if isinstance(technical, dict):
                for key, value in technical.items():
                    if value: lines.append(f"  {key.upper():<18}: {safe_str(value)}")
            else:
                lines.append(f"  TECHNICAL       : {safe_str(technical)}")
            lines.append("")

    # If nothing worked, dump all data as fallback
    if not any(vehicle_data.get(k) for k in ["regNo", "owner", "manufacturer", "vehicle"]):
        lines.append("=" * 50)
        lines.append("  VEHICLE DATA")
        lines.append("-" * 50)
        for key, value in vehicle_data.items():
            if isinstance(value, dict) and key != "data":
                lines.append(f"  {key.upper():<18}:")
                for k2, v2 in value.items():
                    if v2: lines.append(f"    {k2.upper():<16}: {safe_str(v2)}")
            elif isinstance(value, list):
                lines.append(f"  {key.upper():<18}: ({len(value)} items)")
            else:
                lines.append(f"  {key.upper():<18}: {safe_str(value)}")
        lines.append("")

    lines.append("═" * 50)
    lines.append(f"  Powered by @HATHI02")
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
    pdf.cell(0, 4, f"  Powered by @HATHI02", ln=True)

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
    pdf.cell(0, 4, f"  Powered by @HATHI02", ln=True)

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
    pdf.cell(0, 4, f"  Powered by @HATHI02", ln=True)

    buffer = io.BytesIO()
    buffer.write(pdf.output())
    buffer.seek(0)
    return buffer

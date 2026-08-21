"""
HathixShadow OSINT Bot - PDF Report Generator
Dark hacker-themed PDF with colored sections for all services.
"""

import io
import os
import re
from fpdf import FPDF

try:
    from config import BRAND_NAME, BRAND_TAGLINE, DEVELOPER
except ImportError:
    BRAND_NAME = "HathixShadow"
    BRAND_TAGLINE = "OSINT Bot"
    DEVELOPER = "@shadowxdeveloper"


def escape_html(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# Dark hacker color palette
DARK_BG = (18, 18, 24)
SECTION_BG = (28, 28, 40)
NEON_GREEN = (0, 255, 65)
NEON_CYAN = (0, 200, 255)
NEON_PURPLE = (180, 80, 255)
NEON_YELLOW = (255, 220, 50)
NEON_RED = (255, 70, 70)
NEON_ORANGE = (255, 150, 50)
TEXT_WHITE = (230, 230, 240)
TEXT_GRAY = (140, 140, 160)
TEXT_DIM = (80, 80, 100)
DIVIDER_COLOR = (45, 45, 65)

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002B50\U00002764\U0000FE0F\U0000203C\U00002049\U000020A0-\U000020CF"
    "]+", flags=re.UNICODE
)


def safe_str(val, default="N/A") -> str:
    if val is None or val == "":
        return default
    result = str(val)
    result = EMOJI_PATTERN.sub("", result)
    return result if result else default


class OSINTReportPDF(FPDF):
    def __init__(self, title="OSINT REPORT", subtitle="INTELLIGENCE REPORT", accent_color=None):
        super().__init__()
        self.accent = accent_color or NEON_GREEN
        self._title = title
        self._subtitle = subtitle
        self.set_auto_page_break(auto=True, margin=20)
        self.set_font("Courier", size=9)

    def _draw_dark_bg(self):
        self.set_fill_color(*DARK_BG)
        self.rect(0, 0, 210, 297, "F")

    def header(self):
        self._draw_dark_bg()
        self.set_fill_color(*self.accent)
        self.rect(0, 0, 210, 3, "F")
        self.set_y(10)
        self.set_font("Courier", "B", 18)
        self.set_text_color(*self.accent)
        self.cell(0, 12, self._title, ln=True, align="C")
        self.set_font("Courier", "B", 14)
        self.set_text_color(*NEON_CYAN)
        self.cell(0, 10, self._subtitle, ln=True, align="C")
        self.set_draw_color(*self.accent)
        self.line(30, self.get_y() + 2, 180, self.get_y() + 2)
        self.ln(8)

    def footer(self):
        self.set_y(-20)
        self.set_fill_color(*self.accent)
        self.rect(0, 294, 210, 3, "F")
        self.set_font("Courier", "", 7)
        self.set_text_color(*TEXT_DIM)
        self.cell(0, 5, f"Powered by {BRAND_NAME} | {DEVELOPER}", align="C")
        self.ln(4)
        self.set_text_color(60, 60, 80)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_header(self, title: str, color=None):
        if color is None:
            color = self.accent
        self.set_fill_color(*SECTION_BG)
        self.rect(10, self.get_y(), 190, 10, "F")
        self.set_fill_color(*color)
        self.rect(10, self.get_y(), 3, 10, "F")
        self.set_font("Courier", "B", 10)
        self.set_text_color(*color)
        self.set_x(16)
        self.cell(0, 10, f"// {title}", ln=True)
        self.set_draw_color(*DIVIDER_COLOR)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def label_value(self, label: str, value: str, label_width: int = 42, value_color=None):
        if value_color is None:
            value_color = TEXT_WHITE
        self.set_font("Courier", "B", 8)
        self.set_text_color(*TEXT_GRAY)
        self.cell(label_width, 5, f"  {label}:", align="L")
        self.set_font("Courier", "", 8)
        self.set_text_color(*value_color)
        v = safe_str(value)
        if len(v) > 135:
            v = v[:135] + "..."
        self.cell(0, 5, v, ln=True)

    def record_header(self, num: int, color=None):
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
        y = self.get_y()
        self.set_draw_color(*DIVIDER_COLOR)
        self.line(12, y, 198, y)
        self.ln(4)

    def info_box(self, text: str, color=None):
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

    def dump_dict(self, data: dict, skip_keys=None):
        skip_keys = skip_keys or []
        for key, value in data.items():
            if key in skip_keys:
                continue
            if isinstance(value, dict):
                self.section_header(key.replace("_", " ").upper(), NEON_CYAN)
                self.dump_dict(value)
            elif isinstance(value, list):
                if value:
                    self.section_header(f"{key.replace('_', ' ').upper()} ({len(value)})", NEON_YELLOW)
                    for i, item in enumerate(value[:10], 1):
                        if isinstance(item, dict):
                            self.record_header(i, NEON_YELLOW)
                            self.dump_dict(item)
                        else:
                            self.label_value(f"Item {i}", safe_str(item))
            else:
                color = NEON_GREEN if "name" in key.lower() else NEON_CYAN if "id" in key.lower() or "number" in key.lower() else TEXT_WHITE
                self.label_value(key.replace("_", " ").title(), safe_str(value), value_color=color)


def generate_service_pdf(data: dict, service_name: str, query: str) -> io.BytesIO:
    accent_map = {
        "ip_info": NEON_CYAN,
        "num_info": NEON_GREEN,
        "name_info": NEON_PURPLE,
        "vehicle_full": NEON_YELLOW,
        "vehicle_parivahan": NEON_ORANGE,
        "hotx": NEON_RED,
        "aadhaar_family": NEON_PURPLE,
    }
    title_map = {
        "ip_info": "IP INTEL REPORT",
        "num_info": "NUMBER INTEL REPORT",
        "name_info": "NAME INTEL REPORT",
        "vehicle_full": "VEHICLE REGISTRY",
        "vehicle_parivahan": "M-PARIVAHAN REPORT",
        "hotx": "PHONE INTEL REPORT",
        "aadhaar_family": "AADHAAR FAMILY REPORT",
    }
    subtitle_map = {
        "ip_info": "INTERNET PROTOCOL ANALYSIS",
        "num_info": "TELECOM INTELLIGENCE",
        "name_info": "IDENTITY INTELLIGENCE",
        "vehicle_full": "VEHICLE REGISTRATION",
        "vehicle_parivahan": "GOVT VEHICLE DATABASE",
        "hotx": "DEEP PHONE LOOKUP",
        "aadhaar_family": "FAMILY TRACE REPORT",
    }

    accent = accent_map.get(service_name, NEON_GREEN)
    title = title_map.get(service_name, "OSINT REPORT")
    subtitle = subtitle_map.get(service_name, "INTELLIGENCE REPORT")

    pdf = OSINTReportPDF(title=title, subtitle=subtitle, accent_color=accent)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.info_box(f"TARGET: {query}", accent)
    pdf.ln(2)

    api_data = data.get("data", data)
    if isinstance(api_data, dict):
        pdf.section_header("RAW DATA", accent)
        pdf.dump_dict(api_data)

    pdf.divider()
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(*TEXT_DIM)
    pdf.cell(0, 4, f"  {BRAND_NAME} | {DEVELOPER}", ln=True)

    buffer = io.BytesIO()
    buffer.write(pdf.output())
    buffer.seek(0)
    return buffer


# Text formatters for each service

SERVICE_EMOJIS = {
    "ip_info": "🌐",
    "num_info": "📱",
    "name_info": "👤",
    "vehicle_full": "🚗",
    "vehicle_parivahan": "🏛",
    "hotx": "📞",
    "aadhaar_family": "👨‍👩‍👧",
}

SERVICE_TITLES = {
    "ip_info": "IP ADDRESS INTEL",
    "num_info": "PHONE NUMBER INTEL",
    "name_info": "IDENTITY INTEL",
    "vehicle_full": "VEHICLE REGISTRY",
    "vehicle_parivahan": "M-PARIVAHAN REPORT",
    "hotx": "DEEP PHONE INTEL",
    "aadhaar_family": "AADHAAR FAMILY TRACE",
}

FIELD_LABELS = {
    "ip": "IP Address",
    "country": "Country",
    "countryCode": "Country Code",
    "region": "Region",
    "regionName": "Region Name",
    "city": "City",
    "zip": "ZIP Code",
    "lat": "Latitude",
    "lon": "Longitude",
    "timezone": "Timezone",
    "isp": "ISP",
    "org": "Organization",
    "as": "AS Number",
    "asname": "AS Name",
    "mobile": "Mobile",
    "proxy": "Proxy",
    "hosting": "Hosting",
    "query": "Query",
    "number": "Number",
    "name": "Name",
    "operator": "Operator",
    "state": "State",
    "country_name": "Country",
    "carrier": "Carrier",
    "type": "Type",
    "owner_name": "Owner Name",
    "father_name": "Father Name",
    "address": "Address",
    "village": "Village",
    "district": "District",
    "registration_number": "Registration No",
    "owner": "Owner",
    "vehicle_class": "Vehicle Class",
    "fuel_type": "Fuel Type",
    "maker_model": "Maker Model",
    "insurance_upto": "Insurance Upto",
    "fitness_upto": "Fitness Upto",
    "tax_upto": "Tax Upto",
    "pucc_upto": "PUC Upto",
    "rc_status": "RC Status",
    "engine_number": "Engine No",
    "chassis_number": "Chassis No",
    "engine_cc": "Engine CC",
    "seating_capacity": "Seating",
    "standing_capacity": "Standing",
    "wheel_base": "Wheel Base",
    "unladen_weight": "Unladen Weight",
    "gross_weight": "Gross Weight",
    "color": "Color",
    "norms_type": "Norms Type",
    "status": "Status",
    "data": "Data",
    "success": "Success",
}


def _fmt_value(val, key=""):
    if val is None or val == "":
        return "—"
    s = str(val).strip()
    if not s:
        return "—"
    if key in ("mobile", "proxy", "hosting"):
        return "Yes" if s.lower() in ("true", "1", "yes") else "No"
    return s


def _fmt_field(key, val):
    label = FIELD_LABELS.get(key, key.replace("_", " ").title())
    v = _fmt_value(val, key)
    return f"  <b>{label}:</b> {escape_html(v)}"


def _fmt_dict_lines(data: dict, indent: int = 1, skip_keys=None) -> list:
    lines = []
    skip_keys = skip_keys or {"success", "status"}
    for key, value in data.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict):
            lines.append(f"{'  ' * indent}<b>┌ {key.replace('_', ' ').upper()}</b>")
            lines.extend(_fmt_dict_lines(value, indent + 1, skip_keys))
        elif isinstance(value, list):
            if value:
                lines.append(f"{'  ' * indent}<b>┌ {key.replace('_', ' ').upper()} ({len(value)})</b>")
                for i, item in enumerate(value[:8], 1):
                    if isinstance(item, dict):
                        lines.append(f"{'  ' * (indent+1)}<b>── Record {i} ──</b>")
                        lines.extend(_fmt_dict_lines(item, indent + 2, skip_keys))
                    else:
                        lines.append(f"{'  ' * (indent+1)}{i}. {_fmt_value(item)}")
                if len(value) > 8:
                    lines.append(f"{'  ' * (indent+1)}... +{len(value)-8} more")
        else:
            lines.append(f"{'  ' * indent}{_fmt_field(key, value)}")
    return lines


def format_text_report(data: dict, service_name: str, query: str) -> str:
    emoji = SERVICE_EMOJIS.get(service_name, "🔍")
    title = SERVICE_TITLES.get(service_name, "OSINT REPORT")
    api_data = data.get("data", data)

    lines = []

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  {emoji}  <b>{BRAND_NAME} OSINT</b>")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"  <b>{title}</b>")
    lines.append(f"────────────────────────────────")
    lines.append(f"  <b>Target:</b> {escape_html(query)}")
    from datetime import datetime
    lines.append(f"  <b>Time:</b>   {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    lines.append(f"────────────────────────────────")
    lines.append("")

    if isinstance(api_data, dict):
        lines.extend(_fmt_dict_lines(api_data))
    elif isinstance(api_data, list):
        for i, item in enumerate(api_data[:10], 1):
            lines.append(f"  <b>── Record {i} ──</b>")
            if isinstance(item, dict):
                lines.extend(_fmt_dict_lines(item, 1))
            else:
                lines.append(f"    {_fmt_value(item)}")
    else:
        lines.append(f"  {_fmt_value(api_data)}")

    lines.append("")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  <b>{BRAND_NAME}</b> • {escape_html(DEVELOPER)}")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)

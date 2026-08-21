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
    "ip_info": "\U0001F310",
    "num_info": "\U0001F4F1",
    "name_info": "\U0001F464",
    "vehicle_full": "\U0001F697",
    "vehicle_parivahan": "\U0001F3DB",
    "hotx": "\U0001F4DE",
    "aadhaar_family": "\U0001F468\u200D\U0001F469\u200D\U0001F467",
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

FIELD_EMOJIS = {
    "name": "\U0001F464", "fullname": "\U0001F464", "full_name": "\U0001F464", "owner_name": "\U0001F464", "owner": "\U0001F464",
    "father_name": "\U0001F468", "fathername": "\U0001F468",
    "phone": "\U0001F4DE", "phone2": "\U0001F4DE", "phone3": "\U0001F4DE", "number": "\U0001F4DE", "mobile": "\U0001F4DE",
    "mobileoperator": "\U0001F4E1", "operator": "\U0001F4E1", "carrier": "\U0001F4E1",
    "address": "\U0001F4CD", "adres": "\U0001F4CD", "adres2": "\U0001F4CD", "location": "\U0001F4CD",
    "city": "\U0001F3D9", "state": "\U0001F5FA", "region": "\U0001F5FA", "regionname": "\U0001F5FA", "indianstate": "\U0001F5FA",
    "country": "\U0001F30D", "countryname": "\U0001F30D", "countrycode": "\U0001F30D",
    "district": "\U0001F3D8", "village": "\U0001F3D8",
    "pincode": "\U0001F4EE", "zip": "\U0001F4EE", "zipcode": "\U0001F4EE",
    "isp": "\U0001F4E1", "org": "\U0001F3E2", "organization": "\U0001F3E2", "as": "\U0001F4E1", "asname": "\U0001F4E1",
    "latitude": "\U0001F4CD", "lat": "\U0001F4CD", "longitude": "\U0001F4CD", "lon": "\U0001F4CD",
    "timezone": "\U0001F550",
    "registration_number": "\U0001F522", "registrationno": "\U0001F522",
    "vehicle_class": "\U0001F698", "vehicleclass": "\U0001F698",
    "fuel_type": "\u26FD", "fueltype": "\u26FD",
    "maker_model": "\U0001F698", "makemodel": "\U0001F698",
    "insurance_upto": "\U0001F6E1", "insuranceupto": "\U0001F6E1",
    "fitness_upto": "\u2705", "fitnessupto": "\u2705",
    "tax_upto": "\U0001F4B0", "taxupto": "\U0001F4B0",
    "pucc_upto": "\U0001F4CB", "puccupto": "\U0001F4CB",
    "rc_status": "\U0001F4CB", "rcstatus": "\U0001F4CB",
    "engine_number": "\u2699", "engineno": "\u2699", "enginnumber": "\u2699",
    "chassis_number": "\u2699", "chassisno": "\u2699",
    "engine_cc": "\u2699", "enginecc": "\u2699",
    "color": "\U0001F3A8", "colour": "\U0001F3A8",
    "status": "\U0001F4CA", "title": "\U0001F4C4", "source": "\U0001F4C4",
    "query": "\U0001F50D", "developer": "\U0001F4BB",
    "response_time_ms": "\u23F1", "responsetimems": "\u23F1",
    "continent": "\U0001F30D", "continentcode": "\U0001F30D",
    "hostname": "\U0001F310", "loc": "\U0001F4CD",
    "rto": "\U0001F3DB", "rtodata": "\U0001F3DB", "rtoid": "\U0001F3DB", "rtocode": "\U0001F3DB",
    "regno": "\U0001F522", "regauthority": "\U0001F3DB",
    "regdate": "\U0001F4C5", "manufacturermonthyear": "\U0001F4C5", "manufactureryear": "\U0001F4C5",
    "vehicleage": "\U0001F4C5",
    "chassis": "\u2699", "engine": "\u2699",
    "puccnumber": "\U0001F4CB", "puccvalidupto": "\U0001F4CB",
    "insuranvalidupto": "\U0001F6E1",
    "taxvalidupto": "\U0001F4B0",
    "fitnessvalidupto": "\u2705",
}

SKIP_KEYS = {"success", "status", "developer", "response_time_ms", "responsetimems"}


def _fmt_value(val, key=""):
    if val is None or val == "":
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "n/a", ""):
        return None
    return s


def _fmt(key, val):
    v = _fmt_value(val, key)
    if v is None:
        return None
    emoji = FIELD_EMOJIS.get(key.lower(), "\u2502")
    label = key.replace("_", " ").replace("-", " ").title()
    return f"{emoji} {label}: {v}"


def _add(key, val, lines):
    line = _fmt(key, val)
    if line:
        lines.append(f"    {line}")


def _walk(data, lines, depth=0):
    sp = "  " * depth
    for key, value in data.items():
        if key.lower() in SKIP_KEYS:
            continue
        if isinstance(value, dict):
            lines.append(f"{sp}\u2500\u2500 {key.replace('_',' ').upper()}")
            _walk(value, lines, depth + 1)
        elif isinstance(value, list):
            if value:
                for i, item in enumerate(value[:5], 1):
                    if isinstance(item, dict):
                        lines.append(f"{sp}  \u25B6 Record #{i}")
                        _walk(item, lines, depth + 1)
                    else:
                        l = _fmt("item", item)
                        if l:
                            lines.append(f"{sp}    {l}")
        else:
            l = _fmt(key, value)
            if l:
                lines.append(f"{sp}{l}")


# ============================================================
# SERVICE-SPECIFIC FORMATTERS
# ============================================================

def _format_ip(data):
    d = data.get("data", data)
    lines = []
    sources = d.get("data", d) if isinstance(d.get("data"), dict) else d
    if isinstance(sources, dict):
        for source_name, source_data in sources.items():
            if not isinstance(source_data, dict):
                continue
            lines.append(f"")
            lines.append(f"    \u2500\u2500 {escape_html(source_name.upper())} \u2500\u2500")
            for key, val in source_data.items():
                if key.lower() in SKIP_KEYS:
                    continue
                _add(key, val, lines)
    return lines


def _format_numinfo(data):
    d = data.get("data", data)
    result = d.get("result", d) if isinstance(d.get("result"), dict) else d
    inner = result.get("data", result) if isinstance(result.get("data"), dict) else result
    lines = []
    for source_name, source_data in inner.items():
        if not isinstance(source_data, dict):
            continue
        title = source_data.get("title", source_name)
        lines.append(f"")
        lines.append(f"    \u2500\u2500 {escape_html(title.upper())} \u2500\u2500")
        records = source_data.get("records", [])
        if isinstance(records, list):
            for i, rec in enumerate(records[:5], 1):
                if isinstance(rec, dict):
                    lines.append(f"      \u2776 Record #{i}")
                    for k, v in rec.items():
                        _add(k, v, lines)
                else:
                    _add("item", rec, lines)
        elif isinstance(source_data, dict):
            for k, v in source_data.items():
                if k.lower() in ("title",):
                    continue
                _add(k, v, lines)
    return lines


def _format_name(data):
    d = data.get("data", data)
    lines = []
    if isinstance(d, dict):
        for key, value in d.items():
            if key.lower() in SKIP_KEYS:
                continue
            if isinstance(value, list):
                for i, item in enumerate(value[:5], 1):
                    if isinstance(item, dict):
                        lines.append(f"")
                        lines.append(f"    \u2500\u2500 RECORD #{i} \u2500\u2500")
                        for k, v in item.items():
                            _add(k, v, lines)
                    else:
                        _add("item", item, lines)
            elif isinstance(value, dict):
                lines.append(f"")
                lines.append(f"    \u2500\u2500 {key.replace('_',' ').upper()} \u2500\u2500")
                _walk(value, lines, 3)
            else:
                _add(key, value, lines)
    return lines


def _format_vehicle(data):
    d = data.get("data", data)
    resp = d.get("response", d) if isinstance(d.get("response"), dict) else d
    lines = []
    if isinstance(resp, dict):
        for key, val in resp.items():
            _add(key, val, lines)
    return lines


def _format_hotx(data):
    d = data.get("data", data)
    result = d.get("result", d) if isinstance(d.get("result"), dict) else d
    resp = result.get("response", result) if isinstance(result.get("response"), dict) else result
    inner = resp.get("data", resp) if isinstance(resp.get("data"), (dict, list)) else resp
    lines = []
    if isinstance(inner, list):
        for i, item in enumerate(inner[:5], 1):
            if isinstance(item, dict):
                lines.append(f"")
                lines.append(f"    \u2500\u2500 RECORD #{i} \u2500\u2500")
                for k, v in item.items():
                    _add(k, v, lines)
            else:
                _add("item", item, lines)
    elif isinstance(inner, dict):
        for k, v in inner.items():
            if k.lower() in SKIP_KEYS:
                continue
            _add(k, v, lines)
    return lines


def _format_aadhaar(data):
    d = data.get("data", data)
    lines = []
    if isinstance(d, dict):
        for key, value in d.items():
            if key.lower() in SKIP_KEYS:
                continue
            if isinstance(value, list):
                for i, item in enumerate(value[:10], 1):
                    if isinstance(item, dict):
                        lines.append(f"")
                        lines.append(f"    \u2500\u2500 MEMBER #{i} \u2500\u2500")
                        for k, v in item.items():
                            _add(k, v, lines)
                    else:
                        _add("item", item, lines)
            elif isinstance(value, dict):
                lines.append(f"")
                lines.append(f"    \u2500\u2500 {key.replace('_',' ').upper()} \u2500\u2500")
                _walk(value, lines, 3)
            else:
                _add(key, value, lines)
    return lines


def _format_generic(data):
    api_data = data.get("data", data)
    lines = []
    if isinstance(api_data, dict):
        _walk(api_data, lines, 2)
    elif isinstance(api_data, list):
        for i, item in enumerate(api_data[:5], 1):
            if isinstance(item, dict):
                lines.append(f"")
                lines.append(f"    \u2500\u2500 RECORD #{i} \u2500\u2500")
                _walk(item, lines, 3)
            else:
                _add("item", item, lines)
    else:
        _add("result", api_data, lines)
    return lines


FORMATTERS = {
    "ip_info": _format_ip,
    "num_info": _format_numinfo,
    "name_info": _format_name,
    "vehicle_full": _format_vehicle,
    "vehicle_parivahan": _format_vehicle,
    "hotx": _format_hotx,
    "aadhaar_family": _format_aadhaar,
}


def format_text_report(data: dict, service_name: str, query: str) -> str:
    from datetime import datetime
    emoji = SERVICE_EMOJIS.get(service_name, "\U0001F50D")
    title = SERVICE_TITLES.get(service_name, "OSINT REPORT")

    lines = []
    lines.append(f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    lines.append(f"  {emoji}  {BRAND_NAME} OSINT")
    lines.append(f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    lines.append("")
    lines.append(f"  {emoji}  {title}")
    lines.append(f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    lines.append(f"  \U0001F3AF Target: {query}")
    lines.append(f"  \U0001F550 Time: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    lines.append(f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    lines.append("")

    formatter = FORMATTERS.get(service_name, _format_generic)
    result_lines = formatter(data)
    if result_lines:
        lines.extend(result_lines)
    else:
        lines.append("    No data found.")

    lines.append("")
    lines.append(f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    lines.append(f"  {BRAND_NAME} \u2022 {DEVELOPER}")
    lines.append(f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501")
    return "\n".join(lines)

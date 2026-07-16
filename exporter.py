"""
Phone Number OSINT Report Image Exporter
Generates styled PNG images of phone number OSINT reports.
Cross-platform: works on Windows, Linux (Railway), and macOS.
"""

import io
import os
import json
from PIL import Image, ImageDraw, ImageFont

# Load branding from config
try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME = "OSINT Bot"
    BRAND_TAGLINE = "Phone Number OSINT Report"

# Color palette - dark hacker theme
BG_COLOR = (18, 18, 24)
HEADER_BG = (30, 30, 42)
SECTION_BG = (22, 22, 30)
BORDER_COLOR = (50, 50, 70)
TEXT_PRIMARY = (230, 230, 240)
TEXT_SECONDARY = (160, 160, 180)
TEXT_ACCENT = (0, 255, 65)
TEXT_WARN = (255, 200, 50)
TEXT_DANGER = (255, 80, 80)
TEXT_BRIGHT = (100, 200, 255)
DIVIDER_COLOR = (60, 60, 80)
WATERMARK_COLOR = (40, 40, 55)

# Image settings
IMG_WIDTH = 800
PADDING = 40
CONTENT_WIDTH = IMG_WIDTH - (PADDING * 2)

# Load logo path from config
try:
    from config import LOGO_PATH
except ImportError:
    LOGO_PATH = "media/logo.png"

LOGO_SIZE = 80


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get font with cross-platform fallback."""
    search_paths = []

    if bold:
        search_paths.extend([
            "C:/Windows/Fonts/consolab.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ])
    else:
        search_paths.extend([
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ])

    for path in search_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    for name in ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "FreeSans.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _draw_divider(draw: ImageDraw.Draw, y: int, width: int = CONTENT_WIDTH) -> int:
    """Draw a horizontal divider line."""
    x_start = PADDING
    x_end = PADDING + width
    draw.line([(x_start, y), (x_end, y)], fill=DIVIDER_COLOR, width=1)
    return y + 12


def _draw_section_header(draw: ImageDraw.Draw, y: int, title: str,
                         font: ImageFont.FreeTypeFont) -> int:
    """Draw a section header with background."""
    bbox = draw.textbbox((0, 0), title, font=font)
    header_height = bbox[3] - bbox[1] + 16
    draw.rectangle(
        [PADDING, y, PADDING + CONTENT_WIDTH, y + header_height],
        fill=HEADER_BG
    )
    draw.text((PADDING + 10, y + 6), title, font=font, fill=TEXT_ACCENT)
    return y + header_height + 8


def _format_number(n) -> str:
    """Format a number with commas."""
    if n is None:
        return "0"
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)


def _safe(val, default="N/A") -> str:
    """Safely convert value to string."""
    if val is None or val == "":
        return default
    return str(val)


def _calculate_height(data: dict) -> int:
    """Calculate the required image height based on content."""
    height = PADDING
    height += 60  # Title
    height += 20  # Spacer

    lookup_type = data.get("lookup_type", "numleak")

    if lookup_type == "vehicle":
        vehicle_data = data.get("vehicle_data", {})
        height += 40  # Target section
        height += 30 * 8  # Owner + vehicle fields
        height += 40  # Insurance section
        height += 30 * 4
        height += 40  # Technical section
        height += 30 * 4
    elif lookup_type in ("upi", "numtoupi"):
        upi_data = data.get("upi_data", {})
        height += 40  # Target section
        height += 30 * 6  # Top-level fields
        accounts = upi_data.get("accounts", [])
        if accounts:
            height += 40
            height += 30 * min(len(accounts), 5) * 4
        transactions = upi_data.get("transactions", [])
        if transactions:
            height += 40
            height += 30 * min(len(transactions), 5) * 4
    else:
        # numleak format (default)
        numleak_data = data.get("numleak_data", {})
        height += 40  # Phone number info section
        height += 30 * 4
        chain = numleak_data.get("chain", {})
        records = chain.get("records", [])
        if records:
            height += 40
            height += 30 * min(len(records), 3) * 6
            height += 20
        calltracer = numleak_data.get("calltracer", {})
        if calltracer:
            height += 40
            height += 30 * 6
            height += 20

    # Footer + Watermark
    height += 40
    height += 80

    return max(height, 600)


def _render_numleak_section(draw, data, y, font_section, font_label, font_value, font_small):
    """Render numleak data on the image. Returns updated y."""
    numleak_data = data.get("numleak_data", {})
    chain = numleak_data.get("chain", {})
    calltracer = numleak_data.get("calltracer", {})

    if chain:
        y = _draw_section_header(draw, y, "DATA LEAK DETAILS", font_section)
        leak_fields = [
            ("Title", _safe(chain.get("title"))),
            ("Info", _safe(chain.get("description", ""))[:60]),
        ]
        for label, value in leak_fields:
            draw.text((PADDING + 10, y), f"{label}:", font=font_label, fill=TEXT_SECONDARY)
            draw.text((PADDING + 180, y), value, font=font_value, fill=TEXT_PRIMARY)
            y += 28
        y += 10

        leak_records = chain.get("records", [])
        if leak_records:
            for i, record in enumerate(leak_records[:3], 1):
                y += 4
                draw.text((PADDING + 10, y), f"--- Leak Record #{i} ---", font=font_label, fill=TEXT_WARN)
                y += 24
                for label, key in [("Name", "FullName"), ("Father", "FatherName"),
                                   ("Phone", "Phone"), ("Phone 2", "Phone2"),
                                   ("Doc ID", "DocumentNumber"), ("Address", "Adres"),
                                   ("Region", "Region")]:
                    value = record.get(key)
                    if value:
                        val_str = str(value)[:50]
                        draw.text((PADDING + 20, y), f"{label}:", font=font_small, fill=TEXT_SECONDARY)
                        draw.text((PADDING + 120, y), val_str, font=font_small, fill=TEXT_PRIMARY)
                        y += 20
            if len(leak_records) > 3:
                draw.text((PADDING + 10, y), f"... and {len(leak_records) - 3} more records",
                           font=font_small, fill=TEXT_SECONDARY)
                y += 24
        y += 10
        y = _draw_divider(draw, y)

    if calltracer:
        y = _draw_section_header(draw, y, "SIM & DEVICE INFO", font_section)
        for label, key in [("SIM Card", "SIM card"), ("State", "Mobile State"),
                           ("Connection", "Connection"), ("Hometown", "Hometown"),
                           ("Language", "Language"), ("IMEI", "IMEI number")]:
            value = calltracer.get(key)
            if value:
                draw.text((PADDING + 10, y), f"{label}:", font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 28
        y += 10
        y = _draw_divider(draw, y)

    return y


def _render_upi_section(draw, data, y, font_section, font_label, font_value, font_small):
    """Render UPI data on the image. Returns updated y."""
    upi_data = data.get("upi_data", {})

    y = _draw_section_header(draw, y, "UPI DETAILS", font_section)

    # Top-level fields
    for key, value in upi_data.items():
        if key in ("accounts", "transactions", "data"):
            continue
        if isinstance(value, (dict, list)):
            continue
        draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                   font=font_label, fill=TEXT_SECONDARY)
        draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
        y += 26

    # Nested data fields
    nested = upi_data.get("data", {})
    if isinstance(nested, dict):
        for key, value in nested.items():
            if key in ("accounts", "transactions"):
                continue
            if isinstance(value, (dict, list)):
                continue
            draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                       font=font_label, fill=TEXT_SECONDARY)
            draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
            y += 26
    y += 10
    y = _draw_divider(draw, y)

    # Accounts
    accounts = upi_data.get("accounts", [])
    if accounts:
        y = _draw_section_header(draw, y, f"LINKED UPI ACCOUNTS ({len(accounts)})", font_section)
        for i, acc in enumerate(accounts[:5], 1):
            y += 4
            draw.text((PADDING + 10, y), f"--- Account #{i} ---", font=font_label, fill=TEXT_WARN)
            y += 24
            if isinstance(acc, dict):
                for key, value in acc.items():
                    if isinstance(value, (dict, list)):
                        continue
                    draw.text((PADDING + 20, y), f"{key.replace('_', ' ').title()}:",
                               font=font_small, fill=TEXT_SECONDARY)
                    draw.text((PADDING + 160, y), str(value)[:50], font=font_small, fill=TEXT_PRIMARY)
                    y += 20
            else:
                draw.text((PADDING + 20, y), f"UPI ID: {str(acc)[:50]}",
                           font=font_small, fill=TEXT_PRIMARY)
                y += 20
        y += 10
        y = _draw_divider(draw, y)

    # Transactions
    transactions = upi_data.get("transactions", [])
    if transactions:
        y = _draw_section_header(draw, y, f"TRANSACTION HISTORY ({len(transactions)})", font_section)
        for i, tx in enumerate(transactions[:5], 1):
            y += 4
            draw.text((PADDING + 10, y), f"--- TX #{i} ---", font=font_label, fill=TEXT_WARN)
            y += 24
            if isinstance(tx, dict):
                for key, value in tx.items():
                    if isinstance(value, (dict, list)):
                        continue
                    draw.text((PADDING + 20, y), f"{key.replace('_', ' ').title()}:",
                               font=font_small, fill=TEXT_SECONDARY)
                    draw.text((PADDING + 160, y), str(value)[:50], font=font_small, fill=TEXT_PRIMARY)
                    y += 20
            else:
                draw.text((PADDING + 20, y), f"TXN: {str(tx)[:50]}",
                           font=font_small, fill=TEXT_PRIMARY)
                y += 20
        y += 10
        y = _draw_divider(draw, y)

    return y


def _render_vehicle_section(draw, data, y, font_section, font_label, font_value, font_small):
    """Render vehicle data on the image. Returns updated y."""
    vehicle_data = data.get("vehicle_data", {})

    owner = vehicle_data.get("owner", {})
    vehicle = vehicle_data.get("vehicle", {})
    insurance = vehicle_data.get("insurance", {})
    technical = vehicle_data.get("technical", {})

    # Flat response fallback
    if not owner and not vehicle:
        owner = {
            "name": vehicle_data.get("owner_name") or vehicle_data.get("name"),
            "father_name": vehicle_data.get("father_name"),
            "address": vehicle_data.get("owner_address") or vehicle_data.get("address"),
        }
        vehicle = {
            "registration_number": vehicle_data.get("registration_number"),
            "maker": vehicle_data.get("maker"),
            "model": vehicle_data.get("model"),
            "color": vehicle_data.get("color"),
            "fuel_type": vehicle_data.get("fuel_type"),
        }

    if owner and isinstance(owner, dict) and any(v for v in owner.values() if v):
        y = _draw_section_header(draw, y, "OWNER DETAILS", font_section)
        for key, value in owner.items():
            if value:
                draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                           font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 26
        y += 10
        y = _draw_divider(draw, y)

    if vehicle and isinstance(vehicle, dict) and any(v for v in vehicle.values() if v):
        y = _draw_section_header(draw, y, "VEHICLE DETAILS", font_section)
        for key, value in vehicle.items():
            if value:
                draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                           font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 26
        y += 10
        y = _draw_divider(draw, y)

    if insurance and isinstance(insurance, dict) and any(v for v in insurance.values() if v):
        y = _draw_section_header(draw, y, "INSURANCE DETAILS", font_section)
        for key, value in insurance.items():
            if value:
                draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                           font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 26
        y += 10
        y = _draw_divider(draw, y)

    if technical and isinstance(technical, dict) and any(v for v in technical.values() if v):
        y = _draw_section_header(draw, y, "TECHNICAL DETAILS", font_section)
        for key, value in technical.items():
            if value:
                draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                           font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 26
        y += 10
        y = _draw_divider(draw, y)

    # Fallback: print all keys
    if not owner and not vehicle and not insurance and not technical:
        y = _draw_section_header(draw, y, "VEHICLE DATA", font_section)
        for key, value in vehicle_data.items():
            if isinstance(value, dict):
                for k2, v2 in value.items():
                    draw.text((PADDING + 10, y), f"{k2.replace('_', ' ').title()}:",
                               font=font_label, fill=TEXT_SECONDARY)
                    draw.text((PADDING + 180, y), str(v2)[:50], font=font_value, fill=TEXT_PRIMARY)
                    y += 24
            elif isinstance(value, list):
                draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                           font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), f"({len(value)} items)",
                           font=font_value, fill=TEXT_PRIMARY)
                y += 24
            else:
                draw.text((PADDING + 10, y), f"{key.replace('_', ' ').title()}:",
                           font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 24
        y += 10

    return y


def generate_report_image(data: dict) -> io.BytesIO:
    """
    Generate a styled PNG image of the OSINT report.
    Supports numleak, UPI, and vehicle lookup types.
    """
    number = data.get("number", data.get("vehicle_plate", "N/A"))
    lookup_type = data.get("lookup_type", "numleak")

    img_height = _calculate_height(data)

    img = Image.new("RGB", (IMG_WIDTH, img_height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = _get_font(28, bold=True)
    font_section = _get_font(18, bold=True)
    font_label = _get_font(15, bold=True)
    font_value = _get_font(14)
    font_small = _get_font(12)

    y = PADDING

    # === HEADER with optional logo ===
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            aspect = logo.width / logo.height
            new_h = LOGO_SIZE
            new_w = int(new_h * aspect)
            logo = logo.resize((new_w, new_h), Image.LANCZOS)
            logo_x = IMG_WIDTH - PADDING - new_w
            img.paste(logo, (logo_x, y), logo)
        except Exception:
            pass

    # Dynamic title based on lookup type
    titles = {
        "vehicle": "VEHICLE REGISTRATION REPORT",
        "upi": "UPI INTELLIGENCE REPORT",
        "numtoupi": "UPI INTELLIGENCE REPORT",
        "numleak": "DATA LEAK INTELLIGENCE REPORT",
    }
    title = titles.get(lookup_type, "PHONE NUMBER OSINT REPORT")
    draw.text((PADDING, y), title, font=font_title, fill=TEXT_ACCENT)
    bbox = draw.textbbox((0, 0), title, font=font_title)
    y += bbox[3] - bbox[1] + 8

    target_label = "Plate" if lookup_type == "vehicle" else "Target"
    subtitle = f"{target_label}: {number}"
    draw.text((PADDING, y), subtitle, font=font_value, fill=TEXT_SECONDARY)
    y += 30

    y = _draw_divider(draw, y)

    # === TARGET INFO ===
    y = _draw_section_header(draw, y, "TARGET INFO", font_section)
    draw.text((PADDING + 10, y), f"{target_label}:", font=font_label, fill=TEXT_SECONDARY)
    draw.text((PADDING + 180, y), number, font=font_value, fill=TEXT_PRIMARY)
    y += 28
    draw.text((PADDING + 10, y), "Type:", font=font_label, fill=TEXT_SECONDARY)
    draw.text((PADDING + 180, y), lookup_type.upper(), font=font_value, fill=TEXT_PRIMARY)
    y += 28
    y += 10
    y = _draw_divider(draw, y)

    # === LOOKUP TYPE SPECIFIC SECTIONS ===
    if lookup_type == "vehicle":
        y = _render_vehicle_section(draw, data, y, font_section, font_label, font_value, font_small)
    elif lookup_type in ("upi", "numtoupi"):
        y = _render_upi_section(draw, data, y, font_section, font_label, font_value, font_small)
    else:
        y = _render_numleak_section(draw, data, y, font_section, font_label, font_value, font_small)

    # === FOOTER ===
    y += 10

    # === WATERMARK / BRANDING ===
    watermark_y = y + 10
    draw.rectangle(
        [0, watermark_y, IMG_WIDTH, watermark_y + 50],
        fill=WATERMARK_COLOR
    )
    font_brand = _get_font(16, bold=True)
    draw.text(
        (PADDING, watermark_y + 14),
        f"{'=' * 3} @HATHI02 {'=' * 3}",
        font=font_brand, fill=TEXT_ACCENT
    )
    bbox_tag = draw.textbbox((0, 0), BRAND_TAGLINE, font=font_small)
    tag_width = bbox_tag[2] - bbox_tag[0]
    draw.text(
        (IMG_WIDTH - PADDING - tag_width, watermark_y + 18),
        BRAND_TAGLINE,
        font=font_small, fill=TEXT_SECONDARY
    )
    y = watermark_y + 50

    # Trim image to actual content height
    final_height = min(y + PADDING, img_height)
    img = img.crop((0, 0, IMG_WIDTH, final_height))

    # Save to BytesIO
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    return buffer

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

    # Phone number info section
    height += 40
    height += 30 * 4
    height += 20

    # Records section (number data)
    number_data = data.get("number_data", {})
    results = number_data.get("results", [])
    if results:
        height += 40
        height += 30 * min(len(results), 3) * 7  # ~7 fields per record
        height += 20

    # Leak data section
    numleak_data = data.get("numleak_data", {})
    chain = numleak_data.get("chain", {})
    records = chain.get("records", [])
    if records:
        height += 40
        height += 30 * min(len(records), 3) * 6
        height += 20

    # SIM info section
    calltracer = numleak_data.get("calltracer", {})
    if calltracer:
        height += 40
        height += 30 * 6
        height += 20

    # Footer + Watermark
    height += 40
    height += 80

    return max(height, 600)


def generate_report_image(data: dict) -> io.BytesIO:
    """
    Generate a styled PNG image of the Phone Number OSINT report.

    Args:
        data: Combined data dict with number_data and numleak_data.

    Returns:
        io.BytesIO object containing the PNG image.
    """
    number = data.get("number", "N/A")
    number_data = data.get("number_data", {})
    numleak_data = data.get("numleak_data", {})

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
    logo_loaded = False
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            aspect = logo.width / logo.height
            new_h = LOGO_SIZE
            new_w = int(new_h * aspect)
            logo = logo.resize((new_w, new_h), Image.LANCZOS)
            logo_x = IMG_WIDTH - PADDING - new_w
            img.paste(logo, (logo_x, y), logo)
            logo_loaded = True
        except Exception:
            pass

    title = "PHONE NUMBER OSINT REPORT"
    draw.text((PADDING, y), title, font=font_title, fill=TEXT_ACCENT)
    bbox = draw.textbbox((0, 0), title, font=font_title)
    y += bbox[3] - bbox[1] + 8

    subtitle = f"Target: {number}"
    draw.text((PADDING, y), subtitle, font=font_value, fill=TEXT_SECONDARY)
    y += 30

    y = _draw_divider(draw, y)

    # === PHONE NUMBER INFO SECTION ===
    y = _draw_section_header(draw, y, "PHONE NUMBER INFO", font_section)

    total = number_data.get("total", 0)
    results = number_data.get("results", [])

    info_fields = [
        ("Number", number),
        ("Total Records", _format_number(total)),
        ("Status", "DATA FOUND" if results else "NO DATA"),
        ("Source", _safe(number_data.get("by", "Unknown"))),
    ]

    for label, value in info_fields:
        draw.text((PADDING + 10, y), f"{label}:", font=font_label, fill=TEXT_SECONDARY)
        draw.text((PADDING + 180, y), value, font=font_value, fill=TEXT_PRIMARY)
        y += 28

    y += 10
    y = _draw_divider(draw, y)

    # === RECORD DETAILS SECTION ===
    if results:
        y = _draw_section_header(draw, y, "RECORD DETAILS", font_section)

        for i, record in enumerate(results[:3], 1):
            y += 4
            draw.text((PADDING + 10, y), f"--- Record #{i} ---", font=font_label, fill=TEXT_WARN)
            y += 24

            record_fields = [
                ("Name", record.get("name")),
                ("Mobile", record.get("mobile")),
                ("Father", record.get("fname")),
                ("Address", str(record.get("address", ""))[:60]),
                ("Circle", record.get("circle")),
                ("Email", record.get("email")),
                ("Alt Num", record.get("alt")),
            ]

            for label, value in record_fields:
                if value and value != "N/A":
                    val_str = str(value)[:50]
                    draw.text((PADDING + 20, y), f"{label}:", font=font_small, fill=TEXT_SECONDARY)
                    draw.text((PADDING + 120, y), val_str, font=font_small, fill=TEXT_PRIMARY)
                    y += 20

        if len(results) > 3:
            draw.text(
                (PADDING + 10, y),
                f"... and {len(results) - 3} more records",
                font=font_small, fill=TEXT_SECONDARY
            )
            y += 24

        y += 10
        y = _draw_divider(draw, y)

    # === LEAK DATA SECTION ===
    chain = numleak_data.get("chain", {})
    leak_records = chain.get("records", [])

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

        if leak_records:
            for i, record in enumerate(leak_records[:3], 1):
                y += 4
                draw.text((PADDING + 10, y), f"--- Leak Record #{i} ---", font=font_label, fill=TEXT_WARN)
                y += 24

                leak_record_fields = [
                    ("Name", record.get("FullName")),
                    ("Father", record.get("FatherName")),
                    ("Phone", record.get("Phone")),
                    ("Phone 2", record.get("Phone2")),
                    ("Doc ID", record.get("DocumentNumber")),
                    ("Address", str(record.get("Adres", ""))[:60]),
                    ("Region", record.get("Region")),
                ]

                for label, value in leak_record_fields:
                    if value:
                        val_str = str(value)[:50]
                        draw.text((PADDING + 20, y), f"{label}:", font=font_small, fill=TEXT_SECONDARY)
                        draw.text((PADDING + 120, y), val_str, font=font_small, fill=TEXT_PRIMARY)
                        y += 20

            if len(leak_records) > 3:
                draw.text(
                    (PADDING + 10, y),
                    f"... and {len(leak_records) - 3} more records",
                    font=font_small, fill=TEXT_SECONDARY
                )
                y += 24

        y += 10
        y = _draw_divider(draw, y)

    # === SIM & DEVICE INFO ===
    calltracer = numleak_data.get("calltracer", {})
    if calltracer:
        y = _draw_section_header(draw, y, "SIM & DEVICE INFO", font_section)

        sim_fields = [
            ("SIM Card", calltracer.get("SIM card")),
            ("State", calltracer.get("Mobile State")),
            ("Connection", calltracer.get("Connection")),
            ("Hometown", calltracer.get("Hometown")),
            ("Language", calltracer.get("Language")),
            ("IMEI", calltracer.get("IMEI number")),
        ]

        for label, value in sim_fields:
            if value:
                draw.text((PADDING + 10, y), f"{label}:", font=font_label, fill=TEXT_SECONDARY)
                draw.text((PADDING + 180, y), str(value)[:50], font=font_value, fill=TEXT_PRIMARY)
                y += 28

        y += 10
        y = _draw_divider(draw, y)

    # === FOOTER ===
    draw.text(
        (PADDING, y),
        f"Source: {_safe(number_data.get('by', 'Unknown'))} | Channel: {_safe(number_data.get('channel', 'N/A'))}",
        font=font_small, fill=TEXT_SECONDARY
    )
    y += 30

    # === WATERMARK / BRANDING ===
    watermark_y = y + 10
    draw.rectangle(
        [0, watermark_y, IMG_WIDTH, watermark_y + 50],
        fill=WATERMARK_COLOR
    )
    font_brand = _get_font(16, bold=True)
    draw.text(
        (PADDING, watermark_y + 14),
        f"{'=' * 3} {BRAND_NAME} {'=' * 3}",
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

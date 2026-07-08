"""
OSINT Report Image Exporter
Generates styled PNG images of Instagram OSINT reports.
Cross-platform: works on Windows, Linux (Railway), and macOS.
"""

import io
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

# Load branding from config
try:
    from config import BRAND_NAME, BRAND_TAGLINE
except ImportError:
    BRAND_NAME = "OSINT Bot"
    BRAND_TAGLINE = "Instagram Intelligence Report"

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

LOGO_SIZE = 80  # Logo will be resized to this height


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


def _calculate_height(data: dict) -> int:
    """Calculate the required image height based on content."""
    profile = data.get("profile", {})
    osint = data.get("osint", {})

    height = PADDING
    height += 60  # Title
    height += 20  # Spacer

    # Profile section
    height += 40
    height += 30 * 8
    if profile.get("biography"):
        height += 30
    height += 20

    # Stats section
    height += 40
    height += 30 * 5
    height += 20

    # OSINT section
    height += 40
    if osint.get("available") and osint.get("records"):
        for record in osint.get("records", [])[:5]:
            height += 30 * 6
            height += 10
    else:
        height += 30

    # Footer + Watermark
    height += 40
    height += 80  # Extra space for watermark/branding

    return max(height, 600)


def generate_report_image(data: dict) -> io.BytesIO:
    """
    Generate a styled PNG image of the OSINT report with branding watermark.

    Args:
        data: The API response dictionary containing profile and osint data.

    Returns:
        io.BytesIO object containing the PNG image.
    """
    profile = data.get("profile", {})
    osint = data.get("osint", {})
    osint_note = data.get("osint_note", "")

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
            # Resize logo to fit height
            aspect = logo.width / logo.height
            new_h = LOGO_SIZE
            new_w = int(new_h * aspect)
            logo = logo.resize((new_w, new_h), Image.LANCZOS)
            # Paste logo on the right side of the header
            logo_x = IMG_WIDTH - PADDING - new_w
            img.paste(logo, (logo_x, y), logo)
            logo_loaded = True
        except Exception:
            pass

    title = "INSTAGRAM OSINT REPORT"
    draw.text((PADDING, y), title, font=font_title, fill=TEXT_ACCENT)
    bbox = draw.textbbox((0, 0), title, font=font_title)
    y += bbox[3] - bbox[1] + 8

    subtitle = f"Target: @{_safe(profile.get('username', 'unknown'))}"
    draw.text((PADDING, y), subtitle, font=font_value, fill=TEXT_SECONDARY)
    y += 30

    y = _draw_divider(draw, y)

    # === PROFILE SECTION ===
    y = _draw_section_header(draw, y, "PROFILE INFO", font_section)

    fields = [
        ("Username", f"@{_safe(profile.get('username'))}"),
        ("Full Name", _safe(profile.get("full_name"))),
        ("Verified", "Yes" if profile.get("is_verified") else "No"),
        ("Account", "Private" if profile.get("is_private") else "Public"),
    ]

    if profile.get("is_business_account"):
        fields.append(("Type", "Business Account"))
    elif profile.get("is_professional_account"):
        fields.append(("Type", "Professional Account"))
    else:
        fields.append(("Type", "Personal Account"))

    if profile.get("category_name"):
        fields.append(("Category", str(profile["category_name"])))
    if profile.get("business_category_name"):
        fields.append(("Business", str(profile["business_category_name"])))
    if profile.get("external_url"):
        fields.append(("Website", str(profile["external_url"])[:60]))

    for label, value in fields:
        draw.text((PADDING + 10, y), f"{label}:", font=font_label, fill=TEXT_SECONDARY)
        draw.text((PADDING + 180, y), value, font=font_value, fill=TEXT_PRIMARY)
        y += 28

    y += 10
    y = _draw_divider(draw, y)

    # === STATISTICS SECTION ===
    y = _draw_section_header(draw, y, "STATISTICS", font_section)

    stats = [
        ("Followers", _format_number(profile.get("followers", 0))),
        ("Following", _format_number(profile.get("following", 0))),
        ("Posts", _format_number(profile.get("posts", 0))),
    ]

    if profile.get("estimated_creation_year"):
        stats.append(("Created", f"~{profile['estimated_creation_year']}"))
    if profile.get("id"):
        stats.append(("Account ID", str(profile["id"])))

    for label, value in stats:
        draw.text((PADDING + 10, y), f"{label}:", font=font_label, fill=TEXT_SECONDARY)
        draw.text((PADDING + 180, y), value, font=font_value, fill=TEXT_BRIGHT)
        y += 28

    y += 10
    y = _draw_divider(draw, y)

    # === OSINT SECTION ===
    y = _draw_section_header(draw, y, "OSINT LEAKED DATA", font_section)

    if osint.get("available") and osint.get("records"):
        record_count = len(osint["records"])
        draw.text(
            (PADDING + 10, y),
            f"Status: Data Available ({record_count} records)",
            font=font_value, fill=TEXT_ACCENT
        )
        y += 28

        for i, record in enumerate(osint["records"][:5], 1):
            y += 4
            draw.text((PADDING + 10, y), f"--- Record #{i} ---", font=font_label, fill=TEXT_WARN)
            y += 24

            record_fields = [
                ("ID", record.get("id")),
                ("Username", record.get("username")),
                ("Name", record.get("name")),
                ("Email", record.get("email")),
                ("Phone", record.get("phone")),
                ("Address", record.get("address")),
            ]

            for label, value in record_fields:
                if value:
                    val_str = str(value)[:50]
                    draw.text((PADDING + 20, y), f"{label}:", font=font_small, fill=TEXT_SECONDARY)
                    draw.text((PADDING + 120, y), val_str, font=font_small, fill=TEXT_PRIMARY)
                    y += 22
    else:
        draw.text(
            (PADDING + 10, y),
            "Status: No leaked data found",
            font=font_value, fill=TEXT_DANGER
        )
        y += 28
        if osint_note:
            draw.text((PADDING + 10, y), f"Note: {osint_note}", font=font_small, fill=TEXT_SECONDARY)
            y += 24

    y += 10
    y = _draw_divider(draw, y)

    # === FOOTER ===
    draw.text(
        (PADDING, y),
        f"Source: {_safe(data.get('by', 'Unknown'))} | Cached: {'Yes' if data.get('cached') else 'No'} | {_safe(data.get('cached_at', 'N/A'))[:19]}",
        font=font_small, fill=TEXT_SECONDARY
    )
    y += 30

    # === WATERMARK / BRANDING ===
    # Draw a subtle branded bar at the bottom
    watermark_y = y + 10
    draw.rectangle(
        [0, watermark_y, IMG_WIDTH, watermark_y + 50],
        fill=WATERMARK_COLOR
    )
    # Left: Brand name
    font_brand = _get_font(16, bold=True)
    draw.text(
        (PADDING, watermark_y + 14),
        f"{'=' * 3} {BRAND_NAME} {'=' * 3}",
        font=font_brand, fill=TEXT_ACCENT
    )
    # Right: Tagline
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


def _safe(val, default="N/A") -> str:
    """Safely convert value to string."""
    if val is None or val == "":
        return default
    return str(val)

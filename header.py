"""
Header Image Generator for HathixShadow OSINT Bot.
Generates branded welcome images for the /start command.
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont

# Colors
BG_COLOR = (15, 15, 25)
ACCENT_PURPLE = (128, 0, 255)
TEXT_WHITE = (240, 240, 250)
TEXT_GRAY = (150, 150, 170)

# Image dimensions
WIDTH = 800
HEIGHT = 300


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get font with cross-platform fallback."""
    search_paths = []
    if bold:
        search_paths.extend([
            "C:/Windows/Fonts/consolab.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ])
    else:
        search_paths.extend([
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ])

    for path in search_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_header_image(brand_name: str = "Hathix Shadow",
                          tagline: str = "Instagram Intelligence Report",
                          logo_path: str = "media/logo.png",
                          credits: int = 0,
                          is_new: bool = False) -> io.BytesIO:
    """
    Generate a branded header image for the /start command.

    Args:
        brand_name: The bot brand name.
        tagline: Subtitle text.
        logo_path: Path to logo image.
        credits: User's current credits.
        is_new: Whether this is a new user.

    Returns:
        io.BytesIO object containing the PNG image.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = _get_font(36, bold=True)
    font_tagline = _get_font(16)
    font_small = _get_font(14, bold=True)

    # Draw accent line at top
    draw.rectangle([0, 0, WIDTH, 4], fill=ACCENT_PURPLE)

    # Load and paste logo if available
    logo_x = 40
    logo_y = 50
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_size = 120
            aspect = logo.width / logo.height
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            img.paste(logo, (logo_x, logo_y), logo)
            text_x = logo_x + logo_size + 30
        except Exception:
            text_x = logo_x
    else:
        text_x = logo_x

    # Brand name
    y = 60
    draw.text((text_x, y), brand_name, font=font_title, fill=TEXT_WHITE)

    # Tagline
    y += 45
    draw.text((text_x, y), tagline, font=font_tagline, fill=TEXT_GRAY)

    # Divider line
    y += 30
    draw.line([(text_x, y), (WIDTH - 40, y)], fill=ACCENT_PURPLE, width=2)

    # Credits info
    y += 20
    if is_new:
        draw.text((text_x, y), "Welcome! You received 3 FREE credits!", font=font_small, fill=ACCENT_PURPLE)
    else:
        draw.text((text_x, y), f"Your Balance: {credits} credits", font=font_small, fill=ACCENT_PURPLE)

    # Bottom accent line
    draw.rectangle([0, HEIGHT - 4, WIDTH, HEIGHT], fill=ACCENT_PURPLE)

    # Save to BytesIO
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer

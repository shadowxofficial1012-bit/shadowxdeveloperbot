"""
HathixShadow OSINT Bot - QR Payment System
Generates unique single-use QR codes with exact UPI amount.
"""

import io
import secrets
import string
import qrcode
from qrcode.image.pil import PilImage
from PIL import Image, ImageDraw, ImageFont
from config import UPI_ID, UPI_NAME, BRAND_NAME


def _generate_token(length=16):
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_upi_qr(package_key, amount, label=None):
    token = _generate_token()
    upi_url = (
        f"upi://pay?pa={UPI_ID}"
        f"&pn={UPI_NAME}"
        f"&am={amount}"
        f"&cu=INR"
        f"&tn={token}"
    )
    if label:
        upi_url += f"&tn={token}%20{label.replace(' ', '%20')}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    return qr_img, token


def generate_qr_with_text(package_key, amount, package_label, upi_id=None):
    if upi_id is None:
        upi_id = UPI_ID

    qr_img, token = generate_upi_qr(package_key, amount, package_label)
    qr_w, qr_h = qr_img.size

    canvas_w = max(qr_w + 60, 400)
    qr_y_start = 80
    text_block_h = 200
    canvas_h = qr_y_start + qr_h + text_block_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), (18, 18, 24))
    draw = ImageDraw.Draw(canvas)

    try:
        font_large = ImageFont.truetype("arial.ttf", 22)
        font_medium = ImageFont.truetype("arial.ttf", 16)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except (OSError, IOError):
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

    accent = (0, 255, 65)
    cyan = (0, 200, 255)
    white = (230, 230, 240)
    dim = (120, 120, 140)

    draw.text((canvas_w // 2, 10), f"{BRAND_NAME}", fill=accent, font=font_large, anchor="mt")
    draw.text((canvas_w // 2, 38), f"Scan & Pay Rs.{amount}", fill=cyan, font=font_medium, anchor="mt")
    draw.text((canvas_w // 2, 58), f"{package_label}", fill=white, font=font_small, anchor="mt")

    qr_x = (canvas_w - qr_w) // 2
    canvas.paste(qr_img, (qr_x, qr_y_start))

    text_y = qr_y_start + qr_h + 15
    draw.text((canvas_w // 2, text_y), f"UPI ID: {upi_id}", fill=white, font=font_medium, anchor="mt")
    draw.text((canvas_w // 2, text_y + 25), f"Amount: Rs.{amount} (Exact)", fill=accent, font=font_medium, anchor="mt")
    draw.text((canvas_w // 2, text_y + 50), f"Token: {token}", fill=dim, font=font_small, anchor="mt")
    draw.text((canvas_w // 2, text_y + 70), "Single-use QR. Do not share.", fill=(255, 70, 70), font=font_small, anchor="mt")

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf, token

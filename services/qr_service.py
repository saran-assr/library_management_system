import io
import base64
import qrcode
import qrcode.image.svg


def generate_qr_svg(data):
    """
    Generate an SVG string for the given payload using qrcode SvgImage factory.
    Zero binary dependencies, lightweight, and crystal-clear vector output.
    """
    factory = qrcode.image.svg.SvgImage
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=factory,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    stream = io.BytesIO()
    img.save(stream)
    return stream.getvalue().decode("utf-8")


def generate_qr_data_uri(data):
    """
    Generate a base64 encoded SVG data URI for inline HTML rendering.
    e.g. data:image/svg+xml;base64,...
    """
    svg_content = generate_qr_svg(data)
    b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"

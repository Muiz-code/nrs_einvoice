import base64
import io
import json
import time


def _load_public_key(value):
    from cryptography.hazmat.primitives import serialization

    data = value.strip()
    if "BEGIN" not in data:
        data = base64.b64decode(data).decode()
    return serialization.load_pem_public_key(data.encode())


def build_qr_string(irn, public_key, certificate):
    """Fallback only: encrypt IRN + timestamp with the NRS public key (from crypto_keys.txt)."""
    from cryptography.hazmat.primitives.asymmetric import padding

    key = _load_public_key(public_key)
    message = json.dumps(
        {"irn": f"{irn}.{int(time.time())}", "certificate": certificate.strip()},
        separators=(",", ":"),
    ).encode()
    return base64.b64encode(key.encrypt(message, padding.PKCS1v15())).decode()


def qr_data_uri(text):
    import qrcode

    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

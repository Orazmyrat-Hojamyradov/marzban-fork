import base64
import binascii

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding, x25519
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from OpenSSL import crypto

_HAPP_CRYPT4_PUBLIC_KEY = b"""-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA3UZ0M3L4K+WjM3vkbQnz
ozHg/cRbEXvQ6i4A8RVN4OM3rK9kU01FdjyoIgywve8OEKsFnVwERZAQZ1Trv60B
hmaM76QQEE+EUlIOL9EpwKWGtTL5lYC1sT9XJMNP3/CI0gP5wwQI88cY/xedpOEB
W72EmOOShHUm/b/3m+HPmqwc4ugKj5zWV5SyiT829aFA5DxSjmIIFBAms7DafmSq
LFTYIQL5cShDY2u+/sqyAw9yZIOoqW2TFIgIHhLPWek/ocDU7zyOrlu1E0SmcQQb
LFqHq02fsnH6IcqTv3N5Adb/CkZDDQ6HvQVBmqbKZKf7ZdXkqsc/Zw27xhG7OfXC
tUmWsiL7zA+KoTd3avyOh93Q9ju4UQsHthL3Gs4vECYOCS9dsXXSHEY/1ngU/hjO
WFF8QEE/rYV6nA4PTyUvo5RsctSQL/9DJX7XNh3zngvif8LsCN2MPvx6X+zLouBX
zgBkQ9DFfZAGLWf9TR7KVjZC/3NsuUCDoAOcpmN8pENBbeB0puiKMMWSvll36+2M
YR1Xs0MgT8Y9TwhE2+TnnTJOhzmHi/BxiUlY/w2E0s4ax9GHAmX0wyF4zeV7kDkc
vHuEdc0d7vDmdw0oqCqWj0Xwq86HfORu6tm1A8uRATjb4SzjTKclKuoElVAVa5Jo
oh/uZMozC65SmDw+N5p6Su8CAwEAAQ==
-----END PUBLIC KEY-----"""


def generate_happ_crypt4_link(url: str) -> str:
    """Encrypt a subscription URL into a Happ crypt4 deep link using RSA PKCS1v15."""
    public_key = load_pem_public_key(_HAPP_CRYPT4_PUBLIC_KEY)
    encrypted = public_key.encrypt(url.encode(), asym_padding.PKCS1v15())
    return "happ://crypt4/" + base64.b64encode(encrypted).decode()


def get_cert_SANs(cert: bytes):
    cert = x509.load_pem_x509_certificate(cert, default_backend())
    san_list = []
    for extension in cert.extensions:
        if isinstance(extension.value, x509.SubjectAlternativeName):
            san = extension.value
            for name in san:
                san_list.append(name.value)
    return san_list


def generate_certificate():
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    cert = crypto.X509()
    cert.get_subject().CN = "Gozargah"
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(100*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')
    cert_pem = crypto.dump_certificate(
        crypto.FILETYPE_PEM, cert).decode("utf-8")
    key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8")

    return {
        "cert": cert_pem,
        "key": key_pem
    }


def add_base64_padding(b64_string: str) -> str:
    """Adds missing Base64 padding if necessary."""
    missing_padding = len(b64_string) % 4
    return b64_string + ('=' * (4 - missing_padding)) if missing_padding else b64_string


def get_x25519_public_key(private_key_b64: str) -> str:
    """
    Converts an X25519 private key (URL-safe Base64) into a public key (URL-safe Base64 format).

    :param private_key_b64: The private key in URL-safe Base64 format (without padding).
    :return: The corresponding public key as a URL-safe Base64 string (without padding).
    """
    try:
        # Decode Base64 (URL-safe) Add padding if needed
        private_key_bytes = base64.urlsafe_b64decode(
            add_base64_padding(private_key_b64))

        # Ensure the private key is 32 bytes
        if len(private_key_bytes) != 32:
            raise ValueError(
                "Invalid private key length. Must be 32 bytes after decoding.")

        # Load the private key
        private_key = x25519.X25519PrivateKey.from_private_bytes(
            private_key_bytes)

        # Derive the public key
        public_key = private_key.public_key()

        # Convert the public key to bytes
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        # Encode the public key as URL-safe Base64 (without padding)
        public_key_b64 = base64.urlsafe_b64encode(
            public_key_bytes).decode().rstrip("=")

        return public_key_b64

    except (ValueError, binascii.Error):
        raise ValueError("Invalid private key.")

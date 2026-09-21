
import os
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from ipaddress import ip_address


def _cert_is_valid(cert_path: str, min_days_remaining: int = 30) -> bool:
    """Return True if cert exists, is parseable, and doesn't expire within min_days_remaining."""
    try:
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        remaining = cert.not_valid_after_utc - datetime.datetime.now(datetime.timezone.utc)
        if remaining.days < min_days_remaining:
            print(f"[WARN] Certificate expires in {remaining.days} days — regenerating.")
            return False
        return True
    except Exception as e:
        print(f"[WARN] Certificate invalid or unreadable ({e}) — regenerating.")
        return False


def generate_self_signed_cert():
    cert_dir = os.path.join(os.path.dirname(__file__), "certs")
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
        print(f"Created directory: {cert_dir}")

    key_path = os.path.join(cert_dir, "key.pem")
    cert_path = os.path.join(cert_dir, "cert.pem")

    if os.path.exists(key_path) and os.path.exists(cert_path):
        if _cert_is_valid(cert_path):
            print("Certificates already exist and are valid. Skipping generation.")
            return
        # Remove stale/corrupt certs before regenerating
        for p in (key_path, cert_path):
            try:
                os.remove(p)
            except OSError:
                pass

    print("Generating new self-signed certificate...")

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Generate certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"MX"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"CDMX"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"CDMX"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Atlas ERP"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(u"localhost"),
            x509.DNSName(u"127.0.0.1"),
            x509.IPAddress(ip_address("127.0.0.1")),
        ]),
        critical=False,
    ).sign(key, hashes.SHA256())

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass  # Windows ignores chmod; POSIX failures shouldn't block startup

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Certificates generated successfully at: {cert_dir}")


if __name__ == "__main__":
    generate_self_signed_cert()

#!/usr/bin/env python3
"""
Custom Spotify OAuth handler with a local HTTPS callback server.

Spotify requires HTTPS redirect URIs. This module generates a self-signed
certificate on the fly and spins up a temporary HTTPS server to capture
the OAuth callback code.
"""

import http.server
import ipaddress
import os
import socket
import ssl
import tempfile
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timezone, timedelta

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


REDIRECT_PORT = 8888
REDIRECT_HOST = "localhost"
REDIRECT_PATH = "/callback"
REDIRECT_URI = f"https://{REDIRECT_HOST}:{REDIRECT_PORT}{REDIRECT_PATH}"

_SUCCESS_HTML = b"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2>Authentication successful!</h2>
<p>You can close this tab and return to the terminal.</p>
</body></html>"""

_ERROR_HTML = b"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2>Authentication failed</h2>
<p>Please check the terminal for details.</p>
</body></html>"""


def _generate_self_signed_cert() -> tuple[str, str]:
    """Generate a temporary self-signed cert and key, return (cert_path, key_path)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, REDIRECT_HOST),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(REDIRECT_HOST),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    tmp_dir = tempfile.mkdtemp()
    cert_path = os.path.join(tmp_dir, "cert.pem")
    key_path = os.path.join(tmp_dir, "key.pem")

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    return cert_path, key_path


def _run_callback_server(code_holder: dict, cert_path: str, key_path: str):
    """Start a one-shot HTTPS server that captures the OAuth code."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # suppress request logs

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = dict(urllib.parse.parse_qsl(parsed.query))

            if "code" in params:
                code_holder["code"] = params["code"]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_SUCCESS_HTML)
            else:
                error = params.get("error", "unknown")
                code_holder["error"] = error
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_ERROR_HTML)

            # Signal the server to stop after this request
            threading.Thread(target=self.server.shutdown).start()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)

    server = http.server.HTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


def get_spotify_token(client_id: str, client_secret: str, scope: str) -> dict:
    """
    Run the full Spotify OAuth PKCE-less Authorization Code flow with a local
    HTTPS callback server. Returns the token dict from Spotify.
    """
    import secrets

    cert_path, key_path = _generate_self_signed_cert()
    state = secrets.token_urlsafe(16)

    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&scope={urllib.parse.quote(scope)}"
        f"&state={state}"
    )

    code_holder: dict = {}

    server_thread = threading.Thread(
        target=_run_callback_server,
        args=(code_holder, cert_path, key_path),
        daemon=True,
    )
    server_thread.start()

    print(f"Opening Spotify login in your browser...")
    print(f"  If the browser doesn't open, visit:\n  {auth_url}")
    print()
    print("NOTE: Your browser will warn about an untrusted certificate.")
    print("This is expected — click 'Advanced' → 'Proceed to localhost' to continue.")
    print()
    webbrowser.open(auth_url)

    server_thread.join(timeout=120)

    if "error" in code_holder:
        raise RuntimeError(f"Spotify auth denied: {code_holder['error']}")
    if "code" not in code_holder:
        raise RuntimeError("Timed out waiting for Spotify OAuth callback.")

    # Exchange code for token
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code_holder["code"],
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
    )
    resp.raise_for_status()
    return resp.json()

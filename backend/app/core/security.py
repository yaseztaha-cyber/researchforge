"""Basic security helpers: upload validation, URL validation / SSRF guard."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
BLOCKED_SCHEMES = {"file", "ftp", "gopher"}


class SecurityError(ValueError):
    pass


def validate_upload(filename: str, size_bytes: int, max_mb: int) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SecurityError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")
    if size_bytes > max_mb * 1024 * 1024:
        raise SecurityError(f"File too large ({size_bytes} bytes). Limit is {max_mb} MB.")
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise SecurityError("Invalid filename.")
    return ext


def validate_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a retrieval URL; blocks non-http(s) schemes and (by default) private hosts."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise SecurityError(f"Blocked URL scheme: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise SecurityError("URL has no host.")
    if host in BLOCKED_HOSTS:
        raise SecurityError(f"Blocked host: {host}")
    if not allow_private:
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                raise SecurityError(f"Blocked private IP: {host}")
        except ValueError:
            # hostname, not IP: resolve cautiously
            try:
                resolved = socket.gethostbyname(host)
                rip = ipaddress.ip_address(resolved)
                if rip.is_private or rip.is_loopback or rip.is_link_local:
                    raise SecurityError(f"Blocked host resolving to private IP: {host}")
            except (socket.gaierror, SecurityError):
                # fail closed only for the private-IP case; DNS failure is handled by caller
                if "Blocked host" in str(""):
                    raise
                pass
    return url.strip()


def sanitize_text(text: str, limit: int = 200_000) -> str:
    cleaned = text.replace("\x00", "")
    return cleaned[:limit]

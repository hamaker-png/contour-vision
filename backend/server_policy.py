"""Small single-process public-service limits; local mode retains its workflow."""
from collections import deque
import os
import time
from urllib.parse import urlsplit

from .local_settings import public_mode

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
MAX_BODY_BYTES = 60_000_000


def integer_setting(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        raise RuntimeError(f"{name} must be an integer") from None
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def authority(value):
    """Validate an HTTP Host authority without trusting forwarded headers."""
    if not value or any(c.isspace() for c in value) or any(c in value for c in "/\\?#@"):
        return None
    try:
        parsed = urlsplit("//" + value)
        port = parsed.port
        if not parsed.hostname or parsed.username or parsed.password:
            return None
        return parsed.hostname.lower(), port
    except ValueError:
        return None


def configured_hosts():
    values = os.environ.get("CONTOUR_ALLOWED_HOSTS", "").split(",")
    # Render supplies its own exact service hostname, without a wildcard.
    values.append(os.environ.get("RENDER_EXTERNAL_HOSTNAME", ""))
    hosts = set()
    for value in values:
        if not value.strip():
            continue
        parsed = authority(value.strip())
        if parsed is None or "*" in value:
            raise RuntimeError("CONTOUR_ALLOWED_HOSTS must contain exact hostnames, optionally with ports")
        hosts.add(parsed)
    return hosts


def request_origin_error(request):
    host = authority(request.headers.get("host", ""))
    if host is None:
        return "Invalid request host"
    local = host[0] in LOOPBACK or (host[0] == "testserver" and
                                   (not public_mode() or request.client and request.client.host == "testclient"))
    if not local and (not public_mode() or host not in configured_hosts()):
        return "This host is not configured for Contour"
    origin = request.headers.get("origin")
    if origin:
        try:
            parsed = urlsplit(origin)
            origin_host = authority(parsed.netloc)
        except ValueError:
            return "Cross-origin requests are disabled"
        schemes = {"http", "https"} if local else {"https"}
        if (parsed.scheme not in schemes or origin_host != host or parsed.path or
                parsed.query or parsed.fragment or parsed.username or parsed.password):
            return "Cross-origin requests are disabled"
    if request.headers.get("sec-fetch-site") == "cross-site":
        return "Cross-origin requests are disabled"
    return None


class PublicAdmission:
    """No unbounded body/CPU queue. Counts are global, deliberately not spoofable IPs."""
    def __init__(self):
        self.active = 0
        self.started = deque()

    def enter(self):
        maximum = integer_setting("CONTOUR_MAX_ACTIVE_POSTS", 2, 1, 8)
        rate = integer_setting("CONTOUR_POSTS_PER_MINUTE", 60, 1, 600)
        now = time.monotonic()
        while self.started and self.started[0] <= now - 60:
            self.started.popleft()
        if self.active >= maximum:
            return 503, "The shared server is busy. Wait for the current jobs to finish, then retry.", "2"
        if len(self.started) >= rate:
            return 429, "This server's request limit was reached. Wait a minute, then retry.", "60"
        self.active += 1
        self.started.append(now)
        return None

    def leave(self):
        self.active -= 1


def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'; object-src 'none'")
    return response

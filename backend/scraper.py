import ipaddress
import socket
from urllib.parse import urlparse

from bs4 import BeautifulSoup

ALLOWED_SCHEMES = ("http", "https")
ALLOWED_PORTS = (80, 443)
MAX_URL_LENGTH = 2000


class FetchError(Exception):
    """Something went wrong getting a page. The message is safe to show the user."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# tags that almost never hold the real text of a page
NOISE_TAGS = ["script", "style", "noscript", "nav", "header", "footer",
              "aside", "form", "iframe", "svg"]


def extract_text(html):
    """Take raw HTML and return just the readable text as one clean string."""
    soup = BeautifulSoup(html, "html.parser")

    # throw the junk away completely, tag and everything inside it
    for tag in soup(NOISE_TAGS):
        tag.decompose()

    # separator=" " matters: without it "<p>a</p><p>b</p>" would turn into "ab"
    text = soup.get_text(separator=" ")

    # collapse all runs of spaces, tabs and newlines into single spaces
    return " ".join(text.split())


def resolve_ips(host):
    """Look up every IP address a hostname points to."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        raise FetchError("could not find that website")
    return {info[4][0] for info in infos}


def check_url_is_safe(url):
    """Raise FetchError unless this URL is safe for our server to visit."""
    if len(url) > MAX_URL_LENGTH:
        raise FetchError("that link is too long")

    try:
        parsed = urlparse(url)
        port = parsed.port          # raises ValueError if the port is garbage
    except ValueError:
        raise FetchError("that doesn't look like a valid link")

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise FetchError("only http and https links are allowed")
    if not parsed.hostname:
        raise FetchError("that doesn't look like a valid link")
    if parsed.username or parsed.password:
        raise FetchError("links with a username or password are not allowed")
    if port is not None and port not in ALLOWED_PORTS:
        raise FetchError("that port is not allowed")

    # the important part: look at where the name REALLY points, because names
    # and odd number formats (2130706433, 0x7f000001, 127.1) can all mean 127.0.0.1
    ips = resolve_ips(parsed.hostname)
    if not ips:
        raise FetchError("could not find that website")

    for ip in ips:
        ip = ip.split("%")[0]       # ipv6 addresses can carry a "%eth0" suffix
        address = ipaddress.ip_address(ip)
        if address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped   # ::ffff:127.0.0.1 is really 127.0.0.1
        # is_global is False for private, loopback, link-local, reserved, etc.
        # we check EVERY address, so one public + one private record is still blocked
        if not address.is_global:
            raise FetchError("that address is not allowed")
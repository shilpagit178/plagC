import ipaddress
import socket
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ALLOWED_SCHEMES = ("http", "https")
ALLOWED_PORTS = (80, 443)
MAX_URL_LENGTH = 2000

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024    # biggest page we will accept: 2 MB
MAX_REDIRECTS = 3
TIMEOUT = (3, 5)                        # seconds: (to connect, to wait for data)
TOTAL_TIME_LIMIT = 10                   # seconds for the whole download
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
USER_AGENT = "plagC-checker/0.1"

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

def download(url):
    """Safely download a page. Returns (content_type, raw_bytes)."""
    started = time.monotonic()
    current = url

    for _ in range(MAX_REDIRECTS + 1):
        # check EVERY hop, not just the first link: a harmless-looking page
        # can redirect us to an internal address
        check_url_is_safe(current)

        try:
            response = requests.get(
                current,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
                stream=True,            # don't pull the whole body in yet
                allow_redirects=False,  # we follow redirects ourselves, safely
            )
        except requests.exceptions.Timeout:
            raise FetchError("the website took too long to respond", 504)
        except requests.exceptions.RequestException:
            raise FetchError("could not download that page", 502)

        with response:                  # always closes the connection
            if response.is_redirect:
                current = urljoin(current, response.headers["Location"])
                continue

            if response.status_code != 200:
                raise FetchError(f"the website answered with status {response.status_code}", 502)

            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise FetchError("that link is not a web page or plain text")

            # cheap early exit if the server announces a huge body
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > MAX_DOWNLOAD_BYTES:
                raise FetchError("that page is too large", 413)

            # the announced size can lie (or be missing), so count what really arrives.
            # iter_content hands us the DECODED bytes, so a tiny gzip file that
            # expands into gigabytes is stopped here too
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=8192):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise FetchError("that page is too large", 413)
                if time.monotonic() - started > TOTAL_TIME_LIMIT:
                    raise FetchError("the website took too long to respond", 504)
                chunks.append(chunk)
            return content_type, b"".join(chunks)

    raise FetchError("that link redirects too many times", 502)


def fetch_text(url):
    """Download a link and return its readable text."""
    content_type, body = download(url)

    if content_type == "text/plain":
        text = " ".join(body.decode("utf-8", errors="replace").split())
    else:
        # hand BeautifulSoup the raw bytes: it reads the page's own charset
        # declaration, which is more reliable than guessing here
        text = extract_text(body)

    if not text:
        raise FetchError("could not find any readable text on that page "
                         "(it may build its content with JavaScript)", 422)
    return text
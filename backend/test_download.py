# checks downloading pages safely, using a tiny fake web server on this computer
# (no internet needed). run with:  python backend/test_download.py

import gzip
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import scraper
from scraper import FetchError, fetch_text

failed = 0


def check(name, condition):
    global failed
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    if not condition:
        failed += 1


class FakeSite(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the test output quiet

    def reply(self, body, content_type="text/html", status=200, extra=None, length=True):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length:
            self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self.route()
        except (BrokenPipeError, ConnectionResetError):
            pass  # our downloader hung up early on purpose

    def route(self):
        p = self.path
        if p == "/ok":
            self.reply(b"<html><body><nav>menu</nav><p>Hello from the fake site.</p></body></html>")
        elif p == "/plain":
            self.reply(b"just  some\nplain   text", "text/plain")
        elif p == "/ua":
            self.reply(self.headers.get("User-Agent", "").encode(), "text/plain")
        elif p == "/utf8":
            self.reply('<html><head><meta charset="utf-8"></head><body>caf\u00e9 menu</body></html>'.encode("utf-8"))
        elif p == "/pdf":
            self.reply(b"%PDF-1.4 fake", "application/pdf")
        elif p == "/missing":
            self.reply(b"nope", status=404)
        elif p == "/js-only":
            self.reply(b"<html><body><script>render()</script></body></html>")
        elif p == "/big":
            self.reply(b"x" * (3 * 1024 * 1024))
        elif p == "/bigstream":   # no Content-Length at all, just keeps sending
            self.reply(b"", length=False)
            for _ in range(400):
                self.wfile.write(b"y" * 8192)
        elif p == "/gzipbomb":    # tiny on the wire, huge once unpacked
            self.reply(gzip.compress(b"z" * (5 * 1024 * 1024)), extra={"Content-Encoding": "gzip"})
        elif p == "/slow":        # drips one byte at a time
            self.reply(b"", length=False)
            for _ in range(30):
                self.wfile.write(b"s")
                self.wfile.flush()
                time.sleep(0.3)
        elif p == "/redirect":
            self.reply(b"", status=302, extra={"Location": "/ok"})
        elif p == "/redirect-internal":
            self.reply(b"", status=302, extra={"Location": "http://169.254.169.254/latest/meta-data"})
        elif p == "/redirect-file":
            self.reply(b"", status=302, extra={"Location": "file:///etc/passwd"})
        elif p == "/loop":
            self.reply(b"", status=302, extra={"Location": "/loop"})
        else:
            self.reply(b"?", status=404)


server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSite)
BASE = f"http://127.0.0.1:{server.server_address[1]}"
threading.Thread(target=server.serve_forever, daemon=True).start()

# our own safety check would (correctly) refuse 127.0.0.1, so let the test
# server through, and send everything else to the real check
real_check = scraper.check_url_is_safe
scraper.check_url_is_safe = lambda url: None if url.startswith(BASE + "/") else real_check(url)


def fails(path, words, status=None):
    """True if fetching this path raises a FetchError mentioning `words`."""
    try:
        fetch_text(BASE + path)
        return False
    except FetchError as e:
        return words in e.message and (status is None or e.status == status)


# --- things that should work ---
check("normal page -> clean text", fetch_text(BASE + "/ok") == "Hello from the fake site.")
check("plain text page works", fetch_text(BASE + "/plain") == "just some plain text")
check("follows a normal redirect", fetch_text(BASE + "/redirect") == "Hello from the fake site.")
check("reads utf-8 pages correctly", "caf\u00e9" in fetch_text(BASE + "/utf8"))
check("identifies itself with a user agent", "plagC" in fetch_text(BASE + "/ua"))

# --- things that should be refused ---
check("pdf is refused", fails("/pdf", "not a web page"))
check("404 -> error with status 502", fails("/missing", "status 404", 502))
check("page with no readable text -> 422", fails("/js-only", "JavaScript", 422))
check("body over 2 MB (announced) -> 413", fails("/big", "too large", 413))
check("body over 2 MB (not announced) -> 413", fails("/bigstream", "too large", 413))
check("gzip bomb is stopped -> 413", fails("/gzipbomb", "too large", 413))
check("redirect to internal address is blocked", fails("/redirect-internal", "address"))
check("redirect to file:// is blocked", fails("/redirect-file", "http and https"))
check("endless redirects stop -> 502", fails("/loop", "too many times", 502))

# slow server: shrink the total limit so the test doesn't take long
real_limit = scraper.TOTAL_TIME_LIMIT
scraper.TOTAL_TIME_LIMIT = 1
check("slow drip is cut off -> 504", fails("/slow", "too long", 504))
scraper.TOTAL_TIME_LIMIT = real_limit

# nothing is listening on this port at all
scraper.check_url_is_safe = lambda url: None
try:
    fetch_text("http://127.0.0.1:1/")
    check("connection refused -> error, not a crash", False)
except FetchError as e:
    check("connection refused -> error, not a crash", e.status == 502)

server.shutdown()

print()
if failed == 0:
    print("all download checks passed")
else:
    print(f"{failed} check(s) failed, look above")
    sys.exit(1)
# checks the whole API in one go, without needing the server to be running
# (flask has a built-in test client that talks to the app directly).
# run it with:  python backend/test_api.py

import sys

import app as app_module
from app import app
from scraper import FetchError

client = app.test_client()
failed = 0


def check(name, condition):
    global failed
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    if not condition:
        failed += 1


def post(payload):
    return client.post("/api/check", json=payload)


# --- the server is alive and the C++ module loaded ---
r = client.get("/api/health")
check("health -> 200 and ok", r.status_code == 200 and r.get_json()["status"] == "ok")

# --- normal use ---
r = post({"textA": "the quick brown fox jumps", "textB": "a quick brown fox jumps today"})
d = r.get_json()
check("normal request -> 200", r.status_code == 200)
check("normal request -> 80% similarity", d["similarityPercent"] == 80.0)
check("normal request -> one span A[1..4] == B[1..4]",
      len(d["matches"]) == 1 and d["matches"][0]["startInA"] == 1
      and d["matches"][0]["endInA"] == 4 and d["matches"][0]["startInB"] == 1)
check("normal request -> reports engine time", d["elapsedMs"] >= 0)

same = "climate change is a serious global issue"
check("identical text -> 100%", post({"textA": same, "textB": same}).get_json()["similarityPercent"] == 100.0)

# --- bad input should be a 400, never a 500 ---
check("no body -> 400", client.post("/api/check").status_code == 400)
check("json list instead of object -> 400", post([1, 2, 3]).status_code == 400)
check("missing textB -> 400", post({"textA": "hello there"}).status_code == 400)
check("number instead of text -> 400", post({"textA": 123, "textB": "hi"}).status_code == 400)
check("blank text -> 400", post({"textA": "   ", "textB": "hi"}).status_code == 400)
check("GET instead of POST -> 405", client.get("/api/check").status_code == 405)

# --- limits ---
at_limit = " ".join(f"w{i}" for i in range(10000))
over_limit = " ".join(f"w{i}" for i in range(10001))
check("exactly 10000 words -> allowed", post({"textA": at_limit, "textB": at_limit}).status_code == 200)
check("10001 words -> 413", post({"textA": over_limit, "textB": "hi"}).status_code == 413)

big_body = client.post("/api/check", data=b'{"textA": "' + b"x " * 600000 + b'", "textB": "hi"}',
                       content_type="application/json")
check("body over 1 MB -> 413 with a json error", big_body.status_code == 413 and "error" in big_body.get_json())


# --- document B from a link (the network is faked here, no internet needed) ---
real_fetch = app_module.fetch_text
app_module.fetch_text = lambda url: "a quick brown fox jumps today"

r = post({"textA": "the quick brown fox jumps", "urlB": "https://example.com/page"})
d = r.get_json()
check("urlB -> 200 and same result as pasted text", r.status_code == 200 and d["similarityPercent"] == 80.0)
check("urlB -> reports how long the fetch took", isinstance(d["fetchMs"], float))
check("pasted text -> fetchMs is null", post({"textA": "a b c d e", "textB": "a b c d e"}).get_json()["fetchMs"] is None)
check("short page -> not truncated", d["truncatedB"] is False)

check("both textB and urlB -> 400", post({"textA": "hi there", "textB": "x y", "urlB": "https://example.com"}).status_code == 400)
check("neither textB nor urlB -> 400", post({"textA": "hi there"}).status_code == 400)
check("urlB not a string -> 400", post({"textA": "hi there", "urlB": 5}).status_code == 400)
check("blank urlB -> 400", post({"textA": "hi there", "urlB": "   "}).status_code == 400)

app_module.fetch_text = lambda url: " ".join(["word"] * 150000)
r = post({"textA": "word word word word", "urlB": "https://example.com/long"})
check("very long page -> cut and flagged", r.status_code == 200 and r.get_json()["truncatedB"] is True)

def failing(message, status):
    def fake(url):
        raise FetchError(message, status)
    return fake

app_module.fetch_text = failing("the website took too long to respond", 504)
r = post({"textA": "hi there", "urlB": "https://slow.example"})
check("fetch error -> its message and status reach the caller",
      r.status_code == 504 and r.get_json()["error"] == "the website took too long to respond")

# now the real safety check, no fake: internal addresses must be refused end to end
app_module.fetch_text = real_fetch
for bad in ("http://127.0.0.1/", "http://localhost:80/", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
    r = post({"textA": "hi there", "urlB": bad})
    check(f"real guard refuses {bad} -> 400", r.status_code == 400 and "error" in r.get_json())
    
print()
if failed == 0:
    print("all api checks passed")
else:
    print(f"{failed} check(s) failed, look above")
    sys.exit(1)
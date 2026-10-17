# checks the whole API in one go, without needing the server to be running
# (flask has a built-in test client that talks to the app directly).
# run it with:  python backend/test_api.py

import sys

from app import app

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

print()
if failed == 0:
    print("all api checks passed")
else:
    print(f"{failed} check(s) failed, look above")
    sys.exit(1)
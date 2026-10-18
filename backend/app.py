import os
import sys
import time

from flask import Flask, jsonify, request

# The compiled C++ module lives in ../cpp_core, not next to this file,
# so Python doesn't know about it yet. Buildin' the path from THIS file's
# location (not from wherever the terminal happens to be) and tell
# Python to look there too.
HERE = os.path.dirname(os.path.abspath(__file__))
CPP_DIR = os.path.abspath(os.path.join(HERE, "..", "cpp_core"))
sys.path.append(CPP_DIR)

import matcher_module  # noqa: E402  (has to come after the sys.path line)

from scraper import FetchError, fetch_text  # noqa: E402

app = Flask(__name__)

# limits, so one huge request can't tie up the server

MAX_WORDS = 10000                      # per pasted text
MAX_WORDS_FETCHED = 100000             # a fetched page is cut to this many words

app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024   # whole request body: 1 MB


@app.errorhandler(413)
def body_too_large(error):
    # Flask raises 413 on its own when the body is over MAX_CONTENT_LENGTH.
    # By default that comes back as an HTML page; our frontend expects JSON.
    return jsonify({"error": "request is too large (limit is 1 MB)"}), 413


@app.route("/api/health")
def health():
    # quick "is the server alive and did the C++ module load" check
    return jsonify({"status": "ok", "cpp_module": matcher_module.__name__})


@app.route("/api/check", methods=["POST"])

def check():
    # silent=True means "give me None if the body isn't valid JSON"
    # instead of Flask raising its own error page
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "send a JSON object with textA and textB"}), 400

    text_a = data.get("textA")
    text_b = data.get("textB")
    url_b = data.get("urlB")

    # Document B comes from pasted text OR from a link, never both, never neither
    if (text_b is None) == (url_b is None):
        return jsonify({"error": "send exactly one of textB or urlB"}), 400

    if not isinstance(text_a, str) or not text_a.strip():
        return jsonify({"error": "textA must be a non-empty string"}), 400
    # split() is a cheap word count, good enough for a size limit
    if len(text_a.split()) > MAX_WORDS:
        return jsonify({"error": f"each text can be at most {MAX_WORDS} words"}), 413

    fetch_ms = None
    truncated_b = False

    if url_b is not None:
        if not isinstance(url_b, str) or not url_b.strip():
            return jsonify({"error": "urlB must be a non-empty string"}), 400

        fetch_start = time.perf_counter()
        try:
            text_b = fetch_text(url_b.strip())
        except FetchError as e:
            # the scraper already chose a safe message and a fitting status code
            return jsonify({"error": e.message}), e.status
        fetch_ms = (time.perf_counter() - fetch_start) * 1000

        # pages are often long, so cut instead of refusing, and tell the caller
        words = text_b.split()
        if len(words) > MAX_WORDS_FETCHED:
            text_b = " ".join(words[:MAX_WORDS_FETCHED])
            truncated_b = True
    else:
        if not isinstance(text_b, str) or not text_b.strip():
            return jsonify({"error": "textB must be a non-empty string"}), 400
        if len(text_b.split()) > MAX_WORDS:
            return jsonify({"error": f"each text can be at most {MAX_WORDS} words"}), 413

    # time only the C++ call, so the number means "how long the engine took"
    start = time.perf_counter()
    result = matcher_module.compare_texts(text_a, text_b)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # the C++ result is a custom object, so turn it into plain dicts/lists
    # that jsonify knows how to send
    matches = [
        {
            "startInA": m.startInA,
            "endInA": m.endInA,
            "startInB": m.startInB,
            "endInB": m.endInB,
            "wordCount": m.wordCount,
        }
        for m in result.matches
    ]

    return jsonify({
        "similarityPercent": round(result.similarityPercent, 2),
        "totalWordsInA": result.totalWordsInA,
        "totalMatchedWordsInA": result.totalMatchedWordsInA,
        "matches": matches,
        "elapsedMs": round(elapsed_ms, 3),
        "fetchMs": None if fetch_ms is None else round(fetch_ms, 1),
        "truncatedB": truncated_b,
    })


if __name__ == "__main__":
    app.run(debug=True)
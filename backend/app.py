import os
import sys

from flask import Flask, jsonify

# The compiled C++ module lives in ../cpp_core, not next to this file,
# so Python doesn't know about it yet. Buildin' the path from THIS file's
# location (not from wherever the terminal happens to be) and tell
# Python to look there too.
HERE = os.path.dirname(os.path.abspath(__file__))
CPP_DIR = os.path.abspath(os.path.join(HERE, "..", "cpp_core"))
sys.path.append(CPP_DIR)

import matcher_module  # noqa: E402  (has to come after the sys.path line)

app = Flask(__name__)


@app.route("/api/health")
def health():
    # quick "is the server alive and did the C++ module load" check
    return jsonify({"status": "ok", "cpp_module": matcher_module.__name__})


if __name__ == "__main__":
    app.run(debug=True)
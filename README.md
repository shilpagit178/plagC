# plagC — web-based plagiarism detector

A plagiarism checker with a C++ matching engine, exposed to Python through
PyBind11 and served by a small Flask API. You give it two texts and it tells
you what percentage of the first one appears in the second, which stretches
matched, and how long the engine took.

**Status: work in progress.** The engine, the Python bindings and the backend
API are done and tested. URL input and the browser frontend are not built yet
(see the roadmap at the bottom).

## What it does today

- Compares two texts for **exact** matches (word for word, ignoring case and
  punctuation).
- Reports the similarity as "percent of Document A that was found in
  Document B", plus the matched spans as word positions in both documents.
- Rejects bad input with clear JSON errors and refuses oversized requests.

It does not detect paraphrasing yet, and it does not fetch URLs yet.

## How it works

```
POST /api/check  { textA, textB }
        |
   Flask (backend/app.py)         validates input, applies size limits
        |
   matcher_module (C++ via PyBind11)
        |   1. tokenize           lowercase, strip punctuation, split into words
        |   2. shingle            overlapping 4-word windows
        |   3. match              hash map of B's shingles, look up each of A's
        |   4. merge              join neighbouring matches into longer spans
        |   5. score              matched words in A / total words in A
        v
   JSON: similarityPercent, matches, elapsedMs, ...
```

**Shingles.** Comparing single words is useless (every document contains
"the"), so the engine compares runs of N consecutive words. Two documents that
share a 4-word run share real wording. N is fixed at 4: smaller values flag
common phrases, larger ones miss short copying.

**Matching.** Document B's shingles go into an `unordered_map` keyed by hash.
Each shingle of A is looked up, and a hit is only accepted after the actual
words are compared, so a hash collision cannot create a false match.

**Merging.** A copied passage produces many overlapping shingle matches. A
copied run keeps the same offset between its position in B and its position in
A (the "diagonal"), so the engine groups matches by diagonal and joins
consecutive ones into a single span. This also gives the right location when a
phrase appears more than once in B.

**Repeat cap.** If one shingle appears more than 20 times in B, only the first
20 locations are kept. Without this, text like the same word repeated
thousands of times makes the number of match pairs grow with the square of the
repeat count. The cap does not change the score (every matching shingle in A
still gets at least one match); it only limits which locations in B are
reported for extremely common phrases.

**Why a hash map and not a trie.** Every shingle is the same length and the
only question is "does this exact shingle exist in B?", which a hash map
answers in O(1) on average. A trie starts to pay off with variable-length or
prefix matching, which exact matching does not need.

## Project layout

```
plagC/
├── cpp_core/
│   ├── matcher.hpp          structs and function declarations
│   ├── matcher.cpp          the engine
│   ├── bindings.cpp         PyBind11 glue (exposes compare_texts to Python)
│   ├── main.cpp             small C++ demo
│   ├── test_edge_cases.cpp  C++ tests
│   └── test_bindings.py     Python test of the compiled module
├── backend/
│   ├── app.py               Flask API
│   └── test_api.py          API tests
├── frontend/                empty for now
├── requirements.txt
└── README.md
```

## Setup

The compiled module is tied to your OS and Python version, so it has to be
built on the machine that runs it. These steps are for Linux, or WSL on
Windows (building against Windows Python is not supported here).

```bash
# once: system packages (Ubuntu 24.04 shown; match the venv package to your Python)
sudo apt update
sudo apt install -y g++ python3-dev python3-pip python3.12-venv

# once: virtual environment and Python packages
python3 -m venv venv
source venv/bin/activate          # run this in every new terminal
pip install -r requirements.txt

# build the C++ module (repeat whenever the C++ changes)
cd cpp_core
g++ -O3 -Wall -shared -std=c++17 -fPIC \
    $(python3-config --includes) \
    -I$(python -c "import pybind11; print(pybind11.get_include())") \
    bindings.cpp matcher.cpp \
    -o matcher_module$(python3-config --extension-suffix)
cd ..
```

## Run

```bash
python backend/app.py
```

The server starts on `http://127.0.0.1:5000` in debug mode. Debug mode is for
development only; do not deploy it.

## API

### `GET /api/health`

Returns `{"status": "ok", "cpp_module": "matcher_module"}` when the server is
up and the C++ module loaded.

### `POST /api/check`

Request body (JSON):

```json
{ "textA": "the quick brown fox jumps", "textB": "a quick brown fox jumps today" }
```

Response (200):

```json
{
  "similarityPercent": 80.0,
  "totalWordsInA": 5,
  "totalMatchedWordsInA": 4,
  "matches": [
    { "startInA": 1, "endInA": 4, "startInB": 1, "endInB": 4, "wordCount": 4 }
  ],
  "elapsedMs": 0.116
}
```

- Positions are **word indices** (0-based, end inclusive), not character
  offsets.
- `elapsedMs` measures only the C++ call.
- The score is directional: it is the share of `textA` found in `textB`.

Errors are JSON of the form `{"error": "..."}`:

| Status | When |
|--------|------|
| 400 | body is not a JSON object, a field is missing or not a string, or a text is blank |
| 405 | wrong HTTP method |
| 413 | a text is over 10,000 words, or the request body is over 1 MB |

Example:

```bash
curl -s -X POST localhost:5000/api/check \
  -H "Content-Type: application/json" \
  -d '{"textA":"the quick brown fox jumps","textB":"a quick brown fox jumps today"}'
```

## Tests

```bash
# C++ engine (edge cases: empty text, identical text, repeats, ...)
cd cpp_core
g++ -std=c++17 -Wall -o test_edge_cases test_edge_cases.cpp matcher.cpp
./test_edge_cases

# compiled module called from Python (after building it)
python3 test_bindings.py
cd ..

# the API (no server needs to be running)
python backend/test_api.py
```

## Known limitations

- **English only.** The tokenizer keeps ASCII letters and digits and treats
  everything else as a separator, so text in other scripts (for example Hindi)
  produces zero words.
- Apostrophes split words: `don't` becomes `don` and `t`.
- Exact matching only; reworded text is not detected.
- The 10,000-word limit uses a whitespace split, while the engine also splits
  on punctuation, so the limit is approximate.
- Matches are word positions; mapping them back to character offsets for
  highlighting is not done yet.
- Only the Flask development server has been used.

## Roadmap

- [x] Phase 1: C++ matching engine with edge-case tests
- [x] Phase 2: PyBind11 bindings and a Python test
- [x] Phase 3: Flask API with validation, size limits and tests
- [ ] Phase 4: compare against a URL (fetch with requests, extract text with
      BeautifulSoup, with protection against fetching private addresses)
- [ ] Phase 5: browser frontend with highlighted matches and the engine timer
- [ ] Later: paraphrase detection, a non-English tokenizer, measured benchmarks

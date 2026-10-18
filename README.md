# plagC — web-based plagiarism detector

A plagiarism checker with a C++ matching engine, exposed to Python through
PyBind11 and served by a small Flask API. You give it a text and either a
second text or a link, and it tells you what percentage of the first text
appears in the second, which stretches matched, and how long the engine took.

**Status: work in progress.** The engine, the Python bindings, the backend API
and link fetching are done and tested. The browser frontend is not built yet
(see the roadmap at the bottom).

## What it does today

- Compares two texts for **exact** matches (word for word, ignoring case and
  punctuation).
- Document B can be pasted text **or a link**: the server downloads the page
  and extracts its readable text.
- Reports the similarity as "percent of Document A that was found in
  Document B", plus the matched spans as word positions in both documents.
- Rejects bad input with clear JSON errors, refuses oversized requests, and
  refuses links that point at private or internal addresses.

It does not detect paraphrasing yet, and it does not search the web for
sources on its own: you supply the text or the link to compare against.

## How it works

```
POST /api/check  { textA, and either textB or urlB }
        |
   Flask (backend/app.py)         validates input, applies size limits
        |
        |  if urlB:  scraper.py  checks the link is safe, downloads it with
        |                        limits, strips the HTML down to readable text
        v
   matcher_module (C++ via PyBind11)
        |   1. tokenize           lowercase, strip punctuation, split into words
        |   2. shingle            overlapping 4-word windows
        |   3. match              hash map of B's shingles, look up each of A's
        |   4. merge              join neighbouring matches into longer spans
        |   5. score              matched words in A / total words in A
        v
   JSON: similarityPercent, matches, elapsedMs, fetchMs, ...
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

## Fetching links safely

Because the server downloads whatever link a user gives it, a link can be used
to make the server reach things only the server can reach, such as
`http://localhost/...` or a cloud provider's internal metadata address. This
is called server-side request forgery (SSRF). `backend/scraper.py` defends
against it in layers:

- Only `http` and `https`, only ports 80 and 443, no `user:password@` in the
  link, and a maximum link length.
- The hostname is resolved and **every** address it points to must be a public
  address. Disguised forms such as `127.1`, `2130706433`, `0x7f000001` and
  `::ffff:127.0.0.1` are caught because the check is on the resolved address,
  not on the text of the link.
- Redirects are followed manually (at most 3) and each hop is checked again,
  so a harmless-looking page cannot redirect the server to an internal address.
- Downloads are streamed with a 3 s connect timeout, a 5 s read timeout and a
  10 s total limit, and stop at 2 MB of **decoded** content (so a small gzip
  file that expands hugely is stopped too).
- Only `text/html`, `application/xhtml+xml` and `text/plain` are accepted.
- Page text is extracted with BeautifulSoup after removing `script`, `style`,
  `nav`, `header`, `footer`, `aside`, `form`, `iframe` and similar tags.

Known gaps: see "Known limitations" below (DNS rebinding, no rate limiting).

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
│   ├── scraper.py           link safety check, download, HTML -> text
│   ├── test_api.py          API tests
│   ├── test_scraper.py      HTML -> text tests
│   ├── test_url_safety.py   which links are allowed
│   └── test_download.py     download limits, tested against a fake local server
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

Send `textA` plus **exactly one** of `textB` (pasted text) or `urlB` (a link).

```json
{ "textA": "the quick brown fox jumps", "textB": "a quick brown fox jumps today" }
```

```json
{ "textA": "the quick brown fox jumps", "urlB": "https://example.com/article" }
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
  "elapsedMs": 0.116,
  "fetchMs": null,
  "truncatedB": false
}
```

- Positions are **word indices** (0-based, end inclusive), not character
  offsets.
- `elapsedMs` measures only the C++ call. `fetchMs` is how long downloading
  the link took, and is `null` when Document B was pasted.
- `truncatedB` is `true` when a fetched page was longer than 100,000 words and
  was cut. Copied text past the cut-off would not be matched.
- The score is directional: it is the share of `textA` found in Document B.

Limits: pasted texts up to 10,000 words each, request body up to 1 MB, fetched
pages up to 2 MB (cut to their first 100,000 words).

Errors are JSON of the form `{"error": "..."}`:

| Status | When |
|--------|------|
| 400 | body is not a JSON object; `textA` missing, blank or not text; not exactly one of `textB` / `urlB`; `textB` or `urlB` blank or not text; the link is not allowed (wrong scheme or port, credentials, non-public address, unknown host); the link is not a web page or plain text |
| 405 | wrong HTTP method |
| 413 | pasted text over 10,000 words; request body over 1 MB; downloaded page over 2 MB |
| 422 | the page had no readable text (it may build its content with JavaScript) |
| 502 | the other website returned an error, could not be reached, or redirected too many times |
| 504 | the other website took too long (over 10 seconds in total) |

Examples:

```bash
curl -s -X POST localhost:5000/api/check \
  -H "Content-Type: application/json" \
  -d '{"textA":"the quick brown fox jumps","textB":"a quick brown fox jumps today"}'

curl -s -X POST localhost:5000/api/check \
  -H "Content-Type: application/json" \
  -d '{"textA":"This domain is for use in documentation examples without needing permission.","urlB":"https://example.com"}'
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

# backend (none of these need the server running or the internet)
python backend/test_api.py
python backend/test_scraper.py
python backend/test_url_safety.py
python backend/test_download.py
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
- **Pages that build their content with JavaScript come back empty**, because
  the server only reads the HTML it is sent.
- Removing `nav`, `header`, `footer` and `aside` is a heuristic; a site that
  puts real content in those tags will lose it. The page title is kept.
- **DNS rebinding is not fully closed.** The server resolves a hostname to
  check it, and the HTTP library resolves it again to connect. A hostile name
  could answer differently the second time. The full fix is to connect to the
  exact address that was checked.
- There is no rate limiting, and a slow download holds a server thread for up
  to 10 seconds.
- Only the Flask development server has been used.

## Roadmap

- [x] Phase 1: C++ matching engine with edge-case tests
- [x] Phase 2: PyBind11 bindings and a Python test
- [x] Phase 3: Flask API with validation, size limits and tests
- [x] Phase 4: compare against a link (safe download, text extraction)
- [ ] Phase 5: browser frontend with highlighted matches and the engine timer
- [ ] Later: paraphrase detection, a non-English tokenizer, closing the DNS
      rebinding gap, rate limiting, measured benchmarks

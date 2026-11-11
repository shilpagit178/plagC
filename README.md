# plagC

A web-based plagiarism detector. Paste your text, then paste a source text or
give a web page address, and plagC highlights every passage that appears word
for word in both, with a similarity score.

## Tech stack

| Part | Technology | Why |
|------|------------|-----|
| Matching engine | C++17 | The comparison is CPU-bound string and hash work |
| Bridge | PyBind11 | Lets Python call the compiled C++ directly |
| Backend | Python, Flask | Thin API: validates input, calls the engine |
| Page fetching | requests, BeautifulSoup | Downloads a web page and extracts its text |
| Frontend | HTML, CSS, vanilla JavaScript | Input form and highlighted report |

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

A hash match is only accepted after the actual words are compared, so a hash
collision can't cause a false match. Links must point to public addresses,
redirects are checked again at every hop, and downloads have size and time
limits.

## Run it

Needs Linux or WSL, Python 3.12 and g++.

```bash
sudo apt install -y g++ python3-dev python3.12-venv
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cd cpp_core
g++ -O3 -shared -std=c++17 -fPIC $(python3-config --includes) \
    -I$(python -c "import pybind11; print(pybind11.get_include())") \
    bindings.cpp matcher.cpp -o matcher_module$(python3-config --extension-suffix)
cd ..

python backend/app.py        # then open http://localhost:5000
```

## API

`POST /api/check` with `textA` and either `textB` or `urlB`. Returns
`similarityPercent`, the matched `matches` (word positions), `elapsedMs`
(engine time) and `fetchMs`. Errors come back as `{"error": "..."}`.

## Tests

```bash
cd cpp_core && g++ -std=c++17 -o test_edge_cases test_edge_cases.cpp matcher.cpp && ./test_edge_cases && cd ..
python cpp_core/test_bindings.py
python backend/test_api.py
python backend/test_scraper.py
python backend/test_url_safety.py
python backend/test_download.py
```

## Limitations

- Finds exact, word-for-word matches only; reworded text is not detected.
- The tokenizer reads English letters and digits; other scripts produce no words.
- Pages that build their content with JavaScript may come back empty.
- No rate limiting yet.

## Roadmap

- Deploy a public demo (Docker, gunicorn, Render)
- Rate limiting and request logging for the public demo
- Continuous integration: build the module and run every test suite on each push
- Measured benchmarks: the C++ engine against an equivalent pure-Python version
- UTF-8 aware tokenizer, so non-English text works
- Return character offsets from the API, so clients don't need their own tokenizer
- File upload as a source (.txt, .pdf, .docx)
- Compare against several sources at once
- Near-match detection that tolerates small edits (winnowing-style fingerprints)
- Close the DNS-rebinding gap by connecting to the exact address that was checked
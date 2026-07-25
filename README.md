# plagC — Web-Based Plagiarism Detection System

A plagiarism detection system with a C++ performance core (trie/hash-based
exact-match shingling) exposed to a Python/Flask web app via PyBind11.

## Architecture

```
Browser (HTML/JS)
      |
      v
Flask backend (Python) --- BeautifulSoup (scrapes URL sources)
      |
      v
matcher_module (compiled C++, via PyBind11)
      |
      v
Core algorithm: tokenize -> shingle (n-grams) -> hash-match -> merge spans
```

## Why this stack

- **C++ core**: plagiarism matching is CPU-bound string/hash work; C++ avoids
  Python's interpreter overhead for this.
- **PyBind11**: exposes the compiled C++ directly to Python as an importable
  module, instead of reimplementing the algorithm in a slower language.
- **Flask**: thin routing/orchestration layer — no unnecessary framework weight.
- **BeautifulSoup**: reliable HTML parsing for extracting article text from a
  URL, instead of fragile regex-based tag stripping.

## Status

- [x] Phase 1: C++ exact-match core (tokenize, shingle, hash-match, merge spans)
- [ ] Phase 2: PyBind11 bindings
- [ ] Phase 3: Flask API
- [ ] Phase 4: BeautifulSoup URL scraping
- [ ] Phase 5: Frontend

## Phase 1 — C++ core

Located in `cpp_core/`. Build and test standalone (no Python yet):

```bash
cd cpp_core
g++ -std=c++17 -Wall -o test_matcher main.cpp matcher.cpp
./test_matcher
```

### Algorithm

1. Tokenize both texts into lowercase word tokens (punctuation stripped).
2. Generate overlapping N-word shingles for each document.
3. Hash Document B's shingles into an `unordered_map` for O(1) average lookup.
4. Scan Document A's shingles against that map (with collision verification).
5. Merge consecutive matching shingles into contiguous matched spans.
6. Score = (matched words in A / total words in A) * 100.

Shingle size (N) controls sensitivity vs. specificity: smaller N catches more
but flags generic phrasing as false positives; larger N is stricter. N=4-5 is
a reasonable starting point for exact-match detection.

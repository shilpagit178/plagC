#include "matcher.hpp"
#include <cctype>
#include <sstream>
#include <unordered_map>
#include <algorithm>

// ---------------------------------------------------------------------
// tokenize()
// Goal: turn messy raw text into a clean list of lowercase word tokens.
// Why lowercase? "Fox" and "fox" should count as the same word for
// plagiarism purposes -- casing differences aren't meaningful copying.
// Why strip punctuation? "fox." and "fox" should also be treated the same.
// ---------------------------------------------------------------------
std::vector<std::string> tokenize(const std::string& text) {
    std::vector<std::string> tokens;
    std::string current;

    for (char ch : text) {
        if (std::isalnum(static_cast<unsigned char>(ch))) {
            // Build up the current word, lowercased character by character
            current += std::tolower(static_cast<unsigned char>(ch));
        } else {
            // Any non-alphanumeric character (space, comma, period, newline...)
            // marks the end of a word.
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        }
    }
    // Don't forget the last word if the text doesn't end in punctuation/space
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

// ---------------------------------------------------------------------
// generateShingles()
// Goal: slide a window of N consecutive words across the token list.
// We join each window into a single space-separated string, e.g.
// tokens[i..i+n-1] -> "word1 word2 word3"
//
// Number of shingles produced = tokens.size() - n + 1
// (if there are fewer tokens than n, we produce zero shingles)
// ---------------------------------------------------------------------
std::vector<std::string> generateShingles(const std::vector<std::string>& tokens, int n) {
    std::vector<std::string> shingles;

    if (static_cast<int>(tokens.size()) < n) {
        return shingles; // text too short to form even one shingle
    }

    for (int i = 0; i + n <= static_cast<int>(tokens.size()); i++) {
        std::ostringstream oss;
        for (int j = 0; j < n; j++) {
            if (j > 0) oss << ' ';
            oss << tokens[i + j];
        }
        shingles.push_back(oss.str());
    }
    return shingles;
}

// ---------------------------------------------------------------------
// A small internal helper struct: a raw shingle-level match before merging.
// posInA / posInB are the STARTING WORD INDEX of the matching shingle in
// each document (not character positions).
// ---------------------------------------------------------------------
struct RawMatch {
    int posInA;
    int posInB;
};

// ---------------------------------------------------------------------
// findRawMatches()
// This is the "Set Hashing" step from your resume line.
//
// Strategy:
// 1. Build an unordered_map from B's shingles: hash(shingle) -> list of
//    positions where that shingle occurs in B. We use a hash map (not just
//    a plain unordered_set) because we need to know WHERE the match is in
//    B, not just THAT it exists.
// 2. For every shingle in A, hash it and look up candidates in that map.
//    std::hash gives us average O(1) lookup instead of O(n) scanning.
// 3. IMPORTANT: hash collisions are rare but possible (two different
//    strings producing the same hash). So we don't just trust the hash --
//    we double check the actual shingle strings are equal before counting
//    it as a real match. This is a classic hashing correctness practice.
// ---------------------------------------------------------------------
std::vector<RawMatch> findRawMatches(
    const std::vector<std::string>& shinglesA,
    const std::vector<std::string>& shinglesB)
{
    // Map: hash of a shingle -> list of (position, actual shingle string)
    // so we can verify against collisions.
    std::unordered_map<size_t, std::vector<std::pair<int, std::string>>> indexB;
    std::hash<std::string> hasher;

    for (int i = 0; i < static_cast<int>(shinglesB.size()); i++) {
        size_t h = hasher(shinglesB[i]);
        indexB[h].push_back({i, shinglesB[i]});
    }

    std::vector<RawMatch> matches;
    for (int i = 0; i < static_cast<int>(shinglesA.size()); i++) {
        size_t h = hasher(shinglesA[i]);
        auto it = indexB.find(h);
        if (it == indexB.end()) continue; // no candidate at all -> definitely no match

        int keptForThisShingle = 0;
        for (const auto& candidate : it->second) {
            if (candidate.second == shinglesA[i]) {
                // Verified real match (not just a hash collision)
                matches.push_back({i, candidate.first});
                keptForThisShingle++;
                // a shingle that appears this many times in B is a very
                // common phrase, not evidence of copying -- stop collecting
                if (keptForThisShingle >= MAX_LOCATIONS_PER_SHINGLE) break;
            }
        }
    }
    return matches;
}

// ---------------------------------------------------------------------
// mergeMatches()
// Raw matches are one entry PER SHINGLE, so a genuinely copied sentence
// of 10 words (with shingle size 4) would show up as 7 separate
// overlapping raw matches. That's noisy and not what we want to show
// a user ("7 fragments matched" is confusing -- "this whole sentence
// matched" is useful).
//
// So we merge consecutive raw matches into one contiguous span whenever
// BOTH documents advance together: if shingle at word i in A matches
// shingle at word j in B, and the NEXT raw match is (i+1, j+1), that
// means the match is continuing in lockstep in both documents -> merge
// them into a single longer run instead of reporting them separately.
// ---------------------------------------------------------------------
std::vector<MatchSpan> mergeMatches(std::vector<RawMatch> matches, int shingleSize) {
    std::vector<MatchSpan> spans;
    if (matches.empty()) return spans;

    // // Sort by position in A so consecutive shingles are next to each other
    // std::sort(matches.begin(), matches.end(), [](const RawMatch& a, const RawMatch& b) {
    //     return a.posInA < b.posInA;
    // });

    //replaced prev sort logic to -->
    // a copied run keeps the same (posInB - posInA) for every shingle in it,
    // so sort by that "diagonal" first, then by position in A
    std::sort(matches.begin(), matches.end(), [](const RawMatch& a, const RawMatch& b) {
        int diagA = a.posInB - a.posInA;
        int diagB = b.posInB - b.posInA;
        if (diagA != diagB) return diagA < diagB;
        return a.posInA < b.posInA;
    });

    int chainStartA = matches[0].posInA;
    int chainStartB = matches[0].posInB;
    int prevA = matches[0].posInA;
    int prevB = matches[0].posInB;

    for (size_t k = 1; k < matches.size(); k++) {
        int curA = matches[k].posInA;
        int curB = matches[k].posInB;

        // Does this shingle continue the current chain? Both documents
        // must advance by exactly one word position for it to be the
        // same continuous run of copied text.
        if (curA == prevA + 1 && (curB - curA) == (prevB - prevA)) { 
            prevA = curA;
            prevB = curB;
            continue; // still in the same run, keep extending
        }

        // Chain broke -- close off the previous span and start a new one.
        // endInA is prevA + shingleSize - 1 because a shingle starting at
        // prevA covers words [prevA, prevA + shingleSize - 1].
        spans.push_back({
            chainStartA,
            prevA + shingleSize - 1,
            chainStartB,
            prevB + shingleSize - 1,
            (prevA + shingleSize - 1) - chainStartA + 1
        });

        chainStartA = curA;
        chainStartB = curB;
        prevA = curA;
        prevB = curB;
    }

    // Close off the final chain
    spans.push_back({
        chainStartA,
        prevA + shingleSize - 1,
        chainStartB,
        prevB + shingleSize - 1,
        (prevA + shingleSize - 1) - chainStartA + 1
    });

    std::sort(spans.begin(), spans.end(), [](const MatchSpan& a, const MatchSpan& b) {
    if (a.startInA != b.startInA) return a.startInA < b.startInA;
        return a.startInB < b.startInB;
    });

    return spans;
}

// ---------------------------------------------------------------------
// compareTexts()
// The public entry point that ties every step together.
// ---------------------------------------------------------------------
PlagiarismResult compareTexts(const std::string& textA, const std::string& textB, int shingleSize) {
    std::vector<std::string> tokensA = tokenize(textA);
    std::vector<std::string> tokensB = tokenize(textB);

    std::vector<std::string> shinglesA = generateShingles(tokensA, shingleSize);
    std::vector<std::string> shinglesB = generateShingles(tokensB, shingleSize);

    std::vector<RawMatch> rawMatches = findRawMatches(shinglesA, shinglesB);
    std::vector<MatchSpan> mergedSpans = mergeMatches(rawMatches, shingleSize);

    // Count total unique words in A that fall inside some matched span,
    // so overlapping spans (if any) don't get double-counted.
    std::vector<bool> matchedWord(tokensA.size(), false);
    for (const auto& span : mergedSpans) {
        for (int i = span.startInA; i <= span.endInA; i++) {
            if (i >= 0 && i < static_cast<int>(matchedWord.size())) {
                matchedWord[i] = true;
            }
        }
    }
    int totalMatched = 0;
    for (bool b : matchedWord) if (b) totalMatched++;

    PlagiarismResult result;
    result.totalWordsInA = static_cast<int>(tokensA.size());
    result.totalMatchedWordsInA = totalMatched;
    result.similarityPercent = tokensA.empty()
        ? 0.0
        : (100.0 * totalMatched / static_cast<double>(tokensA.size()));
    result.matches = mergedSpans;

    return result;
}

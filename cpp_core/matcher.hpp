#ifndef MATCHER_HPP
#define MATCHER_HPP

#include <string>
#include <vector>

// Fixed shingle size for now (see README for the sensitivity/specificity
// tradeoff discussion). Centralized here so every caller -- main.cpp,
// test files, and later the PyBind11 binding -- uses the same value
// instead of a magic number copy-pasted in multiple places.
constexpr int DEFAULT_SHINGLE_SIZE = 4;

// If one shingle appears more than this many times in Document B, we only
// keep the first few locations. Without a limit, text that repeats a lot
// (like the same word 5000 times) makes the number of match pairs explode.
constexpr int MAX_LOCATIONS_PER_SHINGLE = 20;

// A single contiguous block of matched text between the two documents.
// Positions are WORD indices (not character indices) into the tokenized
// version of each document -- we'll convert back to character offsets
// separately when we want to highlight text on the frontend.
struct MatchSpan {
    int startInA;   // word index where this match starts in Document A
    int endInA;     // word index where this match ends in Document A (inclusive)
    int startInB;   // corresponding word index where it starts in Document B
    int endInB;     // corresponding word index where it ends in Document B
    int wordCount;  // how many words long this matched run is
};

// The final result we hand back after comparing two documents.
struct PlagiarismResult {
    double similarityPercent;          // e.g. 42.5 means 42.5% of Document A's words
                                        // were found copied from Document B
    std::vector<MatchSpan> matches;    // all matched blocks, merged into contiguous runs
    int totalWordsInA;
    int totalMatchedWordsInA;
};

// Step 1: Clean and split raw text into lowercase word tokens.
// "The Quick, Brown Fox!" -> ["the", "quick", "brown", "fox"]
std::vector<std::string> tokenize(const std::string& text);

// Step 2: Slide an N-word window across the tokens to generate shingles.
// tokens = ["the","quick","brown","fox"], n = 2
// -> ["the quick", "quick brown", "brown fox"]
std::vector<std::string> generateShingles(const std::vector<std::string>& tokens, int n);

// Step 3 + 4 + 5: The main entry point. Tokenizes both texts, builds shingles,
// finds matches via hashing, merges adjacent matches into contiguous spans,
// and computes a similarity score.
PlagiarismResult compareTexts(const std::string& textA, const std::string& textB, int shingleSize);

#endif

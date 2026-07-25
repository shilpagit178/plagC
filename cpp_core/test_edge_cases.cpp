#include "matcher.hpp"
#include <iostream>
#include <string>
#include <cassert>

// Small helper so each test prints a clear pass/fail instead of us having
// to eyeball raw numbers every time.
void check(const std::string& testName, bool condition) {
    std::cout << (condition ? "[PASS] " : "[FAIL] ") << testName << "\n";
    if (!condition) {
        std::cout << "       ^ this needs investigating before we move on\n";
    }
}

int main() {
    int n = 4; // shingle size, matches main.cpp

    // -----------------------------------------------------------------
    // Test 1: Completely unrelated documents -> should be ~0% similarity
    // -----------------------------------------------------------------
    {
        std::string a = "The weather today is sunny and warm outside.";
        std::string b = "Quantum computers use qubits instead of classical bits.";
        PlagiarismResult r = compareTexts(a, b, n);
        check("No overlap -> 0% similarity", r.similarityPercent == 0.0 && r.matches.empty());
    }

    // -----------------------------------------------------------------
    // Test 2: Identical documents -> should be 100% similarity, one span
    // covering the entire document.
    // -----------------------------------------------------------------
    {
        std::string a = "Machine learning models require large amounts of training data to generalize well.";
        PlagiarismResult r = compareTexts(a, a, n);
        check("Identical documents -> 100% similarity", r.similarityPercent == 100.0);
        check("Identical documents -> exactly one merged span", r.matches.size() == 1);
        if (!r.matches.empty()) {
            check("Identical documents -> span covers all words in A",
                  r.matches[0].startInA == 0 && r.matches[0].endInA == r.totalWordsInA - 1);
        }
    }

    // -----------------------------------------------------------------
    // Test 3: Text shorter than shingle size -> zero shingles generated,
    // should NOT crash, should just report 0 matches.
    // -----------------------------------------------------------------
    {
        std::string a = "Hi there";       // only 2 words, n = 4
        std::string b = "Hello world foo bar baz";
        PlagiarismResult r = compareTexts(a, b, n);
        check("Text shorter than shingle size -> no crash, 0 matches",
              r.matches.empty() && r.similarityPercent == 0.0);
    }

    // -----------------------------------------------------------------
    // Test 4: Empty string input -> should not crash, should be 0%.
    // -----------------------------------------------------------------
    {
        std::string a = "";
        std::string b = "Some perfectly normal document text here.";
        PlagiarismResult r = compareTexts(a, b, n);
        check("Empty Document A -> no crash, 0% (not NaN/div-by-zero)",
              r.similarityPercent == 0.0 && r.totalWordsInA == 0);
    }

    // -----------------------------------------------------------------
    // Test 5: Two separate copied chunks, with different text in between
    // -> should produce TWO separate merged spans, not one incorrectly
    // joined span, and not fragmented shingle-by-shingle spans.
    // -----------------------------------------------------------------
    {
        std::string a = "Artificial intelligence is transforming industries worldwide today. "
                         "Completely unrelated filler sentence goes right here now. "
                         "Deep neural networks require significant computational resources overall.";
        std::string b = "Yesterday I read that artificial intelligence is transforming industries worldwide today, "
                         "which surprised nobody. Meanwhile, deep neural networks require significant computational "
                         "resources overall, according to the report.";
        PlagiarismResult r = compareTexts(a, b, n);
        check("Two separate copied chunks -> exactly 2 merged spans", r.matches.size() == 2);
    }

    // -----------------------------------------------------------------
    // Test 6: Case + punctuation shouldn't matter -> should still match
    // -----------------------------------------------------------------
    {
        std::string a = "Climate change is a pressing global issue";
        std::string b = "CLIMATE CHANGE, IS a pressing... global issue!!";
        PlagiarismResult r = compareTexts(a, b, n);
        check("Case/punctuation-insensitive matching", r.similarityPercent == 100.0);
    }

    std::cout << "\nAll edge case tests executed.\n";
    return 0;
}

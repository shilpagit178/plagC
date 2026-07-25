#include "matcher.hpp"
#include <iostream>
#include <string>

int main() {
    std::string docA =
        "Machine learning is a subset of artificial intelligence that "
        "focuses on building systems that learn from data. Instead of "
        "being explicitly programmed, these systems improve automatically "
        "through experience.";

    std::string docB =
        "Deep learning is a specialized field within AI. Machine learning "
        "is a subset of artificial intelligence that focuses on building "
        "systems that learn from data, and it has grown rapidly since 2010.";

    int shingleSize = DEFAULT_SHINGLE_SIZE;

    PlagiarismResult result = compareTexts(docA, docB, shingleSize);

    std::cout << "===== Plagiarism Check Result =====\n";
    std::cout << "Total words in Document A: " << result.totalWordsInA << "\n";
    std::cout << "Matched words: " << result.totalMatchedWordsInA << "\n";
    std::cout << "Similarity: " << result.similarityPercent << "%\n\n";

    std::cout << "Matched spans (word index ranges):\n";
    for (const auto& span : result.matches) {
        std::cout << "  A[" << span.startInA << ".." << span.endInA << "] "
                  << "== B[" << span.startInB << ".." << span.endInB << "] "
                  << "(" << span.wordCount << " words)\n";
    }

    return 0;
}

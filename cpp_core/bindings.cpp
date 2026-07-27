#include <pybind11/pybind11.h>
#include <pybind11/stl.h>   // needed for automatic std::vector <-> Python list conversion
#include "matcher.hpp"

namespace py = pybind11;

PYBIND11_MODULE(matcher_module, m) {
    m.doc() = "PyBind11 bindings for the plagC C++ exact-match plagiarism core";

    py::class_<MatchSpan>(m, "MatchSpan")
        .def_readwrite("startInA", &MatchSpan::startInA)
        .def_readwrite("endInA", &MatchSpan::endInA)
        .def_readwrite("startInB", &MatchSpan::startInB)
        .def_readwrite("endInB", &MatchSpan::endInB)
        .def_readwrite("wordCount", &MatchSpan::wordCount);

    py::class_<PlagiarismResult>(m, "PlagiarismResult")
        .def_readwrite("similarityPercent", &PlagiarismResult::similarityPercent)
        .def_readwrite("matches", &PlagiarismResult::matches)
        .def_readwrite("totalWordsInA", &PlagiarismResult::totalWordsInA)
        .def_readwrite("totalMatchedWordsInA", &PlagiarismResult::totalMatchedWordsInA);

    m.def("compare_texts", &compareTexts,
          "Compare two texts for exact-match plagiarism",
          py::arg("textA"), py::arg("textB"),
          py::arg("shingleSize") = DEFAULT_SHINGLE_SIZE);
}
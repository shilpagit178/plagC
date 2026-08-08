# quick script to check that the compiled C++ module actually works
# from Python before I plug it into Flask. basically doing by hand
# what I already tested manually in the python shell, but now it's
# something I can just rerun anytime instead of retyping everything

import matcher_module

def run_test(name, textA, textB, shingle_size, expected_percent):
    result = matcher_module.compare_texts(textA, textB, shingle_size)
    passed = result.similarityPercent == expected_percent
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} -> got {result.similarityPercent}%, expected {expected_percent}%")
    if not passed:
        print("    something's off here, need to check this one")
    return passed

def print_matches(result):
    # just for me to eyeball the spans, not part of pass/fail
    for m in result.matches:
        print(f"    A[{m.startInA}..{m.endInA}] == B[{m.startInB}..{m.endInB}]  ({m.wordCount} words)")


all_passed = True

# same sentence, no changes at all -> should be 100%
all_passed &= run_test(
    "identical text",
    "climate change is a serious global issue",
    "climate change is a serious global issue",
    4,
    100.0,
)

# nothing shared at all -> should be 0%
all_passed &= run_test(
    "completely different text",
    "the cat sat on the mat",
    "quantum physics is really hard to understand",
    4,
    0.0,
)

# this is the one I already ran by hand in the shell earlier,
# just making it permanent here so I don't lose it
result = matcher_module.compare_texts(
    "the quick brown fox jumps",
    "a quick brown fox jumps today",
    3,
)
print(f"[CHECK] partial overlap -> {result.similarityPercent}%")
print_matches(result)
all_passed &= (result.similarityPercent == 80.0)

# empty string shouldn't crash python either, same as it didn't crash c++
all_passed &= run_test(
    "empty document A",
    "",
    "some text that exists here",
    4,
    0.0,
)

print()
if all_passed:
    print("everything passed, bindings are working correctly")
else:
    print("something failed above, go check it before moving to flask")
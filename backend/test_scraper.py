# checks the html -> text cleaning, no internet needed
# run with:  python backend/test_scraper.py

import sys

from scraper import extract_text

failed = 0


def check(name, condition):
    global failed
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    if not condition:
        failed += 1


html = """
<html>
  <head>
    <title>My Page</title>
    <style>p { color: red; }</style>
    <script>var secret = "do not show me";</script>
  </head>
  <body>
    <nav>Home About Contact</nav>
    <h1>Big   Title</h1>
    <p>First paragraph.</p>
    <p>Second&nbsp;paragraph &amp; more.</p>
    <!-- a hidden comment -->
    <footer>Copyright someone</footer>
  </body>
</html>
"""
text = extract_text(html)
print("   got:", repr(text))

check("keeps the real text", "First paragraph." in text and "Big Title" in text)
check("decodes html entities (&amp; and &nbsp;)", "Second paragraph & more." in text)
check("drops script contents", "secret" not in text)
check("drops style contents", "color" not in text)
check("drops nav and footer", "Home About" not in text and "Copyright" not in text)
check("drops html comments", "hidden comment" not in text)
check("collapses extra whitespace", "  " not in text and "\n" not in text)
check("paragraphs don't glue together", "paragraph.Second" not in text)
check("broken html doesn't crash", extract_text("<p>unclosed <b>bold") == "unclosed bold")
check("empty html gives empty text", extract_text("") == "")

print()
if failed == 0:
    print("all scraper checks passed")
else:
    print(f"{failed} check(s) failed, look above")
    sys.exit(1)
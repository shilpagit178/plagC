from bs4 import BeautifulSoup

# tags that almost never hold the real text of a page
NOISE_TAGS = ["script", "style", "noscript", "nav", "header", "footer",
              "aside", "form", "iframe", "svg"]


def extract_text(html):
    """Take raw HTML and return just the readable text as one clean string."""
    soup = BeautifulSoup(html, "html.parser")

    # throw the junk away completely, tag and everything inside it
    for tag in soup(NOISE_TAGS):
        tag.decompose()

    # separator=" " matters: without it "<p>a</p><p>b</p>" would turn into "ab"
    text = soup.get_text(separator=" ")

    # collapse all runs of spaces, tabs and newlines into single spaces
    return " ".join(text.split())
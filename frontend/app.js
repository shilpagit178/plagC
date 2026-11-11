// plagC frontend. The server reports matches as WORD positions, so we split the
// text with the same rule as the C++ tokenizer (runs of A-Z a-z 0-9) to find where
// each word sits, then wrap matched stretches in <mark> elements.
const MAX_WORDS = 10000;

function tokens(text) {
  const out = [], re = /[A-Za-z0-9]+/g;
  let m;
  while ((m = re.exec(text))) out.push({ s: m.index, e: m.index + m[0].length });
  return out;
}

// word spans -> character ranges, sorted, with any overlap trimmed off
function rangesFor(spans, toks, startKey, endKey) {
  const list = [];
  spans.forEach((sp, id) => {
    const a = toks[sp[startKey]], b = toks[sp[endKey]];
    if (a && b) list.push({ s: a.s, e: b.e, id });
  });
  list.sort((x, y) => x.s - y.s);
  const out = [];
  for (const r of list) {
    const last = out[out.length - 1];
    if (last && r.s < last.e) { if (r.e <= last.e) continue; r.s = last.e; }
    out.push(r);
  }
  return out;
}

if (typeof document !== "undefined") {
  const $ = (id) => document.getElementById(id);
  const wc = (t) => tokens(t).length;
  let mode = "text";

  function paint(box, text, ranges) {          // text nodes + <mark>, never innerHTML
    box.replaceChildren();
    let at = 0;
    for (const r of ranges) {
      box.append(text.slice(at, r.s));
      const mk = document.createElement("mark");
      mk.className = "c" + (r.id % 6);
      mk.dataset.p = r.id;
      mk.textContent = text.slice(r.s, r.e);
      box.append(mk);
      at = r.e;
    }
    box.append(text.slice(at));
  }

  function refresh() {
    const a = wc($("a").value), b = wc($("b").value);
    $("ca").textContent = a.toLocaleString() + " words";
    $("cb").textContent = mode === "text" ? b.toLocaleString() + " words" : "";
    $("ca").classList.toggle("over", a > MAX_WORDS);
    $("cb").classList.toggle("over", mode === "text" && b > MAX_WORDS);
    const hasB = mode === "text" ? b > 0 : $("u").value.trim() !== "";
    $("go").disabled = !(a > 0 && a <= MAX_WORDS && hasB && !(mode === "text" && b > MAX_WORDS));
  }

  function setMode(m) {
    mode = m;
    $("tt").setAttribute("aria-selected", m === "text");
    $("tu").setAttribute("aria-selected", m === "url");
    $("b").hidden = m !== "text";
    $("u").hidden = m !== "url";
    $("hint").textContent = m === "text" ? "Up to 10,000 words per text."
      : "The server downloads the page and reads its text. Pages that need JavaScript to load may come back empty.";
    refresh();
  }

  function fail(msg) { const e = $("err"); e.textContent = msg; e.hidden = false; $("out").hidden = true; }

  function show(d, textA, textB) {
    const pct = d.similarityPercent;
    $("pct").textContent = Math.round(pct);
    $("out").dataset.band = pct < 15 ? "low" : pct < 40 ? "mid" : pct < 70 ? "high" : "max";
    $("verdict").textContent = pct === 0 ? "No copied passages found" : pct < 15 ? "Little overlap"
      : pct < 40 ? "Some overlap" : pct < 70 ? "Substantial overlap" : "Mostly copied";
    const n = d.matches.length, ms = d.elapsedMs + " ms engine" + (d.fetchMs != null ? ", " + d.fetchMs + " ms fetch" : "");
    $("detail").textContent = d.totalMatchedWordsInA + " of " + d.totalWordsInA + " words in your text appear in the source, in "
      + n + (n === 1 ? " passage" : " passages") + " (" + ms + ").";
    $("note").textContent = d.truncatedB ? "The page was very long, so only its first 100,000 words were compared." : "";

    const ta = tokens(textA), tb = tokens(textB), spans = d.matches;
    const okA = ta.length === d.totalWordsInA;     // safety: never highlight the wrong words
    const okB = spans.every((s) => s.endInB < tb.length);
    paint($("da"), textA, okA ? rangesFor(spans, ta, "startInA", "endInA") : []);
    paint($("db"), textB, okB ? rangesFor(spans, tb, "startInB", "endInB") : []);
    if (!okA || !okB) $("note").textContent += " Highlighting was skipped because the word counts did not line up.";

    const strip = $("strip"); strip.replaceChildren();
    if (okA) for (const r of rangesFor(spans, ta, "startInA", "endInA")) {
      const i = document.createElement("i");
      i.className = "c" + (r.id % 6);
      i.style.left = (r.s / textA.length) * 100 + "%";
      i.style.width = ((r.e - r.s) / textA.length) * 100 + "%";
      strip.append(i);
    }
    const lg = $("legend"); lg.replaceChildren();
    spans.forEach((sp, id) => {
      const li = document.createElement("li"), bt = document.createElement("button");
      bt.type = "button"; bt.className = "c" + (id % 6);
      bt.textContent = "Passage " + (id + 1) + ": " + sp.wordCount + " words";
      bt.onclick = () => jump(id);
      li.append(bt); lg.append(li);
    });
    $("err").hidden = true; $("out").hidden = false;
    $("out").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }

  function jump(id) {
    document.querySelectorAll("mark.flash").forEach((m) => m.classList.remove("flash"));
    document.querySelectorAll('mark[data-p="' + id + '"]').forEach((m) => {
      m.classList.add("flash"); m.scrollIntoView({ block: "center" });
    });
  }

  $("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const textA = $("a").value, body = { textA };
    if (mode === "text") body.textB = $("b").value; else body.urlB = $("u").value.trim();
    const btn = $("go"); btn.disabled = true; btn.classList.add("busy");
    btn.textContent = mode === "url" ? "Fetching the page..." : "Checking...";
    try {
      const res = await fetch("/api/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const d = await res.json().catch(() => null);
      if (!res.ok) return fail((d && d.error) || "The server answered with status " + res.status + ".");
      show(d, textA, mode === "text" ? body.textB : d.sourceText);
    } catch (e) {
      fail("Could not reach the server. Check that it is running, then try again.");
    } finally {
      btn.classList.remove("busy"); btn.textContent = "Check for copying"; refresh();
    }
  });

  $("tt").onclick = () => setMode("text");
  $("tu").onclick = () => setMode("url");
  ["a", "b", "u"].forEach((id) => $(id).addEventListener("input", refresh));
  $("print").onclick = () => window.print();
  $("theme").onclick = () => {
    const root = document.documentElement;
    const now = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    root.dataset.theme = now === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
  };
  $("ex").onclick = () => {
    setMode("text");
    $("a").value = "Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data. Instead of being explicitly programmed, these systems improve automatically through experience. This essay argues that data quality matters more than model size.";
    $("b").value = "Deep learning is a specialized field within AI. Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data, and it has grown rapidly since 2010. Researchers often say that data quality matters more than model size.";
    refresh();
  };
  refresh();
} else {
  module.exports = { tokens, rangesFor };
}
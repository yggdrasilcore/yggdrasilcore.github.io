#!/usr/bin/env python3
"""Yggdrasilcore home page generator.

Gathers every public repository in the organisation, classifies each one by
its GitHub topics (ignoring the `wow` and `yggdrasilcore` tags), asks a local
Ollama model for a short README summary, and renders a static GitHub Pages
site (index + one page per category + one page per repository).

The generator, its stylesheet and the summary cache live on the `web` branch;
only the hash cache is written back at the end of a run.

Runs on the standard library only.

    python3 gen_site.py --org yggdrasilcore --cache data/cache.json --out dist
"""

import argparse
import base64
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"

# Topics that carry no categorisation value: everything else on a repo is a tag.
IGNORE_TOPICS = {"wow", "yggdrasilcore"}

# Only repositories carrying this inclusion tag are listed. It is never a category.
INCLUDE_TOPIC = "yggdrasilcore"

# Repositories that are infrastructure, not projects.
IGNORE_REPOS = {".github"}

WEBSITE = "https://yggdrasilwow.com"
ORG_URL = "https://github.com/yggdrasilcore"

INTRO = [
    "Yggdrasilcore is an open-source, modular MMORPG framework for the "
    "abandonware WotLK 3.3.5a (build 12340) client, forged in the fires of "
    "World of Warcraft emulation and built to be extended.",
    "We are the team behind Yggdrasil WoW. Every project below is public, and "
    "each one traces its lineage through the emulation family tree:",
]

TREE = ["MaNGOS", "TrinityCore", "SunwellCore", "AzerothCore", "Yggdrasilcore"]

TREE_NOTE = (
    "Four generations of emulators carried the 3.3.5a flame this far. "
    "Yggdrasilcore is the branch we grow on top."
)

SYSTEM_PROMPT = (
    "You are a technical writer for the Yggdrasilcore project. "
    "Write plain, factual prose. Never use markdown, lists, or headings. "
    "Never use em dashes; use commas, colons, or periods instead."
)

USER_TMPL = (
    "Summarise this project README for a website card in 2 to 3 sentences. "
    "Say what the project is and what it does. Output only the summary.\n\n"
    "Repository: {name}\n"
    "Description: {desc}\n\n"
    "README:\n{readme}"
)

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

MODEL = "qwen3.5:4b"


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def gh(path, token):
    req = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "yggdrasilcore-home",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def list_public_repos(org, token):
    repos, page = [], 1
    while True:
        batch = gh(
            "/orgs/%s/repos?type=public&sort=updated&per_page=100&page=%d"
            % (org, page),
            token,
        )
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def get_readme(owner, name, token):
    try:
        data = gh("/repos/%s/%s/readme" % (owner, name), token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ""
        raise
    raw = data.get("content", "")
    if not raw:
        return ""
    try:
        return base64.b64decode(raw).decode("utf-8", "ignore")
    except Exception:
        return ""


def get_pages_url(owner, name, token):
    try:
        data = gh("/repos/%s/%s/pages" % (owner, name), token)
    except urllib.error.HTTPError:
        return ""
    return data.get("html_url", "")


def topics(repo):
    return {t.strip().lower() for t in (repo.get("topics") or []) if t.strip()}


def classify(repo):
    """Category list from topics, ignoring the `wow` and `yggdrasilcore` tags.

    A repository with no remaining topic is not categorised and is dropped.
    """
    return sorted(topics(repo) - IGNORE_TOPICS)


def readme_hash(text):
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:16]


def ollama_generate(model, prompt, endpoint):
    payload = {
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 220},
    }
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp).get("response", "")


def summarize(repo, readme, cats, model, endpoint, cache, budget):
    """Return (summary, used_llm).

    The cache is keyed on the repository and invalidated when the README hash
    changes or when the repository's categories no longer match the ones the
    cached summary was generated for.
    """
    key = repo["full_name"]
    digest = readme_hash(readme)
    entry = cache.get(key)
    if (
        entry
        and entry.get("readme_sha") == digest
        and entry.get("summary")
        and entry.get("categories") == cats
    ):
        return entry["summary"], False
    if not readme.strip():
        return repo.get("description") or "No README is available for this project.", False
    if budget["left"] <= 0:
        return repo.get("description") or "No summary available.", False
    budget["left"] -= 1
    prompt = USER_TMPL.format(
        name=repo["name"],
        desc=repo.get("description") or "(none)",
        readme=readme[:8000],
    )
    summary = THINK_RE.sub("", ollama_generate(model, prompt, endpoint)).strip()
    if not summary:
        summary = repo.get("description") or "No summary available."
    cache[key] = {"readme_sha": digest, "summary": summary, "categories": cats}
    return summary, True


def esc(text):
    return html.escape(text or "", quote=True)


def page(title, body, rel, active=""):
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · Yggdrasilcore</title>
<link rel="icon" href="{rel}assets/favicon.ico">
<link rel="icon" type="image/png" href="{rel}assets/favicon.png">
<link rel="stylesheet" href="{rel}assets/style.css">
</head>
<body>
<header class="topbar">
  <a class="brand" href="{rel}index.html">
    <img src="{rel}assets/favicon.png" alt="Yggdrasilcore">
    <span>Yggdrasilcore</span>
  </a>
  <nav class="nav">
    <a href="{rel}index.html"{home}>Projects</a>
    <a href="{org}" target="_blank" rel="noopener">GitHub</a>
    <a href="{site}" target="_blank" rel="noopener">Yggdrasil WoW</a>
    <button id="theme-toggle" aria-label="Toggle theme">
      <svg id="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      <svg id="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
    </button>
  </nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="foot">
  <span>© {year} Yggdrasilcore</span>
  <span>Summaries generated by {model}</span>
</footer>
<script>
(function () {{
  var key = "ygg-home-theme";
  var body = document.body;
  var sun = document.getElementById("icon-sun");
  var moon = document.getElementById("icon-moon");
  function apply(light) {{
    body.classList.toggle("light", light);
    sun.style.display = light ? "none" : "";
    moon.style.display = light ? "" : "none";
  }}
  apply(localStorage.getItem(key) === "light");
  document.getElementById("theme-toggle").addEventListener("click", function () {{
    var light = !body.classList.contains("light");
    localStorage.setItem(key, light ? "light" : "dark");
    apply(light);
  }});
}})();
</script>
</body>
</html>
""".format(
        title=esc(title),
        body=body,
        rel=rel,
        org=ORG_URL,
        site=WEBSITE,
        year=datetime.date.today().year,
        model=MODEL,
        home=' class="active"' if active == "home" else "",
    )


def repo_card(repo):
    cats = "".join(
        '<span class="chip">%s</span>' % esc(c) for c in repo["categories"]
    )
    desc = esc(repo.get("description") or "No description.")
    return """<a class="card" href="{href}">
  <div class="card-head"><span class="card-name">{name}</span>{chips}</div>
  <p class="card-desc">{desc}</p>
</a>""".format(
        href="repo-%s.html" % slugify(repo["name"]),
        name=esc(repo["name"]),
        chips=cats,
        desc=desc,
    )


def render_index(repos, categories, model):
    stats = (
        '<div class="stat-row">'
        '<div class="stat"><b>%d</b><span>projects</span></div>'
        '<div class="stat"><b>%d</b><span>categories</span></div>'
        "</div>" % (len(repos), len(categories))
    )
    tree = " → ".join('<span class="tree-node">%s</span>' % esc(t) for t in TREE)
    intro = "".join("<p>%s</p>" % esc(p) for p in INTRO)
    sections = []
    for cat in sorted(categories):
        items = "".join(repo_card(r) for r in categories[cat])
        sections.append(
            """<section class="cat">
  <h2><a href="tag-{slug}.html">{name}</a><span class="count">{n}</span></h2>
  <div class="grid">{items}</div>
</section>""".format(
                slug=slugify(cat),
                name=esc(cat),
                n=len(categories[cat]),
                items=items,
            )
        )
    body = """<section class="hero">
  <img class="logo" src="assets/logo.png" alt="Yggdrasilcore">
  <p class="eyebrow">Open-source WotLK 3.3.5a framework</p>
  <h1>Welcome to Yggdrasilcore.</h1>
  <div class="lead">{intro}</div>
  <div class="tree">{tree}</div>
  <p class="tree-note">{note}</p>
  <div class="cta-row">
    <a class="cta primary" href="{site}" target="_blank" rel="noopener">Play on Yggdrasil WoW</a>
    <a class="cta" href="{org}" target="_blank" rel="noopener">View on GitHub</a>
  </div>
  {stats}
</section>
{sections}""".format(
        intro=intro,
        tree=tree,
        note=esc(TREE_NOTE),
        site=WEBSITE,
        org=ORG_URL,
        stats=stats,
        sections="".join(sections),
    )
    return page("Projects", body, "", "home")


def render_tag(cat, repos):
    items = "".join(repo_card(r) for r in repos)
    body = """<a class="back" href="index.html">back</a>
<section class="cat-head">
  <h1>{name}</h1>
  <p>{n} project(s) tagged <span class="chip">{name}</span></p>
</section>
<div class="grid">{items}</div>""".format(
        name=esc(cat), n=len(repos), items=items
    )
    return page(cat, body, "")


def render_repo(repo):
    links = ['<a class="cta" href="%s" target="_blank" rel="noopener">Source</a>'
             % esc(repo["html_url"])]
    if "addons" in repo["categories"]:
        links.append(
            '<a class="cta primary" href="%s" target="_blank" rel="noopener">'
            "Download (.zip)</a>" % esc(repo["zip_url"])
        )
    elif repo.get("pages_url"):
        links.append(
            '<a class="cta primary" href="%s" target="_blank" rel="noopener">'
            "Documentation</a>" % esc(repo["pages_url"])
        )
    chips = "".join(
        '<a class="chip" href="tag-%s.html">%s</a>' % (slugify(c), esc(c))
        for c in repo["categories"]
    )
    body = """<a class="back" href="index.html">back</a>
<article class="repo">
  <h1>{name}</h1>
  {chips}
  <p class="repo-desc">{desc}</p>
  <div class="summary">{summary}</div>
  <div class="cta-row">{links}</div>
</article>""".format(
        name=esc(repo["name"]),
        chips=chips,
        desc=esc(repo.get("description") or ""),
        summary=esc(repo["summary"]),
        links="".join(links),
    )
    return page(repo["name"], body, "")


def load_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default="yggdrasilcore")
    parser.add_argument("--cache", default="data/cache.json")
    parser.add_argument("--out", default="dist")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--endpoint", default="http://localhost:11434")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    global MODEL
    MODEL = args.model

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

    cache = load_cache(args.cache)
    budget = {"left": args.limit if args.limit > 0 else 10 ** 9}

    repos = [r for r in list_public_repos(args.org, token)
             if not r["name"] in IGNORE_REPOS and not r["name"].startswith(".")]
    print("Discovered %d public repositories" % len(repos), file=sys.stderr)

    categories = {}
    prepared = []
    kept = set()
    llm_calls = 0
    for repo in sorted(repos, key=lambda r: r["name"].lower()):
        if INCLUDE_TOPIC not in topics(repo):
            print("Skipping %s (missing %s tag)" % (repo["name"], INCLUDE_TOPIC),
                  file=sys.stderr)
            continue
        cats = classify(repo)
        if not cats:
            print("Skipping %s (no topics)" % repo["name"], file=sys.stderr)
            continue
        kept.add(repo["full_name"])
        readme = get_readme(args.org, repo["name"], token)
        summary, used = summarize(
            repo, readme, cats, args.model, args.endpoint, cache, budget
        )
        llm_calls += int(used)
        prepared.append(
            {
                "name": repo["name"],
                "description": repo.get("description"),
                "html_url": repo["html_url"],
                "zip_url": "%s/archive/refs/heads/%s.zip"
                % (repo["html_url"], repo.get("default_branch", "main")),
                "pages_url": get_pages_url(args.org, repo["name"], token)
                if repo.get("has_pages")
                else "",
                "summary": summary,
                "categories": cats,
            }
        )
        for cat in cats:
            categories.setdefault(cat, []).append(prepared[-1])

    for stale in [k for k in cache if k not in kept]:
        del cache[stale]
    print("LLM summaries generated: %d" % llm_calls, file=sys.stderr)

    if os.path.isdir(args.out):
        shutil.rmtree(args.out)
    shutil.copytree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
                    os.path.join(args.out, "assets"))

    def write(name, content):
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as handle:
            handle.write(content)

    write("index.html", render_index(prepared, categories, args.model))
    for cat, items in categories.items():
        write("tag-%s.html" % slugify(cat), render_tag(cat, items))
    for repo in prepared:
        write("repo-%s.html" % slugify(repo["name"]), render_repo(repo))

    cache["generated"] = datetime.datetime.utcnow().isoformat(timespec="seconds")
    with open(args.cache, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, sort_keys=True)
    print("Site written to %s" % args.out, file=sys.stderr)


if __name__ == "__main__":
    main()

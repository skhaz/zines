#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = ["jinja2>=3.1.6"]
# ///
import html
import json
import os
import re
import subprocess
import urllib.parse
from datetime import date

from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
COLLECTIONS = [
    ("portuguese", "BRAZILIAN", "br"),
    ("english", "ENGLISH", "en"),
]
TODAY = date.today().strftime("%Y-%m-%d")
REPO_URL = "https://github.com/skhaz/zines"
SITE_URL = "https://skhaz.github.io/zines"
FEED_MAX = 30

GITHUB_PIX = """00000000111100000000
00000111111111100000
00001111111111110000
00011111111111111000
00111011111111011100
01110000000000011110
01111000000000011110
11110000000000001111
11110000000000001111
11110000000000001111
11110000000000001111
11110000000000001111
11110000000000001111
01111000000000011110
01101110000001111110
01110111000011111100
00110000000011111100
00011100000011111000
00001110000011110000
00000010000001000000""".splitlines()


def _build_gh_svg():
    n = len(GITHUB_PIX)
    rects = []
    for y, row in enumerate(GITHUB_PIX):
        for x, c in enumerate(row):
            if c == "1":
                rects.append('<rect x="{}" y="{}" width="1" height="1"/>'.format(x, y))

    return (
        '<svg class="ghpix" viewBox="0 0 {n} {n}" fill="currentColor" '
        'shape-rendering="crispEdges" aria-hidden="true">{}</svg>'
    ).format("".join(rects), n=n)


GH_SVG = _build_gh_svg()
REPO_LINK = '<a class="repo" href="{}" target="_blank" rel="noopener">{} source</a>'.format(
    REPO_URL, GH_SVG
)

ANSI_FG = {
    30: "#1a1a1a", 31: "#c40000", 32: "#00a400", 33: "#a48a00",
    34: "#2222dd", 35: "#b300b3", 36: "#00a4a4", 37: "#b0b0b0",
}
ANSI_FG_BRIGHT = {
    30: "#555555", 31: "#ff5555", 32: "#55ff55", 33: "#ffff55",
    34: "#5599ff", 35: "#ff55ff", 36: "#55ffff", 37: "#ffffff",
}
ANSI_BG = {
    40: "#000000", 41: "#7a0000", 42: "#006600", 43: "#6a5500",
    44: "#000077", 45: "#700070", 46: "#006666", 47: "#9a9a9a",
}
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
CSI_OTHER_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-ln-z]")


def has_ansi(text):
    return SGR_RE.search(text) is not None


def ansi_to_html(text):
    text = CSI_OTHER_RE.sub("", text)
    fg = bg = None
    bold = False
    parts = []
    idx = 0

    def emit(chunk):
        if not chunk:
            return

        seg = html.escape(chunk, quote=False)
        styles = []
        if fg is not None:
            styles.append("color:" + (ANSI_FG_BRIGHT if bold else ANSI_FG)[fg])
        elif bold:
            styles.append("font-weight:bold")

        if bg is not None:
            styles.append("background:" + ANSI_BG[bg])

        if styles:
            parts.append('<span style="' + ";".join(styles) + '">' + seg + "</span>")
        else:
            parts.append(seg)

    for m in SGR_RE.finditer(text):
        emit(text[idx:m.start()])
        idx = m.end()
        codes = [int(c) for c in m.group(1).split(";") if c != ""] or [0]
        for c in codes:
            if c == 0:
                fg = bg = None
                bold = False
            elif c == 1:
                bold = True
            elif c == 22:
                bold = False
            elif 30 <= c <= 37:
                fg = c
            elif c == 39:
                fg = None
            elif 40 <= c <= 47:
                bg = c
            elif c == 49:
                bg = None
            elif 90 <= c <= 97:
                fg = c - 60
                bold = True
            elif 100 <= c <= 107:
                bg = c - 60

    emit(text[idx:])
    return "".join(parts)


def natkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def uenc(seg):
    return urllib.parse.quote(seg, safe="")


def uenc_path(rel):
    parts = rel.replace(os.sep, "/").split("/")
    return "/".join(uenc(p) for p in parts)


def site_url(abs_path):
    return SITE_URL + "/" + uenc_path(os.path.relpath(abs_path, ROOT))


def href_for(link_dir, current_dir):
    target = os.path.join(link_dir, "index.html")
    rel = os.path.relpath(target, current_dir)
    return uenc_path(rel)


def rel_root(dirpath):
    rel = os.path.relpath(dirpath, ROOT)
    if rel == ".":
        return ""

    return "../" * len(rel.split(os.sep))


def strip_outer_pre(text):
    t = text
    t = re.sub(r"^\s*<pre[^>]*>\s*", "", t)
    t = re.sub(r"\s*</pre>\s*$", "", t)
    return t


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def txt_files(folder):
    return sorted(
        [f for f in os.listdir(folder) if f.endswith(".txt") and not f.endswith(".orig")],
        key=natkey,
    )


def count_txt(folder):
    n = 0
    for _base, _dirs, files in os.walk(folder):
        for f in files:
            if f.endswith(".txt") and not f.endswith(".orig"):
                n += 1

    return n


def git_date(rel_path):
    try:
        out = subprocess.run(
            [
                "git", "log", "-1", "--format=%cI", "--",
                rel_path,
                ":(exclude,glob){}/**/*.html".format(rel_path),
                ":(exclude){}/*.html".format(rel_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def trail_for(abs_path, coll_label, zpath, zine):
    trail = [(coll_label, ROOT), (zine, zpath)]
    rel = os.path.relpath(abs_path, zpath)
    if rel != ".":
        comps = rel.split(os.sep)[:-1]
        cur = zpath
        for c in comps:
            cur = os.path.join(cur, c)
            trail.append((c, cur))

    return trail


env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=False,
    keep_trailing_newline=False,
)
env.filters["esc"] = lambda s: html.escape(str(s), quote=False)
env.globals["crumbs"] = env.get_template("crumbs.html.j2").module.crumbs


def trail_ctx(trail, current_dir):
    return [{"label": label, "href": href_for(ldir, current_dir)} for label, ldir in trail]


def shell_ctx(doc_title, dirpath):
    rr = rel_root(dirpath)
    return {
        "doc_title": doc_title,
        "css": rr + "style.css",
        "home": rr + "index.html",
        "root": rr,
        "repo_link": REPO_LINK,
        "today": TODAY,
    }


def render_folder(dirpath, trail):
    name = os.path.basename(dirpath)
    entries = os.listdir(dirpath)
    dirs = sorted([d for d in entries if os.path.isdir(os.path.join(dirpath, d))], key=natkey)
    files = txt_files(dirpath)
    dir_rows = [
        {
            "href": uenc(d) + "/index.html",
            "name": d,
            "count": count_txt(os.path.join(dirpath, d)),
        }
        for d in dirs
    ]
    file_rows = [
        {
            "href": uenc(os.path.splitext(f)[0]) + ".html",
            "name": f,
            "size": os.path.getsize(os.path.join(dirpath, f)),
        }
        for f in files
    ]
    return env.get_template("folder.html.j2").render(
        name=name,
        root_href=href_for(ROOT, dirpath),
        trail=trail_ctx(trail, dirpath),
        dirs=dir_rows,
        files=file_rows,
        **shell_ctx("{} :: ZINES".format(name), dirpath),
    )


def render_content(txt_path, trail, prev_stem, next_stem):
    name = os.path.basename(txt_path)
    stem = os.path.splitext(name)[0]
    dirpath = os.path.dirname(txt_path)
    raw = read_text(txt_path)
    is_html = re.match(r"^\s*<html", raw, re.IGNORECASE) is not None
    text = strip_outer_pre(raw)
    ansi = has_ansi(text)
    orig = name + ".orig"
    return env.get_template("content.html.j2").render(
        stem=stem,
        is_html=is_html,
        ansi=ansi,
        text=text,
        text_html=ansi_to_html(text) if ansi else None,
        raw_href=uenc(name),
        orig_href=uenc(orig) if os.path.exists(os.path.join(dirpath, orig)) else None,
        prev_href=uenc(prev_stem) + ".html" if prev_stem else None,
        next_href=uenc(next_stem) + ".html" if next_stem else None,
        root_href=href_for(ROOT, dirpath),
        trail=trail_ctx(trail, dirpath),
        **shell_ctx("{} :: ZINES".format(stem), dirpath),
    )


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def walk_coll(coll_dir, coll_label, pages, articles):
    croot = os.path.join(ROOT, coll_dir)
    nzines = nfiles = 0
    if not os.path.isdir(croot):
        return 0, 0

    for zine in sorted(os.listdir(croot), key=natkey):
        zpath = os.path.join(croot, zine)
        if not os.path.isdir(zpath):
            continue

        nzines += 1
        for base, dirs, _files in os.walk(zpath):
            dirs.sort(key=natkey)
            rel = os.path.relpath(base, zpath)
            if rel == ".":
                btrail = [(coll_label, ROOT)]
            else:
                btrail = trail_for(base, coll_label, zpath, zine)
            out = os.path.join(base, "index.html")
            write(out, render_folder(base, btrail))
            pages.append(out)

        for base, _dirs, _files in os.walk(zpath):
            siblings = txt_files(base)
            for i, f in enumerate(siblings):
                nfiles += 1
                fp = os.path.join(base, f)
                out = os.path.join(base, os.path.splitext(f)[0] + ".html")
                ftrail = trail_for(fp, coll_label, zpath, zine)
                prev_stem = os.path.splitext(siblings[i - 1])[0] if i > 0 else None
                next_stem = (
                    os.path.splitext(siblings[i + 1])[0] if i + 1 < len(siblings) else None
                )
                write(out, render_content(fp, ftrail, prev_stem, next_stem))
                pages.append(out)
                articles.append(uenc_path(os.path.relpath(out, ROOT)))

    return nzines, nfiles


def collect():
    sections = []
    stats = {}
    grand_zines = grand_files = 0
    for coll_dir, label, code in COLLECTIONS:
        croot = os.path.join(ROOT, coll_dir)
        if not os.path.isdir(croot):
            continue

        rows = []
        czines = cfiles = 0
        for zine in sorted(os.listdir(croot), key=natkey):
            zpath = os.path.join(croot, zine)
            if not os.path.isdir(zpath):
                continue

            czines += 1
            cnt = count_txt(zpath)
            cfiles += cnt
            rows.append(
                {
                    "href": uenc(coll_dir) + "/" + uenc(zine) + "/index.html",
                    "name": zine,
                    "count": cnt,
                    "path": os.path.join(coll_dir, zine),
                    "url": site_url(zpath),
                }
            )

        grand_zines += czines
        grand_files += cfiles
        stats[coll_dir] = {"titles": czines, "files": cfiles}
        sections.append(
            {
                "dir": coll_dir,
                "label": label,
                "code": code,
                "titles": czines,
                "files": cfiles,
                "rows": rows,
            }
        )

    return sections, stats, grand_zines, grand_files


def render_root(sections, grand_zines, grand_files):
    return env.get_template("root.html.j2").render(
        grand_zines=grand_zines,
        grand_files=grand_files,
        sections=sections,
        **shell_ctx("ZINES :: underground e-zine archive", ROOT),
    )


def render_readme(sections, stats):
    return env.get_template("readme.md.j2").render(colls=sections, stats=stats)


def render_sitemap(pages):
    urls = [SITE_URL + "/"] + [site_url(p) for p in pages]
    return env.get_template("sitemap.xml.j2").render(urls=urls)


def render_feed(sections):
    entries = []
    for s in sections:
        for row in s["rows"]:
            updated = git_date(row["path"])
            if updated:
                entries.append({"title": row["name"], "url": row["url"], "updated": updated})

    entries.sort(key=lambda e: e["updated"], reverse=True)
    entries = entries[:FEED_MAX]
    updated = entries[0]["updated"] if entries else TODAY + "T00:00:00Z"
    return env.get_template("feed.xml.j2").render(site=SITE_URL, updated=updated, entries=entries)


def main():
    pages = []
    articles = []
    nz = nf = 0
    for coll_dir, label, _code in COLLECTIONS:
        a, b = walk_coll(coll_dir, label, pages, articles)
        nz += a
        nf += b

    sections, stats, grand_zines, grand_files = collect()
    root_out = os.path.join(ROOT, "index.html")
    write(root_out, render_root(sections, grand_zines, grand_files))
    pages.append(root_out)
    write(os.path.join(ROOT, "README.md"), render_readme(sections, stats))
    write(os.path.join(ROOT, "sitemap.xml"), render_sitemap(pages))
    write(os.path.join(ROOT, "feed.xml"), render_feed(sections))
    write(os.path.join(ROOT, "random.json"), json.dumps(articles, separators=(",", ":")))
    print("built {} zines, {} text files rendered.".format(nz, nf))


if __name__ == "__main__":
    main()

"""把 gaigezong.com 书籍（目录页 + 各章节页）下载并转换为单个简体中文 Markdown。

依赖：pip install requests beautifulsoup4 opencc-python-reimplemented
用法：python gaigezong_to_md.py <目录页URL> [-o 输出目录] [--no-zhe]
"""
import argparse
import collections
import hashlib
import os
import re
import sys
import tempfile
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from opencc import OpenCC

BLOCK_TAGS = ("p", "div", "h1", "h2", "h3", "h4", "blockquote", "table", "ul", "ol")
INLINE_OK = ("span", "font", "a", "u", "sup", "sub", "p", "div", "td", "th", "li")
# 「著」读 zhù 的常见词，其余转为「着」
ZHU_PREFIX = "显昭卓名原编巨论专土拙遗合"
ZHU_SUFFIX = "作墨名述书者"

cc = OpenCC("t2s")
unknown_tags = collections.Counter()
tables = []


def fetch(url, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, re.sub(r"[^\w.]", "_", url.rsplit("/", 1)[-1] or "index.htm"))
    if not os.path.exists(path):
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
    with open(path, "rb") as f:
        raw = f.read()
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:2048], re.I)
    enc = m.group(1).decode().lower() if m else "utf-8"
    if enc in ("gb2312", "gbk"):
        enc = "gb18030"
    return BeautifulSoup(raw.decode(enc, errors="replace"), "html.parser")


def clean_text(s):
    s = s.replace("\r", "")
    # 源码中折行：中文之间直接拼接，其余换成空格
    s = re.sub(r"(?<=[^\x00-\x7f])[ \t]*\n[ \t]*(?=[^\x00-\x7f])", "", s)
    return re.sub(r"[ \t]*\n[ \t]*", " ", s)


def table_to_md(table):
    rows, width = [], 0
    for tr in table.find_all("tr"):
        cells = [inline(c).replace("\n", " ").replace("|", "\\|").strip() for c in tr.find_all(["td", "th"])]
        width = max(width, len(cells))
        rows.append(cells)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + "---|" * width)
    tables.append("\n".join(lines))
    return f"\n\x00TABLE{len(tables) - 1}\x00\n"


def inline(node):
    if isinstance(node, NavigableString):
        return clean_text(str(node))
    if not isinstance(node, Tag):
        return ""
    name = node.name
    if name == "table":
        return table_to_md(node)
    if name == "br":
        return "\n"
    inner = "".join(inline(c) for c in node.children)
    if name in ("strong", "b"):
        return f"**{inner.strip()}**" if inner.strip() else inner
    if name in ("em", "i"):
        return f"*{inner.strip()}*" if inner.strip() else inner
    if name not in INLINE_OK:
        unknown_tags[name] += 1
    if name in BLOCK_TAGS or name == "li":
        return f"\n{inner}\n"
    return inner


def body_to_blocks(container):
    blocks = []
    for line in inline(container).split("\n"):
        m = re.fullmatch(r"\s*\x00TABLE(\d+)\x00\s*", line)
        if m:
            blocks.append(tables[int(m.group(1))])
        elif line.strip():
            blocks.append(line.rstrip().lstrip(" "))
    return blocks


def find_body(soup):
    cands = soup.find_all("td", class_="style16xi_hui")
    if not cands:
        # 兜底：选直接包含 <p> 最多的元素
        cands = [max(soup.find_all(["td", "div"]), key=lambda t: len(t.find_all("p", recursive=False)))]
    return max(cands, key=lambda t: len(t.get_text()))


def norm(s):
    return re.sub(r"[\s\u3000]", "", s)


def fix_zhe(md):
    md = re.sub(f"([{ZHU_PREFIX}])著", r"\1" + "\x01", md)
    md = re.sub(f"著(?![{ZHU_SUFFIX}])", "着", md)
    return md.replace("\x01", "著")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("index_url", help="书籍目录页，例如 https://gaigezong.com/jiejing/xiduyifusuo/index.htm")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录（默认当前目录）")
    ap.add_argument("--cache", help="网页缓存目录（默认系统临时目录）")
    ap.add_argument("--no-zhe", action="store_true", help="不把「著」转为「着」")
    args = ap.parse_args()

    cache = args.cache or os.path.join(tempfile.gettempdir(), "gaigezong_cache",
                                       hashlib.md5(args.index_url.encode()).hexdigest()[:10])
    index = fetch(args.index_url, cache)

    title_el = index.find(class_="style22xi_jin")
    title = title_el.get_text(strip=True) if title_el else index.title.get_text(strip=True)
    author_el = index.find(lambda t: t.name == "td" and "作者" in t.get_text() and not t.find("td"))
    author = re.sub(r"\s+", " ", author_el.get_text(" ", strip=True)) if author_el else ""

    links, seen = [], set()
    for a in index.find_all("a", href=True):
        href, text = a["href"].strip(), a.get_text(strip=True)
        if (not text or "/" in href or ":" in href or href in seen or href.startswith("index.")
                or not re.search(r"\.html?$", href)):
            continue
        seen.add(href)
        links.append((href, text))
    if not links:
        sys.exit("目录页中未找到章节链接")

    parts = [f"# {title}", ""]
    if author:
        parts += [author, ""]
    parts += [f"來源：{args.index_url}", "", "## 目錄", ""]
    parts += [f"{i}. [{text}](#ch-{i})" for i, (_, text) in enumerate(links, 1)]
    parts.append("")

    for i, (href, toc_title) in enumerate(links, 1):
        soup = fetch(urljoin(args.index_url, href), cache)
        title_td = soup.find(class_="style20xi_jin")
        if title_td and norm(title_td.get_text()) != norm(toc_title):
            print(f"[标题不一致] {href}: 页面='{title_td.get_text(' ', strip=True)}' 目录='{toc_title}'")
        blocks = body_to_blocks(find_body(soup))
        parts += [f'<a id="ch-{i}"></a>', "", f"## {toc_title}", ""]
        for b in blocks:
            parts += [b, ""]
        print(f"{href}: {len(blocks)} 段, {sum(len(b) for b in blocks)} 字")

    md = cc.convert("\n".join(parts))
    if not args.no_zhe:
        md = fix_zhe(md)
    for m in sorted(set(re.findall(r".著.", md))):
        print("保留「著」:", m)
    if unknown_tags:
        print("未处理的标签（内容已按纯文本保留）:", dict(unknown_tags))

    out = os.path.join(args.outdir, re.sub(r'[\\/:*?"<>|]', "_", cc.convert(title)) + ".md")
    os.makedirs(args.outdir, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    print("已写入:", out)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

# -*- coding: utf-8 -*-
"""公認会計士・監査審査会サイトから短答式試験の過去問PDFのマニフェストを作る。"""
import json, re, time, urllib.request, urllib.parse

BASE = "https://www.fsa.go.jp"
INDEX = BASE + "/cpaaob/kouninkaikeishi-shiken/kakoshiken.html"
UA = {"User-Agent": "Mozilla/5.0 (compatible; personal-study-archive/1.0)"}

_cache = {}

def get(url):
    if url in _cache:
        return _cache[url]
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            html = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        html = raw.decode("utf-8", "replace")
    _cache[url] = html
    time.sleep(0.7)          # 相手サーバに負荷をかけない
    return html

LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
TAG = re.compile(r"<[^>]+>")

def links(html, base):
    out = []
    for href, text in LINK.findall(html):
        txt = TAG.sub("", text)
        txt = re.sub(r"\s+", " ", txt).strip()
        out.append((urllib.parse.urljoin(base, href), txt))
    return out


def main():
    idx = get(INDEX)
    # 年度別ページ (…shiken.html)
    years = []
    for url, txt in links(idx, INDEX):
        if re.search(r"/cpaaob/kouninkaikeishi-shiken/[^/]*shiken\.html$", url) and "試験" in txt:
            if (url, txt) not in years:
                years.append((url, txt))
    print(f"year pages: {len(years)}")

    sessions = []
    for yurl, ytxt in years:
        try:
            yhtml = get(yurl)
        except Exception as e:
            print("  !! year page failed", yurl, e)
            continue
        for url, txt in links(yhtml, yurl):
            if not url.lower().endswith(".html"):
                continue
            if "tantou" not in url and "短答" not in txt:
                continue
            kind = None
            if "問題" in txt or "mondai" in url:
                kind = "mondai"
            elif "正解" in txt or "seikai" in url:
                kind = "seikai"
            elif "合格" in txt or "gokaku" in url or "goukaku" in url:
                kind = "gokaku"
            if kind:
                sessions.append({"year_page": yurl, "year_label": ytxt,
                                 "url": url, "text": txt, "kind": kind})

    # 重複除去
    seen, uniq = set(), []
    for s in sessions:
        if s["url"] not in seen:
            seen.add(s["url"])
            uniq.append(s)
    print(f"tantou pages: {len(uniq)}  "
          f"(mondai={sum(1 for s in uniq if s['kind']=='mondai')}, "
          f"seikai={sum(1 for s in uniq if s['kind']=='seikai')}, "
          f"gokaku={sum(1 for s in uniq if s['kind']=='gokaku')})")

    # 各ページ内の PDF を収集
    for s in uniq:
        try:
            h = get(s["url"])
        except Exception as e:
            print("  !! page failed", s["url"], e)
            s["pdfs"] = []
            continue
        pdfs = [{"url": u, "text": t} for u, t in links(h, s["url"])
                if u.lower().endswith(".pdf")]
        s["pdfs"] = pdfs
        print(f"  {s['kind']:7s} {s['text'][:40]:42s} pdfs={len(pdfs)}")

    with open("kakomon_manifest.json", "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)
    print("total pdfs:", sum(len(s["pdfs"]) for s in uniq))


if __name__ == "__main__":
    main()

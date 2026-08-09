# -*- coding: utf-8 -*-
"""教材PDFから A/B 論点ごとの本文を切り出す。

ab_data.json の並び（科目・巻・頁）を正とし、同じ頁で見つかったマーカーを
順番に対応づける。マーカー間のテキストがその論点の本文。
"""
import json, re, sys, collections
from pdfminer.high_level import extract_text

# ファイル名の Unicode 正規化差で直指定が外れることがあるので、glob で解決する
import glob, unicodedata
PATTERNS = {"기업법": "企業法", "감사론": "監査論",
            "재무회계론(이론)": "財務会計論", "관리회계론": "管理会計論"}


def find_book(subject, vol):
    head = unicodedata.normalize("NFC", PATTERNS[subject])
    n = vol[0]
    for f in glob.glob("*.pdf"):
        g = unicodedata.normalize("NFC", f)
        if g.startswith(head) and re.search(r"_" + n + r"_", g):
            return f
    return None

# 一般書：〔短答：A 論文：X〕 ／ 管理会計論レジュメ：重要度A
# ab_data.json は A/B しか持たないが、教材には C 等もある。
# 本文の切れ目には全等級を使い、対応づけには A/B だけを使う。
MARKER = re.compile(
    r"[〔\[]\s*短\s*答\s*[:：]\s*([A-DＡ-Ｄ])[^\]〕]*?論\s*文\s*[:：]\s*[A-DＡ-Ｄ]\s*[〕\]]"
    r"|重\s*要\s*度\s*[\s:：]*([A-DＡ-Ｄ])")

FULL2HALF = str.maketrans("ＡＢＣＤ", "ABCD")


def grade_of(m):
    g = m.group(1) or m.group(2) or ""
    return g.translate(FULL2HALF)

MAXBODY = 1500          # 次のマーカーが遠すぎるときの打ち切り


def pages_of(path):
    txt = extract_text(path)
    return txt.split("\f")


def main():
    ab = json.load(open("ab_data.json", encoding="utf-8"))
    by_book = collections.defaultdict(list)
    for i, t in enumerate(ab):
        by_book[(t["subject"], t["vol"])].append((i, t))

    bodies = [""] * len(ab)
    stats = []
    for key in sorted(by_book, key=lambda k: (k[0], k[1])):
        path = find_book(*key)
        if not path:
            print("  !! no pdf for", key); continue
        pages = pages_of(path)
        items = by_book[key]

        # ab_data 側：頁 → その頁の論点（教材の並び順）
        want = collections.defaultdict(list)
        for i, t in items:
            want[t["page"]].append(i)

        ok = miss = 0
        for pno, idxs in want.items():
            page = pages[pno - 1] if 0 < pno <= len(pages) else ""
            nxt = pages[pno] if pno < len(pages) else ""
            hits = list(MARKER.finditer(page))
            ab_hits = [k for k, m in enumerate(hits) if grade_of(m) in ("A", "B")]
            if len(ab_hits) != len(idxs):
                miss += len(idxs)
                continue
            for k, i in zip(ab_hits, idxs):
                start = hits[k].end()
                end = hits[k + 1].start() if k + 1 < len(hits) else len(page)
                body = page[start:end]
                if k + 1 == len(hits):            # 頁をまたぐ分を少し足す
                    m = MARKER.search(nxt)
                    body += "\n" + (nxt[:m.start()] if m else nxt[:MAXBODY])
                bodies[i] = re.sub(r"\s+", " ", body)[:MAXBODY].strip()
                ok += 1
        stats.append((key, len(items), ok, miss))
        print(f"  {key[0]:14s} {key[1]}  {ok:5d}/{len(items):5d} 本文取得"
              f"（頁のマーカー数が合わず飛ばした {miss}）", flush=True)

    got = sum(1 for b in bodies if len(b) > 40)
    print(f"\n本文が取れた論点 {got}/{len(ab)} ({got/len(ab)*100:.0f}%)")
    lens = [len(b) for b in bodies if b]
    if lens:
        lens.sort()
        print(f"本文の長さ 中央値 {lens[len(lens)//2]} / 最大 {lens[-1]}")
    json.dump(bodies, open("topic_bodies.json", "w", encoding="utf-8"),
              ensure_ascii=False)

    print("\n--- 見本 ---")
    for i in (0, 1200, 2600, 4300):
        if bodies[i]:
            print(f"[{ab[i]['subject']} {ab[i]['grade']}] {ab[i]['heading'][:30]}")
            print("   ", bodies[i][:150], "\n")


if __name__ == "__main__":
    main()

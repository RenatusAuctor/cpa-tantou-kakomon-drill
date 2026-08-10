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

MAXBODY = 5000          # 次のマーカーが遠すぎるときの打ち切り
LOOKAHEAD = 6           # マーカーが見つかるまで先の頁を何枚たどるか

# 本文に紛れ込む柱（ページ上部の章・節見出し）・頁番号・製版コード
NOISE = [
    re.compile(r"^\s*第\s*[０-９0-9]+\s*[章節][^\n]{0,30}$"),
    re.compile(r"^\s*[０-９0-9]{1,4}\s*$"),
    re.compile(r"^\s*[ＭM]\s*\d\s*[―ー\-]\s*\d+\s*$"),
    re.compile(r"^\s*[A-Z]{2,6}\d*\.indd\b.*$"),
    re.compile(r"^\s*\d{6}\s*$"),
]


def strip_noise(text):
    out = []
    for ln in text.split("\n"):
        if any(p.match(ln) for p in NOISE):
            continue
        out.append(ln)
    return "\n".join(out)


# 末尾に残りやすい「次の見出し」のかたち：第○章／１．／（１）／①
HEAD_TAIL = re.compile(
    r"\s(?:第\s*[０-９0-9]+\s*[章節]|[０-９0-9]{1,2}\s*[．.]|"
    r"[（(]\s*[０-９0-9ⅰ-ⅹⅰ-ⅹa-zａ-ｚ]{1,3}\s*[）)]|[①-⑳])"
    r"\s*[^\s。]{0,24}\s*$")
# 図表の通し番号（－ ①－2－3 － ( 10 ) のたぐい）
FIGNO = re.compile(r"－\s*[①-⑳]?[－\-\d\s]{1,12}－|[（(]\s*\d{1,3}\s*[）)]\s*$")


def drop_heading_by_name(b, heading):
    """次の論点の見出しが末尾にそのまま来ている場合に削る。"""
    if not heading:
        return b
    want = re.sub(r"\s+", "", heading)
    if not want:
        return b
    tail = re.sub(r"\s+", "", b[-(len(want) + 12):])
    if not tail.endswith(want):
        return b
    cut, seen = len(b), 0
    while cut > 0 and seen < len(want):
        cut -= 1
        if not b[cut].isspace():
            seen += 1
    return b[:cut].rstrip()


# 図がテキスト化されたときの残骸。数字を壊さないよう、記号の並びだけを対象にする
# （(.)\1{2,} のような一般化は「10000」を「10」にしてしまうので使わない）
SYMRUN = re.compile(r"(?:\s[‘’“”~＿｜|［］\[\]{}／＼^]{1,3}){2,}")


def strip_figure_junk(b):
    return re.sub(r"\s{2,}", " ", SYMRUN.sub(" ", b))


def trim_tail(body, next_heading):
    """末尾に紛れ込む見出し・図表番号を落とす。"""
    b = strip_figure_junk(FIGNO.sub(" ", body)).rstrip()
    b = drop_heading_by_name(b, next_heading)
    # 見出しの形をした断片が続くかぎり削る（「２．法人性 （１） 法人格の制度」など）
    for _ in range(4):
        nb = HEAD_TAIL.sub("", b).rstrip()
        if nb == b:
            break
        b = nb
    b = re.sub(r"\s{2,}", " ", b)
    return b.strip()


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
            hits = list(MARKER.finditer(page))
            ab_hits = [k for k, m in enumerate(hits) if grade_of(m) in ("A", "B")]
            if len(ab_hits) != len(idxs):
                miss += len(idxs)
                continue
            for k, i in zip(ab_hits, idxs):
                start = hits[k].end()
                if k + 1 < len(hits):                    # 同じ頁に次のマーカーがある
                    body = page[start:hits[k + 1].start()]
                else:
                    # 次のマーカーが出るまで頁をまたいで拾う（数頁続く論点がある）
                    body = page[start:]
                    for j in range(pno, min(pno + LOOKAHEAD, len(pages))):
                        nxt = pages[j]
                        m = MARKER.search(nxt)
                        if m:
                            body += "\n" + nxt[:m.start()]
                            break
                        body += "\n" + nxt
                        if len(body) > MAXBODY:
                            break
                body = strip_noise(body)
                body = re.sub(r"[ \t　]+", " ", body)
                body = re.sub(r"\n{2,}", "\n", body).replace("\n", " ")
                body = re.sub(r"\s{2,}", " ", body)
                if len(body) > MAXBODY:                  # 切るなら文の切れ目で
                    cut = body.rfind("。", 0, MAXBODY)
                    body = body[:cut + 1] if cut > MAXBODY * 0.5 else body[:MAXBODY]
                nh = ab[idxs[idxs.index(i) + 1]]["heading"] \
                    if idxs.index(i) + 1 < len(idxs) else ""
                bodies[i] = trim_tail(body, nh)
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

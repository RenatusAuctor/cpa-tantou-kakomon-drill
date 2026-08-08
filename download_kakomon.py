# -*- coding: utf-8 -*-
"""マニフェストから短答式の試験問題・答案用紙・正解PDFを 과거문/ に落とす。"""
import json, os, re, time, urllib.request, collections

UA = {"User-Agent": "Mozilla/5.0 (compatible; personal-study-archive/1.0)"}
OUT = "과거문"
SUBJECTS = ["企業法", "管理会計論", "監査論", "財務会計論"]

KANSUJI = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13,
           "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18,
           "十九": 19, "二十": 20, "二十一": 21, "二十二": 22}


def norm_digits(s):
    s = s.replace("&nbsp;", " ").replace(" ", " ")
    z = "０１２３４５６７８９"
    for i, c in enumerate(z):
        s = s.replace(c, str(i))
    return s


def parse_session(title):
    """ページタイトルから (元号, 年, 回) を取り出す。"""
    t = norm_digits(title)
    m = re.search(r"(令和|平成)\s*([0-9]+|[元一二三四五六七八九十]+)\s*年", t)
    if not m:
        return None
    era = "R" if m.group(1) == "令和" else "H"
    ynum = m.group(2)
    year = int(ynum) if ynum.isdigit() else KANSUJI.get(ynum)
    if year is None:
        return None
    # 第Ⅰ回 / 第Ｉ回 / 第I回 / 第1回 …
    kai = 0
    mk = re.search(r"第\s*(Ⅰ|Ⅱ|ＩＩ|II|Ｉ|I|1|2)\s*回", t)
    if mk:
        g = mk.group(1)
        kai = 2 if g in ("Ⅱ", "ＩＩ", "II", "2") else 1
    return era, year, kai


def sid(era, year, kai):
    return f"{era}{year:02d}" + (f"-{kai}" if kai else "")


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return "skip"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if not data.startswith(b"%PDF"):
        return "notpdf"
    with open(path, "wb") as f:
        f.write(data)
    time.sleep(0.5)
    return "ok"


def main():
    man = json.load(open("kakomon_manifest.json", encoding="utf-8"))
    cnt = collections.Counter(p["url"] for s in man for p in s["pdfs"])
    common = {u for u, c in cnt.items() if c >= 20}

    records = []

    # ---- 1) 試験問題・答案用紙 ----
    for s in man:
        if "試験問題及び答案用紙" not in s["text"]:
            continue
        ses = parse_session(s["text"])
        if not ses:
            print("  ?? cannot parse:", s["text"][:50]); continue
        key = sid(*ses)
        pdfs = [p for p in s["pdfs"] if p["url"] not in common]
        seen = collections.Counter()
        for p in pdfs:
            txt = p["text"]
            # 「誤記について」「訂正」等の付随PDFは科目ファイルではない
            if re.search(r"誤記|誤り|訂正|取扱い", txt):
                records.append({"session": key, "era_year_kai": ses, "subject": "全科目",
                                "kind": "正誤表", "url": p["url"], "src_page": s["url"],
                                "src_title": s["text"], "label": txt})
                continue
            subjs = [x for x in SUBJECTS if x in txt]          # 「管理会計論・監査論」は合本
            if not subjs:
                if "答案用紙" in txt:                            # 全科目まとめの答案用紙
                    records.append({"session": key, "era_year_kai": ses, "subject": "全科目",
                                    "kind": "答案用紙", "url": p["url"], "src_page": s["url"],
                                    "src_title": s["text"], "label": txt})
                continue
            key2 = "・".join(subjs)
            seen[key2] += 1
            kind = "問題" if seen[key2] == 1 else "答案用紙"
            for subj in subjs:
                records.append({"session": key, "era_year_kai": ses, "subject": subj,
                                "kind": kind, "url": p["url"], "src_page": s["url"],
                                "src_title": s["text"], "label": txt,
                                "combined": len(subjs) > 1})

    # ---- 2) 正解、満点及び配点 ----
    for s in man:
        for p in s["pdfs"]:
            if "正解" not in p["text"] or "取扱い" in p["text"]:
                continue
            ses = parse_session(s["text"])
            if not ses:
                continue
            records.append({"session": sid(*ses), "era_year_kai": ses, "subject": "全科目",
                            "kind": "正解", "url": p["url"], "src_page": s["url"],
                            "src_title": s["text"], "label": p["text"]})

    # ---- 3) クロールで拾えなかった回の正解を URL パターンで直接試す ----
    B = "https://www.fsa.go.jp/cpaaob/kouninkaikeishi-shiken/"
    for key, ses, url in [
        ("R08-2", ("R", 8, 2), B + "r8shiken/tantougoukaku_r08-2/06.pdf"),
        ("H25-1", ("H", 25, 1), B + "tantougoukaku25a/03.pdf"),
        ("H25-2", ("H", 25, 2), B + "tantougoukaku25b/03.pdf"),
    ]:
        records.append({"session": key, "era_year_kai": ses, "subject": "全科目",
                        "kind": "正解", "url": url, "src_page": "(pattern guess)",
                        "src_title": "", "label": "正解、満点及び配点(推定URL)"})

    # 同一 session+subject+kind の重複を除去
    uniq, seen = [], set()
    for r in records:
        k = (r["session"], r["subject"], r["kind"])
        if k in seen:
            continue
        seen.add(k); uniq.append(r)

    sessions = sorted({r["session"] for r in uniq})
    print(f"sessions={len(sessions)}  files={len(uniq)}")
    print("  ", " ".join(sessions))

    ok = fail = skip = 0
    for r in uniq:
        d = os.path.join(OUT, r["session"])
        os.makedirs(d, exist_ok=True)
        fn = f"{r['subject']}_{r['kind']}.pdf"
        path = os.path.join(d, fn)
        r["path"] = path
        try:
            st = fetch(r["url"], path)
        except Exception as e:
            print("  !!", r["session"], fn, e); fail += 1; r["path"] = None; continue
        if st == "ok":
            ok += 1
        elif st == "skip":
            skip += 1
        else:
            print("  !! not a pdf:", r["url"]); fail += 1; r["path"] = None

    print(f"downloaded={ok} skipped={skip} failed={fail}")
    json.dump(uniq, open("kakomon_files.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # サマリ
    per = collections.defaultdict(collections.Counter)
    for r in uniq:
        if r.get("path"):
            per[r["session"]][r["kind"]] += 1
    print("\nsession    問題 答案用紙 正解")
    for s in sessions:
        c = per[s]
        print(f"  {s:8s} {c['問題']:4d} {c['答案用紙']:6d} {c['正解']:4d}")


if __name__ == "__main__":
    main()

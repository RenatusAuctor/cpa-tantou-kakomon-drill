# -*- coding: utf-8 -*-
"""過去問テキスト → 問題／肢／正解／肢別O×の構造化データ。"""
import json, re, collections, os

TXT = "과거문_text"
SUBJECTS = ["財務会計論", "監査論", "企業法", "管理会計論"]
MARKS = "アイウエオカキク"

Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def norm(t):
    t = t.replace("\x07", " ").replace(" ", " ")
    t = t.translate(Z2H)
    t = t.replace("．", ".").replace("，", "、")
    return t


FOOTER = re.compile(r"(令和|平成)\s*\d+\s*年第?\s*[ⅠⅡIＩ12]*\s*回?\s*短答式")
HEADER = re.compile(r"^\s*\d*\s*[ＭM]\s*\d\s*[―ー\-]\s*\d+\s*$")
PAGENO = re.compile(r"^\s*\d{1,3}\s*$")          # 単独で置かれた頁番号
BLANK = re.compile(r"^\s*$")


def clean_lines(text):
    out = []
    for ln in text.split("\n"):
        if FOOTER.search(ln) or HEADER.match(ln) or BLANK.match(ln) or PAGENO.match(ln):
            continue
        if ln.strip() == "\f":
            continue
        out.append(ln.rstrip())
    return out


QSTART = re.compile(r"^\s*問\s*題\s*(\d+)(?!\d)")   # 見出しが二重に刷られる年度がある
SHI = re.compile(r"^\s*([" + MARKS + r"])\s*\.\s*(.*)$")
CHOICE = re.compile(r"([1-9])\s*\.\s*([^0-9]{1,24}?)(?=\s+[1-9]\s*\.|$)")
# 「1．アイ」だけが1行に来る形式（pdfminer 出力で頻出）
ONECHOICE = re.compile(r"^\s*[1-9]\s*\.\s*[^\d]{1,20}$")   # 「1． ア イ」のように字間が空く年度がある


SUBJ_IN_FOOTER = re.compile(r"短答式\s*(" + "|".join(SUBJECTS) + r")")


def parse_questions(path, want=None):
    """want を指定すると、そのページ脚注の科目に属する問題だけを返す
    （H25・H26 は管理会計論と監査論が1つのPDFに合本されている）。"""
    raw = norm(open(path, encoding="utf-8").read())
    lines, lsubj, cur_s = [], [], None
    for page in raw.split("\f"):
        m = SUBJ_IN_FOOTER.search(page)
        if m:
            cur_s = m.group(1)
        cl = clean_lines(page)
        lines += cl
        lsubj += [cur_s] * len(cl)
    starts = [i for i, ln in enumerate(lines) if QSTART.match(ln)]
    if not starts:
        return []
    # 問題番号が 1,2,3… と単調増加する並びだけを採用（本文中の「問題2」参照を除去）。
    # 合本PDFでは科目が変わると番号が1に戻るので、科目ごとに数える。
    keep, expect = [], collections.defaultdict(lambda: 1)
    for i in starts:
        n = int(QSTART.match(lines[i]).group(1))
        s = lsubj[i]
        if n == expect[s]:
            keep.append((i, n)); expect[s] += 1
    qs = []
    for k, (i, n) in enumerate(keep):
        j = keep[k + 1][0] if k + 1 < len(keep) else len(lines)
        block = lines[i:j]
        # 冒頭行から「問題 N」を剥がす
        block = block[:]
        block[0] = QSTART.sub("", block[0], count=1)

        stem, shi, cur = [], {}, None
        choice_line = None
        for ln in block:
            m = SHI.match(ln)
            if m:
                cur = m.group(1)
                shi[cur] = [m.group(2)]
                continue
            # 選択肢：1行に3個以上並ぶ場合と、1個ずつ改行される場合の両方
            if len(re.findall(r"[1-9]\s*\.", ln)) >= 3 or ONECHOICE.match(ln):
                choice_line = ln if choice_line is None else choice_line + " " + ln
                cur = None
                continue
            (shi[cur] if cur else stem).append(ln.strip())

        shi = {k2: re.sub(r"\s+", "", "".join(v)) for k2, v in shi.items()}
        stem_t = re.sub(r"\s+", "", "".join(stem))
        choices = {}
        if choice_line:
            for num, body in CHOICE.findall(choice_line):
                choices[int(num)] = re.sub(r"\s+", "", body)
        qs.append({"no": n, "stem": stem_t, "shi": shi, "choices": choices,
                   "page_subject": lsubj[i]})
    if want and any(q["page_subject"] for q in qs):
        qs = [q for q in qs if q["page_subject"] == want]
    return qs


# ---------- 正解表（座標ベース） ----------
QTOK = re.compile(r"^問\s*題\s*(\d+)$")
VTOK = re.compile(r"^([1-9])$")


def parse_seikai(pdf_path, counts):
    """正解PDFの語を座標で読み、{科目: {no: ans}} を返す。

    表は科目ごとの縦列。科目見出し【…】は自分の最初の列の上に来るので、
    「問題N」トークンの x に最も近い見出しをその列の科目とみなす。
    """
    import pdfplumber, warnings
    warnings.filterwarnings("ignore")
    ans = {s: {} for s in SUBJECTS}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                heads = []
                for w in words:
                    # 注記行にも【科目】が出るので、単独の見出し語だけを採用
                    m = re.fullmatch(r"【(" + "|".join(SUBJECTS) + r")】", w["text"].strip())
                    if m:
                        heads.append((w["x0"], m.group(1)))
                if not heads:
                    continue
                # 行にまとめる（「問題　1」は全角空白で2語に割れることがある）
                rows = collections.defaultdict(list)
                for w in words:
                    rows[round(w["top"] / 5)].append(w)
                for _, ws in sorted(rows.items()):
                    ws.sort(key=lambda w: w["x0"])
                    toks = [(norm(w["text"]).strip(), w["x0"]) for w in ws]
                    i = 0
                    while i < len(toks):
                        t, x = toks[i]
                        if t == "問題番号":
                            i += 1; continue
                        no = None
                        m = QTOK.match(t.replace(" ", ""))
                        if m:
                            no = int(m.group(1)); i += 1
                        elif t.replace(" ", "") == "問題" and i + 1 < len(toks) \
                                and toks[i + 1][0].isdigit():
                            no = int(toks[i + 1][0]); i += 2
                        else:
                            i += 1; continue
                        # 直後の1桁数字が正解
                        if i < len(toks) and VTOK.match(toks[i][0]) \
                                and 0 < toks[i][1] - x < 90:
                            subj = min(heads, key=lambda h: abs(h[0] - x))[1]
                            ans[subj][no] = int(toks[i][0]); i += 1
    except Exception as e:
        return None, f"pdfplumber: {e}"

    bad = []
    for s, n in counts.items():
        got = ans.get(s, {})
        missing = [i for i in range(1, n + 1) if i not in got]
        extra = [i for i in got if i > n]
        if missing or extra:
            bad.append(f"{s}: 欠{len(missing)} 余{len(extra)}")
    return ans, ("; ".join(bad) if bad else None)


# ---------- 肢別 O/X ----------
NEG = re.compile(r"誤っているもの|適切でないもの|妥当でないもの|正しくないもの")
POS = re.compile(r"正しいもの|適切なもの|妥当なもの")
COMBO = re.compile(r"^[" + MARKS + r"]+$")


def classify(q):
    ch = q["choices"]
    if q["shi"] and ch and all(COMBO.match(v or "") for v in ch.values()):
        return "組合せ"
    if ch and all(re.match(r"^\d+個$", v or "") for v in ch.values()):
        return "個数"
    if not q["shi"] and ch:
        return "単一選択"
    return "その他"


def derive(q, ans):
    """組合せ型のみ、肢ごとの正誤を返す。"""
    if classify(q) != "組合せ" or ans not in q["choices"]:
        return None
    picked = set(q["choices"][ans])
    if NEG.search(q["stem"]):
        truth = {k: (k not in picked) for k in q["shi"]}
    elif POS.search(q["stem"]):
        truth = {k: (k in picked) for k in q["shi"]}
    else:
        return None
    return truth


def main():
    idx = json.load(open("kakomon_text_index.json", encoding="utf-8"))
    bysess = collections.defaultdict(dict)
    for f in idx:
        bysess[f["session"]][(f["subject"], f["kind"])] = f

    out, diag = [], []
    for sess in sorted(bysess):
        d = bysess[sess]
        qmap, counts = {}, {}
        for subj in SUBJECTS:
            f = d.get((subj, "問題"))
            if not f:
                continue
            qs = parse_questions(f["txt"], want=subj)
            qmap[subj] = qs
            counts[subj] = len(qs)
        sf = d.get(("全科目", "正解"))
        ans, err = (None, "正解PDFなし")
        if sf:
            ans, err = parse_seikai(sf["path"], counts)
        diag.append({"session": sess, "counts": dict(counts), "seikai_err": err})

        for subj, qs in qmap.items():
            for q in qs:
                a = (ans or {}).get(subj, {}).get(q["no"])
                typ = classify(q)
                tr = derive(q, a) if a else None
                out.append({"session": sess, "subject": subj, "no": q["no"],
                            "type": typ, "answer": a, "stem": q["stem"],
                            "shi": q["shi"], "choices": q["choices"],
                            "truth": tr})

    json.dump(out, open("kakomon_questions.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("session  " + "".join(f"{s:>9s}" for s in SUBJECTS) + "   正解表")
    for d in diag:
        c = d["counts"]
        line = f"  {d['session']:7s}" + "".join(f"{c.get(s,0):9d}" for s in SUBJECTS)
        line += "   " + ("OK" if d["seikai_err"] is None else "NG: " + str(d["seikai_err"])[:40])
        print(line)

    ty = collections.Counter((q["subject"], q["type"]) for q in out)
    print("\n科目          型        問題数")
    for (s, t), n in sorted(ty.items()):
        print(f"  {s:12s} {t:8s} {n:5d}")
    ox = sum(len(q["truth"]) for q in out if q["truth"])
    print(f"\n総問題数 {len(out)} / 肢別O×カード {ox}")


if __name__ == "__main__":
    main()

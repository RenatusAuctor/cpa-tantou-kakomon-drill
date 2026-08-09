# -*- coding: utf-8 -*-
"""教材本文と過去問の肢を、漢字・カタカナ n-gram の TF-IDF コサインで対応づける。

形態素解析器が無い環境なので、漢字／カタカナの連続だけを取り出して
その中の2〜4文字を語とみなす。助詞などの機能語は自然に落ちる。
"""
import json, re, math, collections, sys

SUBJ_MAP = {"기업법": "企業法", "감사론": "監査論",
            "재무회계론(이론)": "財務会計論", "관리회계론": "管理会計論"}

RUN = re.compile(r"[一-鿿々ァ-ヺー]{2,}")
NGRAM = (2, 3, 4)
DF_MAX_RATIO = 0.25      # 科目内の1/4超の論点に出る語は捨てる
TOP_K = 2                # 1つの肢につき最大2論点
REL = 0.85               # 1位に肉薄するものだけ2つ目として採る
# 0.32 未満は目視するとほぼ誤り（計算だけの肢など）。
# 0.32〜0.40 で妥当な対応が並びはじめる。
ABS_MIN = 0.32


def terms(text):
    out = collections.Counter()
    for run in RUN.findall(text):
        for n in NGRAM:
            for i in range(len(run) - n + 1):
                out[run[i:i + n]] += 1
    return out


def tfidf(counter, idf):
    v = {}
    for t, c in counter.items():
        w = idf.get(t)
        if w:
            v[t] = (1 + math.log(c)) * w
    n = math.sqrt(sum(x * x for x in v.values()))
    if n:
        for t in v:
            v[t] /= n
    return v


def main():
    ab = json.load(open("ab_data.json", encoding="utf-8"))
    bodies = json.load(open("topic_bodies.json", encoding="utf-8"))
    qs = json.load(open("kakomon_questions.json", encoding="utf-8"))

    # ---- 科目ごとに論点側の索引を作る ----
    idx_by_subj = collections.defaultdict(list)
    for i, t in enumerate(ab):
        idx_by_subj[SUBJ_MAP[t["subject"]]].append(i)

    models = {}
    for subj, ids in idx_by_subj.items():
        docs = {}
        for i in ids:
            # 見出しは効き目が強いので3回ぶん重みを付ける
            docs[i] = terms(ab[i]["heading"] * 3 + " " + (bodies[i] or ""))
        df = collections.Counter()
        for c in docs.values():
            df.update(c.keys())
        N = len(docs)
        cut = N * DF_MAX_RATIO
        idf = {t: math.log(N / d) for t, d in df.items() if 1 < d <= cut}
        inv = collections.defaultdict(list)
        for i, c in docs.items():
            for t, w in tfidf(c, idf).items():
                inv[t].append((i, w))
        models[subj] = (idf, inv, N)
        print(f"  {subj:8s} 論点 {N:5d}  語彙 {len(idf):7d}")

    # ---- 肢／問題を照合 ----
    def match(subj, text):
        idf, inv, _ = models[subj]
        q = tfidf(terms(text), idf)
        if not q:
            return []
        sc = collections.defaultdict(float)
        for t, w in q.items():
            for i, dw in inv.get(t, ()):
                sc[i] += w * dw
        if not sc:
            return []
        best = max(sc.values())
        if best < ABS_MIN:
            return []
        cand = [(v, i) for i, v in sc.items() if v >= max(best * REL, ABS_MIN)]
        cand.sort(reverse=True)
        return [i for _, i in cand[:TOP_K]]

    nshi = ncard_hit = nq_hit = 0
    for k, q in enumerate(qs):
        subj = q["subject"]
        head = q["stem"][:60]
        st = {}
        if q.get("truth"):
            for mk in q["truth"]:
                nshi += 1
                hits = match(subj, head + " " + q["shi"].get(mk, ""))
                st[mk] = hits
                if hits:
                    ncard_hit += 1
        q["shi_topics"] = st
        uni = sorted({i for v in st.values() for i in v})
        if not uni:                       # 肢が無い問題は問題文全体で照合
            uni = match(subj, q["stem"] + "".join(q["shi"].values()))
        q["topics"] = uni
        if uni:
            nq_hit += 1
        if (k + 1) % 300 == 0:
            sys.stdout.write(f"\r  {k+1}/{len(qs)}"); sys.stdout.flush()
    print()

    # ---- 論点側の集計 ----
    freq = collections.Counter()
    cards = collections.Counter()
    sess = collections.defaultdict(set)
    for q in qs:
        for i in q["topics"]:
            freq[i] += 1
            sess[i].add(q["session"])
        for mk, v in q.get("shi_topics", {}).items():
            for i in v:
                cards[i] += 1

    out = []
    for i, t in enumerate(ab):
        out.append({"subject": t["subject"], "grade": t["grade"],
                    "chapter": t["chapter"], "section": t["section"],
                    "heading": t["heading"], "vol": t.get("vol", ""),
                    "page": t.get("page", 0),
                    "freq": freq.get(i, 0), "cards": cards.get(i, 0),
                    "sessions": sorted(sess.get(i, ()))})
    json.dump(out, open("kakomon_topic_freq.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump(qs, open("kakomon_questions.json", "w", encoding="utf-8"),
              ensure_ascii=False)

    hit_t = sum(1 for t in out if t["freq"])
    print(f"\n肢 {ncard_hit}/{nshi} が論点に紐づいた ({ncard_hit/nshi*100:.0f}%)")
    print(f"問題 {nq_hit}/{len(qs)} ({nq_hit/len(qs)*100:.0f}%)")
    print(f"出題実績のある論点 {hit_t}/{len(ab)} ({hit_t/len(ab)*100:.0f}%)")
    per = collections.defaultdict(lambda: [0, 0])
    for t in out:
        per[t["subject"]][0] += 1
        per[t["subject"]][1] += 1 if t["freq"] else 0
    print("\n科目            論点数  出題実績あり")
    for s, (a, b) in per.items():
        print(f"  {s:14s} {a:5d} {b:6d} ({b/a*100:.0f}%)")
    print("\n出題頻度トップ12")
    for t in sorted(out, key=lambda x: -x["freq"])[:12]:
        print(f"  {t['freq']:3d}回 {t['cards']:4d}肢 [{t['subject']} {t['grade']}] "
              f"{t['heading'][:40]}")


if __name__ == "__main__":
    main()

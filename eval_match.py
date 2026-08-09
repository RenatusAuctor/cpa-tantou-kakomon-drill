# -*- coding: utf-8 -*-
"""照合の精度を目で見て確かめる：スコア分布と、高中低それぞれの実例。"""
import json, math, collections, random, sys
import match_by_body as M

ab = json.load(open("ab_data.json", encoding="utf-8"))
bodies = json.load(open("topic_bodies.json", encoding="utf-8"))
qs = json.load(open("kakomon_questions.json", encoding="utf-8"))

idx_by_subj = collections.defaultdict(list)
for i, t in enumerate(ab):
    idx_by_subj[M.SUBJ_MAP[t["subject"]]].append(i)

models = {}
for subj, ids in idx_by_subj.items():
    docs = {i: M.terms(ab[i]["heading"] * 3 + " " + (bodies[i] or "")) for i in ids}
    df = collections.Counter()
    for c in docs.values():
        df.update(c.keys())
    N = len(docs); cut = N * M.DF_MAX_RATIO
    idf = {t: math.log(N / d) for t, d in df.items() if 1 < d <= cut}
    inv = collections.defaultdict(list)
    for i, c in docs.items():
        for t, w in M.tfidf(c, idf).items():
            inv[t].append((i, w))
    models[subj] = (idf, inv)


def top(subj, text, k=3):
    idf, inv = models[subj]
    q = M.tfidf(M.terms(text), idf)
    sc = collections.defaultdict(float)
    for t, w in q.items():
        for i, dw in inv.get(t, ()):
            sc[i] += w * dw
    return sorted(((v, i) for i, v in sc.items()), reverse=True)[:k]


units = []
for q in qs:
    for mk in (q.get("truth") or {}):
        units.append((q, mk, q["stem"][:60] + " " + q["shi"].get(mk, "")))

print(f"肢 {len(units)}件を採点中…")
scored = []
for n, (q, mk, txt) in enumerate(units):
    t = top(q["subject"], txt, 1)
    scored.append((t[0][0] if t else 0.0, q, mk, txt, t[0][1] if t else None))
    if (n + 1) % 500 == 0:
        sys.stdout.write(f"\r  {n+1}/{len(units)}"); sys.stdout.flush()
print()

vals = sorted(s[0] for s in scored)
def pct(p): return vals[int(len(vals) * p)]
print("\n最高スコアの分布")
for p in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99):
    print(f"  上位{100-int(p*100):3d}%点  {pct(p):.3f}")
for th in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
    n = sum(1 for v in vals if v >= th)
    print(f"  閾値 {th:.2f} → 残る肢 {n:5d} ({n/len(vals)*100:.0f}%)")

random.seed(7)
for label, lo, hi in [("高スコア", 0.25, 1.0), ("中スコア", 0.11, 0.14),
                      ("低スコア", 0.05, 0.08)]:
    pool = [s for s in scored if lo <= s[0] < hi]
    print(f"\n===== {label}（{lo}〜{hi}）  該当 {len(pool)}件 =====")
    for sc, q, mk, txt, ti in random.sample(pool, min(4, len(pool))):
        t = ab[ti]
        print(f"[{sc:.3f}] {q['session']} {q['subject']} 問{q['no']}{mk}")
        print(f"   肢  : {q['shi'].get(mk,'')[:78]}")
        print(f"   論点: {t['heading'][:44]}　（{t['chapter'][:20]}）")

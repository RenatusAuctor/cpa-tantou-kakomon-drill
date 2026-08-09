# -*- coding: utf-8 -*-
"""論点チェックリスト用ペイロード：4,389件のA/B論点を辞書圧縮して出す。"""
import json, collections

src = json.load(open("ab_data.json", encoding="utf-8"))
freq = {}
try:
    for t in json.load(open("kakomon_topic_freq.json", encoding="utf-8")):
        if t.get("freq"):
            freq[(t["subject"], t["chapter"], t["section"], t["heading"])] = t["freq"]
except FileNotFoundError:
    pass

SUBJ = ["기업법", "감사론", "관리회계론", "재무회계론(이론)"]
si = {s: i for i, s in enumerate(SUBJ)}

chaps, secs = [], []
ci, xi = {}, {}


def idx(v, arr, d):
    if v not in d:
        d[v] = len(arr); arr.append(v)
    return d[v]


rows = []
for t in src:
    s = si[t["subject"]]
    g = 0 if t["grade"] == "A" else 1
    c = idx(t["chapter"], chaps, ci)
    x = idx(t["section"], secs, xi)
    f = freq.get((t["subject"], t["chapter"], t["section"], t["heading"]), 0)
    rows.append([s, g, c, x, t["heading"], t.get("vol", ""), t.get("page", 0), f])

# 教材の並び（科目 → 巻 → 頁）を保つ
rows.sort(key=lambda r: (r[0], r[5], r[6]))

payload = {"subjects": SUBJ, "chapters": chaps, "sections": secs, "rows": rows,
           "meta": {"n": len(rows),
                    "a": sum(1 for r in rows if r[1] == 0),
                    "b": sum(1 for r in rows if r[1] == 1),
                    "withfreq": sum(1 for r in rows if r[7] > 0)}}
out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
open("checklist_payload.json", "w", encoding="utf-8").write(out)

print(f"rows={len(rows)}  chapters={len(chaps)}  sections={len(secs)}")
print(f"payload = {len(out.encode('utf-8'))/1024:.0f} KB")
c = collections.Counter((SUBJ[r[0]], "AB"[r[1]]) for r in rows)
for k in sorted(c):
    print(f"  {k[0]:14s} {k[1]}  {c[k]:5d}")
print(f"出題実績つき論点 {payload['meta']['withfreq']}")

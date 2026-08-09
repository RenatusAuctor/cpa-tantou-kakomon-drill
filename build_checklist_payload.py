# -*- coding: utf-8 -*-
"""論点チェックリスト用ペイロード：4,389件のA/B論点を辞書圧縮して出す。"""
import json, collections

src = json.load(open("ab_data.json", encoding="utf-8"))

# 論点ID = ab_data.json 上の添字。ドリル側と同じIDなので #topic=<id> で飛べる。
freq, ncards = {}, {}
try:
    tp = json.load(open("kakomon_topic_freq.json", encoding="utf-8"))
    qs = json.load(open("kakomon_questions.json", encoding="utf-8"))
    per = collections.Counter()
    for q in qs:
        for mk, ids in (q.get("shi_topics") or {}).items():
            for t in ids:
                per[t] += 1
    for i, t in enumerate(tp):
        if t.get("freq"):
            freq[i] = t["freq"]
            ncards[i] = per.get(i, 0)
except FileNotFoundError:
    pass

SUBJ = ["기업법", "감사론", "관리회계론", "재무회계론(이론)"]      # ab_data 側のキー
SUBJ_KO = ["기업법", "감사론", "관리회계론", "재무회계론"]          # 画面表示
si = {s: i for i, s in enumerate(SUBJ)}

chaps, secs = [], []
ci, xi = {}, {}


def idx(v, arr, d):
    if v not in d:
        d[v] = len(arr); arr.append(v)
    return d[v]


rows = []
for i, t in enumerate(src):
    s = si[t["subject"]]
    g = 0 if t["grade"] == "A" else 1
    c = idx(t["chapter"], chaps, ci)
    x = idx(t["section"], secs, xi)
    rows.append([s, g, c, x, t["heading"], t.get("vol", ""), t.get("page", 0),
                 freq.get(i, 0), i, ncards.get(i, 0)])

# 教材の並び（科目 → 巻 → 頁）を保つ
rows.sort(key=lambda r: (r[0], r[5], r[6]))

payload = {"subjects": SUBJ_KO, "chapters": chaps, "sections": secs, "rows": rows,
           "meta": {"n": len(rows),
                    "a": sum(1 for r in rows if r[1] == 0),
                    "b": sum(1 for r in rows if r[1] == 1),
                    "withfreq": sum(1 for r in rows if r[7] > 0),
                    "withcards": sum(1 for r in rows if r[9] > 0)}}
out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
open("checklist_payload.json", "w", encoding="utf-8").write(out)

print(f"rows={len(rows)}  chapters={len(chaps)}  sections={len(secs)}")
print(f"payload = {len(out.encode('utf-8'))/1024:.0f} KB")
c = collections.Counter((SUBJ[r[0]], "AB"[r[1]]) for r in rows)
for k in sorted(c):
    print(f"  {k[0]:14s} {k[1]}  {c[k]:5d}")
print(f"出題実績つき論点 {payload['meta']['withfreq']}"
      f"　うち肢カードあり {payload['meta']['withcards']}")

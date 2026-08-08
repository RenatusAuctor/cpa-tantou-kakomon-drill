# -*- coding: utf-8 -*-
"""HTML アーティファクト用のコンパクトな JSON ペイロードを作る。"""
import json, re, collections

qs = json.load(open("kakomon_questions.json", encoding="utf-8"))
tp = json.load(open("kakomon_topic_freq.json", encoding="utf-8"))

SUBJ = ["企業法", "監査論", "管理会計論", "財務会計論"]


def sess_key(s):
    m = re.match(r"([HR])(\d+)(?:-(\d))?", s)
    era, y, k = m.group(1), int(m.group(2)), int(m.group(3) or 0)
    return (0 if era == "H" else 1, y, k)


SESS = sorted({q["session"] for q in qs}, key=sess_key)
si = {s: i for i, s in enumerate(SUBJ)}
ei = {s: i for i, s in enumerate(SESS)}

THEME = re.compile(r"^(.{2,64}?)(?:に関する|について)")


def theme(stem):
    m = THEME.match(stem)
    if m:
        return m.group(1)
    return stem[:34] + ("…" if len(stem) > 34 else "")


cards, questions = [], []
for q in qs:
    s, e = si[q["subject"]], ei[q["session"]]
    th = theme(q["stem"])
    shi = [[k, v] for k, v in q["shi"].items()]
    questions.append([s, e, q["no"], q["type"], q["answer"], q["stem"], shi,
                      q["choices"], len(q.get("topics", []))])
    qi = len(questions) - 1
    if q["truth"]:
        for mk, tv in q["truth"].items():
            cards.append([s, e, q["no"], mk, 1 if tv else 0,
                          th, q["shi"].get(mk, ""), qi])

# 出題頻度のある論点のみ
topics = []
for t in tp:
    if t["freq"] > 0:
        topics.append([t["subject"], t["grade"], t["chapter"], t["section"],
                       t["heading"], t["freq"],
                       [ei[s] for s in t["sessions"] if s in ei]])
topics.sort(key=lambda x: -x[5])

payload = {"subjects": SUBJ, "sessions": SESS, "cards": cards,
           "questions": questions, "topics": topics,
           "meta": {"nq": len(questions), "ncards": len(cards),
                    "ntopics_total": len(tp), "ntopics_hit": len(topics)}}

out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
open("kakomon_payload.json", "w", encoding="utf-8").write(out)
print(f"cards={len(cards)} questions={len(questions)} topics={len(topics)}")
print(f"payload = {len(out.encode('utf-8'))/1024/1024:.2f} MB")
print("sessions:", " ".join(SESS))
print("\n肢別カードの科目内訳")
c = collections.Counter(SUBJ[x[0]] for x in cards)
for k, v in c.most_common():
    print(f"  {k:10s} {v:5d}")

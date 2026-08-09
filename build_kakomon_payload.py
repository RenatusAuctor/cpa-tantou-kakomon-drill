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
    tids = sorted(set(q.get("topics", [])))       # ab_data.json 上の添字＝論点ID
    questions.append([s, e, q["no"], q["type"], q["answer"], q["stem"], shi,
                      q["choices"], tids])
    qi = len(questions) - 1
    if q["truth"]:
        sht = q.get("shi_topics", {})
        for mk, tv in q["truth"].items():
            cards.append([s, e, q["no"], mk, 1 if tv else 0,
                          th, q["shi"].get(mk, ""), qi,
                          sorted(sht.get(mk, []))])   # この肢に紐づく論点

# 論点ID = ab_data.json（＝kakomon_topic_freq.json）上の添字。
# チェックリスト側と同じIDなので、両ツールを相互リンクできる。
SUBJ_JP = {"기업법": "企業法", "감사론": "監査論",
           "관리회계론": "管理会計論", "재무회계론(이론)": "財務会計論"}

ncards = collections.Counter()
for c in cards:
    for t in c[8]:
        ncards[t] += 1

topics = {}
for i, t in enumerate(tp):
    if not t["freq"]:
        continue
    topics[str(i)] = [si[SUBJ_JP[t["subject"]]], 0 if t["grade"] == "A" else 1,
                      t["chapter"], t["section"], t["heading"], t["freq"],
                      ncards.get(i, 0),
                      [ei[s] for s in t["sessions"] if s in ei],
                      t.get("vol", "").replace("권", "巻"), t.get("page", 0)]

payload = {"subjects": SUBJ, "sessions": SESS, "cards": cards,
           "questions": questions, "topics": topics,
           "meta": {"nq": len(questions), "ncards": len(cards),
                    "ntopics_total": len(tp), "ntopics_hit": len(topics),
                    "ncards_with_topic": sum(1 for c in cards if c[8]),
                    "ntopics_with_cards": sum(
                        1 for v in topics.values() if v[6])}}

out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
open("kakomon_payload.json", "w", encoding="utf-8").write(out)
m = payload["meta"]
print(f"cards={len(cards)} questions={len(questions)} topics={len(topics)}")
print(f"payload = {len(out.encode('utf-8'))/1024/1024:.2f} MB")
print(f"論点に紐づくカード {m['ncards_with_topic']}/{len(cards)}"
      f" ({m['ncards_with_topic']/len(cards)*100:.0f}%)")
print(f"カードを持つ論点   {m['ntopics_with_cards']}/{m['ntopics_total']}")
print("\n肢別カードの科目内訳")
c = collections.Counter(SUBJ[x[0]] for x in cards)
for k, v in c.most_common():
    print(f"  {k:10s} {v:5d}")
print("\nカード数が多い論点 上位10")
for k, v in sorted(topics.items(), key=lambda kv: -kv[1][6])[:10]:
    print(f"  {v[6]:4d}枚 (出題{v[5]:3d}回) [{SUBJ[v[0]]} {'AB'[v[1]]}] {v[4][:38]}")

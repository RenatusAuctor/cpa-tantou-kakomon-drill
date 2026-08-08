# -*- coding: utf-8 -*-
"""A/B論点(4,389件) と 過去問(2,282問) を対応づけて出題頻度を出す。"""
import json, re, collections

SUBJ_MAP = {"기업법": "企業法", "감사론": "監査論",
            "재무회계론(이론)": "財務会計論", "관리회계론": "管理会計論"}

# 見出しの先頭にある番号・記号を落とす
NUMPFX = re.compile(r"^[\s（(]*[０-９0-9①-⑳ⅰ-ⅹⅠ-Ⅹ一二三四五六七八九十]+"
                    r"[）).、．・]?\s*")
# 単独では意味が薄く、どの問題にも当たってしまう語
STOP = {"意義", "趣旨", "内容", "定義", "要件", "効果", "種類", "原則", "例外",
        "手続", "方法", "概要", "総論", "総説", "意味", "特徴", "問題点",
        "考え方", "比較", "関係", "適用", "範囲", "区分", "分類", "判断",
        "会計処理", "表示", "開示", "計算", "処理", "目的", "機能", "性質",
        "根拠", "理由", "留意点", "具体例", "その他", "まとめ"}

Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def core(h):
    """見出しからマッチング用のキーワードを取り出す。"""
    h = NUMPFX.sub("", h.strip())
    h = re.sub(r"[（(].*?[）)]", "", h)          # 補足の括弧を除去
    h = re.sub(r"[「」『』【】\s]", "", h)
    h = h.translate(Z2H)
    h = re.sub(r"(について|とは|の場合|に関する事項)$", "", h)
    return h


def main():
    topics = json.load(open("ab_data.json", encoding="utf-8"))
    qs = json.load(open("kakomon_questions.json", encoding="utf-8"))

    # 科目ごとに (キーワード, 論点index) を用意
    bysubj = collections.defaultdict(list)
    for i, t in enumerate(topics):
        jp = SUBJ_MAP[t["subject"]]
        k = core(t["heading"])
        t["key"] = k
        t["hits"] = []
        if len(k) < 4 or k in STOP:
            continue
        bysubj[jp].append((k, i))

    print("マッチング対象キーワード数")
    for s, v in bysubj.items():
        print(f"  {s:8s} {len(v):5d} / {sum(1 for t in topics if SUBJ_MAP[t['subject']]==s)}")

    # 問題テキスト（本文＋肢）を用意
    blobs = []
    for q in qs:
        q["topics"] = []                     # 前回実行の結果を持ち越さない
        b = q["stem"] + "".join(q["shi"].values())
        b = re.sub(r"[（(].*?[）)]", "", b).translate(Z2H)
        blobs.append(b)
    qidx = collections.defaultdict(list)
    for qi, q in enumerate(qs):
        qidx[q["subject"]].append(qi)

    # 一般語すぎるキーワードを文書頻度で落とす（「取締役」等は半数の問題に当たる）
    DF_MAX = 0.06
    kept = {}
    for subj, keys in bysubj.items():
        pool = qidx[subj]
        n = max(len(pool), 1)
        keep = []
        for k, ti in keys:
            df = sum(1 for qi in pool if k in blobs[qi])
            topics[ti]["df"] = df
            if 0 < df <= n * DF_MAX:
                keep.append((k, ti))
        kept[subj] = keep
        print(f"  {subj:8s} 一般語を除外 {len(keys)} → {len(keep)}")

    for subj, keys in kept.items():
        for qi in qidx[subj]:
            for k, ti in keys:
                if k in blobs[qi]:
                    qs[qi]["topics"].append(ti)
                    topics[ti]["hits"].append(qi)

    # 出題頻度
    for t in topics:
        t["freq"] = len(t["hits"])
        t["sessions"] = sorted({qs[i]["session"] for i in t["hits"]})

    matched_q = sum(1 for q in qs if q["topics"])
    matched_t = sum(1 for t in topics if t["freq"])
    print(f"\n論点に紐づいた問題 {matched_q}/{len(qs)} ({matched_q/len(qs)*100:.0f}%)")
    print(f"過去問に出た論点   {matched_t}/{len(topics)} ({matched_t/len(topics)*100:.0f}%)")

    per = collections.defaultdict(lambda: [0, 0])
    for t in topics:
        jp = SUBJ_MAP[t["subject"]]
        per[jp][0] += 1
        per[jp][1] += 1 if t["freq"] else 0
    print("\n科目          論点数  うち出題実績あり")
    for s, (a, b) in per.items():
        print(f"  {s:10s} {a:6d} {b:8d} ({b/a*100:.0f}%)")

    print("\n出題頻度トップ15")
    for t in sorted(topics, key=lambda x: -x["freq"])[:15]:
        print(f"  {t['freq']:3d}回 [{t['subject']} {t['grade']}] {t['heading'][:44]}")

    json.dump(topics, open("kakomon_topic_freq.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump(qs, open("kakomon_questions.json", "w", encoding="utf-8"),
              ensure_ascii=False)


if __name__ == "__main__":
    main()

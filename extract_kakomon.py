# -*- coding: utf-8 -*-
"""過去問PDF → 生テキスト。問題と正解のみ（答案用紙は白紙なので除外）。"""
import json, os, sys
from pdfminer.high_level import extract_text as _extract   # pypdf は一部年度のフォントを復号できない

OUT = "과거문_text"
files = json.load(open("kakomon_files.json", encoding="utf-8"))
os.makedirs(OUT, exist_ok=True)

targets = [f for f in files if f.get("path") and f["kind"] in ("問題", "正解")]
print(f"targets: {len(targets)}")

index, ok, fail = [], 0, 0
for f in targets:
    if not os.path.exists(f["path"]):
        continue
    name = f"{f['session']}_{f['subject']}_{f['kind']}.txt"
    dst = os.path.join(OUT, name)
    try:
        text = _extract(f["path"])          # pdfminer はページ間に \f を入れる
        pages = text.split("\f")
    except Exception as e:
        print("  !!", f["path"], e); fail += 1; continue
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(text)
    index.append({**f, "txt": dst, "pages": len(pages), "chars": len(text)})
    ok += 1
    sys.stdout.write(f"\r  {ok}/{len(targets)}"); sys.stdout.flush()

print(f"\nok={ok} fail={fail}")
json.dump(index, open("kakomon_text_index.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 抽出品質のざっくり確認：科目ごとの1ページあたり文字数
import collections
per = collections.defaultdict(list)
for i in index:
    per[(i["subject"], i["kind"])].append(i["chars"] / max(i["pages"], 1))
print("\n科目               種別   ファイル数  平均文字数/頁")
for (s, k), v in sorted(per.items()):
    print(f"  {s:12s} {k:6s} {len(v):5d}  {sum(v)/len(v):8.0f}")

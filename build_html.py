# -*- coding: utf-8 -*-
"""テンプレートにペイロードを差し込んで配布用HTMLを書き出す。"""

JOBS = [
    ("kakomon_template.html",  "kakomon_payload.json",   "index.html"),
    ("checklist_template.html", "checklist_payload.json", "checklist.html"),
]

for tpl_p, pay_p, out_p in JOBS:
    tpl = open(tpl_p, encoding="utf-8").read()
    pay = open(pay_p, encoding="utf-8").read()
    pay = pay.replace("</", "<\\/")          # </script> で閉じられないように
    out = tpl.replace("__PAYLOAD__", pay)
    open(out_p, "w", encoding="utf-8").write(out)
    print("%-16s %6.2f MB" % (out_p, len(out.encode("utf-8")) / 1024 / 1024))

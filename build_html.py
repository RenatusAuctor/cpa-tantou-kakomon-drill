# -*- coding: utf-8 -*-
import io, os

tpl = open("kakomon_template.html", encoding="utf-8").read()
pay = open("kakomon_payload.json", encoding="utf-8").read()
# </script> で閉じられないようにする
pay = pay.replace("</", "<\\/")
out = tpl.replace("__PAYLOAD__", pay)
open("kakomon_drill.html", "w", encoding="utf-8").write(out)
print("kakomon_drill.html %.2f MB" % (len(out.encode("utf-8")) / 1024 / 1024))

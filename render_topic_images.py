# -*- coding: utf-8 -*-
"""論点ごとに教材の紙面を切り出して img/ に書き出す。

テキスト抽出だと図表が壊れるので、マーカーからマーカーまでを画像で取る。
境界の考え方は extract_topic_bodies.py と同じ（全等級のマーカーが切れ目、
対応づけは A/B のみ）。
"""
import os, re, json, collections, sys, io
import warnings; warnings.filterwarnings("ignore")
import fitz
from PIL import Image
import extract_topic_bodies as E

OUT = "img"
# 紙面は黒い文字と罫線しかないので、1bit にすると同じ解像度で 1/5 以下になる。
# 130dpi では端末で等倍〜拡大になり、「社団性」が「社|団性」に割れて見えた。
# 200dpi なら 340CSSpx×DPR3 に縮小されるので線が保たれる（260 との差は見えない）。
DPI = 200
THRESHOLD = 176
PAD_TOP = 3          # 見出し行が切れないよう少し上から
PAD_X = 6
MAXPAGES = 6         # 次のマーカーが出るまでたどる頁数
FOOTER = re.compile(r"^\s*(－\s*[①-⑳]|[（(]\s*\d{1,4}\s*[）)]|\d{1,4})\s*$"
                    r"|\.indd\b|^\s*[ＭM]\d[―ー-]\d+\s*$")


def lines_of(page):
    """(y0, y1, x0, x1, text) の行リスト。単語を行ごとにまとめ直す。"""
    box = collections.OrderedDict()
    for x0, y0, x1, y1, w, b, l, n in page.get_text("words"):
        e = box.setdefault((b, l), [x0, y0, x1, y1, []])
        e[0] = min(e[0], x0); e[1] = min(e[1], y0)
        e[2] = max(e[2], x1); e[3] = max(e[3], y1)
        e[4].append((n, w))
    out = []
    for (b, l), e in box.items():
        txt = "".join(w for _, w in sorted(e[4]))
        out.append((e[1], e[3], e[0], e[2], txt))
    out.sort()
    return out


def marks_of(page, ls):
    """マーカー行を上から順に。(y0, 等級)"""
    res = []
    for y0, y1, x0, x1, txt in ls:
        m = E.MARKER.search(txt)
        if m:
            res.append((y0, E.grade_of(m)))
    return res


def content_span(ls):
    """柱・ノンブルを除いた本文の左右端と下端。"""
    xs0, xs1, ybot = [], [], 0
    for y0, y1, x0, x1, txt in ls:
        if FOOTER.search(txt.strip()):
            continue
        xs0.append(x0); xs1.append(x1); ybot = max(ybot, y1)
    if not xs0:
        return None
    return min(xs0), max(xs1), ybot


def main():
    ab = json.load(open("ab_data.json", encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    manifest = collections.defaultdict(list)

    by_book = collections.defaultdict(list)
    for i, t in enumerate(ab):
        by_book[(t["subject"], t["vol"])].append(i)

    total_bytes = 0
    for key in sorted(by_book):
        path = E.find_book(*key)
        if not path:
            print("  !! no pdf for", key); continue
        doc = fitz.open(path)
        cache = {}

        def info(pno):                       # 0-origin
            if pno not in cache:
                if 0 <= pno < doc.page_count:
                    ls = lines_of(doc[pno])
                    cache[pno] = (ls, marks_of(doc[pno], ls), content_span(ls))
                else:
                    cache[pno] = ([], [], None)
            return cache[pno]

        want = collections.defaultdict(list)
        for i in by_book[key]:
            want[ab[i]["page"]].append(i)

        ok = miss = 0
        for pno1, idxs in sorted(want.items()):
            p0 = pno1 - 1
            ls, mk, span = info(p0)
            ab_mk = [k for k, (y, g) in enumerate(mk) if g in ("A", "B")]
            if len(ab_mk) != len(idxs) or not span:
                miss += len(idxs); continue
            x0, x1, ybot = span
            for k, i in zip(ab_mk, idxs):
                top = mk[k][0] - PAD_TOP
                rects = []
                if k + 1 < len(mk):
                    rects.append((p0, top, mk[k + 1][0] - PAD_TOP))
                else:
                    rects.append((p0, top, ybot + 2))
                    for j in range(p0 + 1, min(p0 + 1 + MAXPAGES, doc.page_count)):
                        ls2, mk2, sp2 = info(j)
                        if not sp2:
                            break
                        head = min(y for y, _ in ((l[0], 0) for l in ls2)) if ls2 else 0
                        if mk2:
                            rects.append((j, head - PAD_TOP, mk2[0][0] - PAD_TOP))
                            break
                        rects.append((j, head - PAD_TOP, sp2[2] + 2))
                for n, (pg, ya, yb) in enumerate(rects):
                    if yb - ya < 6:
                        continue
                    sp = info(pg)[2] or (x0, x1, yb)
                    clip = fitz.Rect(max(0, sp[0] - PAD_X), max(0, ya),
                                     min(doc[pg].rect.width, sp[1] + PAD_X),
                                     min(doc[pg].rect.height, yb))
                    pm = doc[pg].get_pixmap(clip=clip, dpi=DPI,
                                            colorspace=fitz.csGRAY)
                    im = Image.frombytes("L", (pm.width, pm.height), pm.samples)
                    im = im.point(lambda v: 255 if v > THRESHOLD else 0, mode="1")
                    buf = io.BytesIO()
                    im.save(buf, "PNG", optimize=True)
                    name = f"{i}-{n}.png"
                    data = buf.getvalue()
                    open(os.path.join(OUT, name), "wb").write(data)
                    manifest[i].append(name)
                    total_bytes += len(data)
                ok += 1
            sys.stdout.write(f"\r  {key[0]} {key[1]}  {ok}/{len(by_book[key])}")
            sys.stdout.flush()
        print(f"\r  {key[0]:14s} {key[1]}  切り出し {ok}/{len(by_book[key])}"
              f"（頁のマーカー数が合わず飛ばした {miss}）", flush=True)
        doc.close()

    json.dump({str(k): v for k, v in manifest.items()},
              open("topic_images.json", "w", encoding="utf-8"))
    n_img = sum(len(v) for v in manifest.values())
    print(f"\n論点 {len(manifest)}/{len(ab)} に画像　計 {n_img} 枚　"
          f"{total_bytes/1024/1024:.1f} MB")
    multi = sum(1 for v in manifest.values() if len(v) > 1)
    print(f"2枚以上にまたがる論点 {multi}")


if __name__ == "__main__":
    main()

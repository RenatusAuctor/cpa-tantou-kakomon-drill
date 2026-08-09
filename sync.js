/* 端末間の引き継ぎ。両ツールは同じオリジンなので、1つの書き出しに
   ドリルとチェックリストの両方が入る。読み込みは上書きではなく、
   項目ごとに「新しく触った方」を残す併合。 */
var SYNC = (function () {
  "use strict";
  var DRILL = "cpa-kakomon-v1", CHECK = "cpa-checklist-v1";

  function read(k) {
    try { return JSON.parse(localStorage.getItem(k) || "null"); }
    catch (e) { return null; }
  }
  function write(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); return true; }
    catch (e) { return false; }
  }
  function counts() {
    var d = read(DRILL), c = read(CHECK);
    return { cards: d && d.log ? Object.keys(d.log).length : 0,
             topics: c && c.m ? Object.keys(c.m).length : 0 };
  }

  function exportText() {
    var o = { v: 1, at: Date.now(), k: {} };
    [DRILL, CHECK].forEach(function (k) { var v = read(k); if (v) o.k[k] = v; });
    return JSON.stringify(o);
  }

  /* 肢の記録は t にミリ秒が入っているので、新しい方を残す */
  function mergeDrill(a, b) {
    a = a || {}; b = b || {};
    var log = a.log || {}, inc = b.log || {}, n = 0;
    for (var k in inc) {
      var x = log[k], y = inc[k];
      if (!x || (y.t || 0) > (x.t || 0)) { log[k] = y; n++; }
    }
    a.log = log;
    if (b.day && b.day === a.day) {
      a.done = Math.max(a.done || 0, b.done || 0);
      a.hit = Math.max(a.hit || 0, b.hit || 0);
    }
    return { obj: a, n: n };
  }

  /* 論点は u（最後に触った日）で比べる。u が無い古い記録は t → k の順で代用 */
  function mergeCheck(a, b) {
    a = a || {}; b = b || {};
    var m = a.m || {}, inc = b.m || {}, n = 0;
    for (var k in inc) {
      var x = m[k], y = inc[k];
      if (!x) { m[k] = y; n++; continue; }
      var xu = x.u || x.t || 0, yu = y.u || y.t || 0;
      if (yu > xu || (yu === xu && (y.k || 0) > (x.k || 0))) { m[k] = y; n++; }
    }
    a.m = m;
    if (b.newday && b.newday === a.newday)
      a.newcnt = Math.max(a.newcnt || 0, b.newcnt || 0);
    return { obj: a, n: n };
  }

  function importText(text) {
    var o = JSON.parse(text);
    if (!o || !o.k) throw new Error("形式が違います");
    var r = { cards: 0, topics: 0 };
    if (o.k[DRILL]) {
      var d = mergeDrill(read(DRILL), o.k[DRILL]);
      if (!write(DRILL, d.obj)) throw new Error("保存できません");
      r.cards = d.n;
    }
    if (o.k[CHECK]) {
      var c = mergeCheck(read(CHECK), o.k[CHECK]);
      if (!write(CHECK, c.obj)) throw new Error("保存できません");
      r.topics = c.n;
    }
    return r;
  }

  function stamp() {
    var d = new Date(), p = function (x) { return (x < 10 ? "0" : "") + x; };
    return "" + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) +
      "-" + p(d.getHours()) + p(d.getMinutes());
  }

  /* claude.ai のアーティファクトでは downloads 経由、通常のページでは Blob */
  function saveFile(name, text, done) {
    if (window.claude && window.claude.downloads) {
      window.claude.downloads.save({ filename: name, data: text })
        .then(function () { done("書き出しました：" + name); })
        .catch(function (e) {
          done(e && e.code === "declined" ? "書き出しを取り消しました。"
                                          : blob(name, text));
        });
      return;
    }
    done(blob(name, text));
  }
  function blob(name, text) {
    var u = URL.createObjectURL(new Blob([text], { type: "application/json" }));
    var a = document.createElement("a");
    a.href = u; a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(u); a.remove(); }, 1000);
    return "書き出しました：" + name;
  }

  function mount(hostId, onImported) {
    var el = document.getElementById(hostId);
    if (!el) return;
    el.innerHTML =
      '<div class="flabel">ほかの端末に引き継ぐ</div>' +
      '<div class="synbtns">' +
        '<button type="button" class="sbtn" data-a="ex">書き出す</button>' +
        '<button type="button" class="sbtn" data-a="im">読み込む</button>' +
      '</div>' +
      '<input type="file" accept="application/json,.json" hidden>' +
      '<div class="hint" data-s></div>';
    var msg = el.querySelector("[data-s]");
    var file = el.querySelector("input[type=file]");

    function status(extra) {
      var c = counts();
      msg.textContent = (extra ? extra + "　" : "") +
        "この端末には 肢 " + c.cards.toLocaleString() + "件・論点 " +
        c.topics.toLocaleString() + "件 の記録があります。" +
        "読み込みは上書きではなく、項目ごとに新しい方を残します。";
    }
    status();

    el.querySelector('[data-a="ex"]').onclick = function () {
      saveFile("cpa-progress-" + stamp() + ".json", exportText(), status);
    };
    el.querySelector('[data-a="im"]').onclick = function () { file.click(); };
    file.onchange = function () {
      var f = file.files && file.files[0];
      if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        try {
          var r = importText(String(rd.result));
          status("取り込みました（肢 " + r.cards + "件・論点 " + r.topics + "件を更新）。");
          if (onImported) onImported();
        } catch (e) {
          msg.textContent = "読み込めませんでした：" + e.message +
            "　書き出したファイルをそのまま選んでください。";
        }
        file.value = "";
      };
      rd.readAsText(f);
    };
  }

  return { mount: mount, counts: counts };
})();

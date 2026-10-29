/* C5: quotation status. Four states, fake data only.
   A pending quotation is never shown as confirmed: only "approved" uses confirming words. */
(function () {
  "use strict";

  var M = window.MOCK;
  var F = window.Fmt;
  var O = window.Order;
  var order = O.load();
  var $ = function (id) { return document.getElementById(id); };

  var VIEW = {
    draft: {
      glyph: "✎", label: "טיוטה, טרם נשלחה",
      lead: "הבקשה עדיין לא נשלחה לעסק.",
      text: "אפשר לערוך את ההזמנה ולשלוח אותה כשתהיו מוכנים.",
      action: '<a class="btn" href="c5-submit.html">המשך לשליחה</a>'
    },
    pending: {
      glyph: "…", label: "ממתינה לאישור העסק",
      lead: "זו עדיין אינה הזמנה מאושרת.",
      text: "הבקשה נשלחה והעסק יבדוק אותה. עד שהעסק יאשר, אין הזמנה."
    },
    approved: {
      glyph: "✓", label: "אושרה על ידי העסק",
      lead: "העסק אישר את ההזמנה.",
      text: "ההזמנה אושרה לפי הפרטים והמחירים שנשלחו."
    },
    rejected: {
      glyph: "✕", label: "הבקשה נדחתה",
      lead: "העסק לא אישר את הבקשה.",
      text: "ההזמנה לא אושרה, ולכן אין הזמנה.",
      note: "מצטערים, ה־15 בינואר מלא. נשמח לבצע את האירוע ב־14 בינואר.",
      action: '<a class="btn btn--secondary" href="c1-event.html">עריכת האירוע ושליחה מחדש</a>'
    }
  };

  function timelineHtml(st) {
    var third = st === "approved" ? "אושרה" : st === "rejected" ? "נדחתה" : "החלטת העסק";
    var steps = [
      { t: "טיוטה", s: "done" },
      { t: "נשלחה לאישור", s: st === "draft" ? "todo" : st === "pending" ? "current" : "done" },
      { t: third, s: st === "approved" || st === "rejected" ? "current" : "todo" }
    ];
    if (st === "draft") steps[0].s = "current";
    var GLYPH = { done: "✓", current: "●", todo: "○" };
    var WORD = { done: "הושלם", current: "השלב הנוכחי", todo: "עדיין לא" };
    return steps.map(function (x) {
      return '<li class="timeline__item is-' + x.s + '"' + (x.s === "current" ? ' aria-current="step"' : "") + ">" +
        '<span class="timeline__mark" aria-hidden="true">' + GLYPH[x.s] + "</span>" +
        "<span>" + x.t + '<span class="visually-hidden"> (' + WORD[x.s] + ")</span></span></li>";
    }).join("");
  }

  function render(st) {
    var v = VIEW[st];
    $("status").dataset.state = st;
    $("status-glyph").textContent = v.glyph;
    $("status-label").textContent = v.label;
    $("status-lead").textContent = v.lead;
    $("status-text").textContent = v.text;
    $("owner-note").hidden = !v.note;
    if (v.note) $("owner-note-text").textContent = v.note;
    $("status-action").hidden = !v.action;
    if (v.action) $("status-action").innerHTML = v.action;
    $("timeline").innerHTML = timelineHtml(st);

    var snap = O.view(order);
    var t = snap.totals;
    $("frozen").hidden = st === "draft";
    $("frozen").textContent = "המחירים ננעלו בעת השליחה, " + F.date(snap.date || M.today) + ".";
    $("event-ledger").innerHTML = O.eventLines(snap.event).map(function (x) { return "<li>" + F.esc(x) + "</li>"; }).join("");
    $("lines").innerHTML = t.lines.map(function (l) {
      return '<li class="line"><p class="line__name">' + F.esc(l.dish.name) + "</p>" +
        '<p class="line__calc">' + F.esc(F.qty(l.qty, l.dish.unit)) + " × " + F.moneyText(l.dish.price) + "</p>" +
        '<p class="line__total"><span class="visually-hidden">סה״כ לשורה: </span>' + F.money(l.line) + "</p></li>";
    }).join("");
    $("subtotal").innerHTML = F.money(t.subtotal);
    if (snap.event.fulfillment === "pickup") {
      $("delivery-label").textContent = "איסוף עצמי";
      $("delivery").textContent = "ללא דמי משלוח";
    } else {
      $("delivery-label").textContent = "דמי משלוח" + (t.zone ? " ל" + t.zone.label : "");
      $("delivery").innerHTML = F.money(t.delivery);
    }
    $("total").innerHTML = F.money(t.total);
    document.title = v.label + " · המטבח של סבתא";
  }

  var fromQuery = (new URLSearchParams(window.location.search)).get("status");
  var start = VIEW[fromQuery] ? fromQuery : (order.status || "draft");
  render(start);

  document.querySelector(".demo").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-status]");
    if (b) render(b.dataset.status);
  });
})();

/* Hebrew formatting helpers. Classic script (no modules) so it works on file://.
   Money, quantities and times are wrapped in <bdi dir="ltr"> so RTL text around
   them cannot reorder digits, separators, the minus sign or the shekel sign. */
(function () {
  "use strict";

  var MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
  var WEEKDAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
  var NBSP = " ";
  var MINUS = "−";
  var LRI = "⁦";
  var PDI = "⁩";

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function number(n) {
    var abs = Math.abs(n);
    var whole = Math.round(abs * 100) % 100 === 0;
    var parts = abs.toFixed(whole ? 0 : 2).split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return parts.join(".");
  }

  // Plain text, for places that cannot hold markup (<option>, aria-label, textContent).
  function moneyText(n) {
    return LRI + (n < 0 ? MINUS : "") + number(n) + NBSP + "₪" + PDI;
  }

  function diffText(n) {
    return LRI + (n < 0 ? MINUS : "+") + number(n) + NBSP + "₪" + PDI;
  }

  // HTML, for innerHTML.
  function money(n) {
    return '<bdi class="num" dir="ltr">' + (n < 0 ? MINUS : "") + number(n) + NBSP + "₪</bdi>";
  }

  function moneyDiff(n) {
    return '<bdi class="num" dir="ltr">' + (n < 0 ? MINUS : "+") + number(n) + NBSP + "₪</bdi>";
  }

  function ltr(text) {
    return '<bdi class="num" dir="ltr">' + esc(text) + "</bdi>";
  }

  // Dates are "YYYY-MM-DD" strings; parsed in UTC so the time zone never shifts the day.
  function parse(iso) {
    var p = iso.split("-").map(Number);
    return new Date(Date.UTC(p[0], p[1] - 1, p[2]));
  }

  function toIso(d) {
    return d.getUTCFullYear() + "-" + String(d.getUTCMonth() + 1).padStart(2, "0") + "-" + String(d.getUTCDate()).padStart(2, "0");
  }

  // "15 בינואר 2027"
  function date(iso) {
    var d = parse(iso);
    return d.getUTCDate() + " ב" + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
  }

  // "יום שישי, 15 בינואר 2027"
  function dateLong(iso) {
    return "יום " + WEEKDAYS[parse(iso).getUTCDay()] + ", " + date(iso);
  }

  // "ינואר 2027"
  function monthYear(year, month) {
    return MONTHS[month] + " " + year;
  }

  var NOUNS = { tray: ["מגש", "מגשים"], kg: ["ק״ג", "ק״ג"], item: ["יחידה", "יחידות"] };
  var UNIT_PER = { tray: "למגש", kg: "לק״ג", item: "ליחידה" };

  // "3 מגשים", "1 מגש", "4 ק״ג"
  function qty(n, unit) {
    return n + " " + NOUNS[unit][n === 1 ? 0 : 1];
  }

  window.Fmt = {
    qty: qty,
    UNIT_PER: UNIT_PER,
    MONTHS: MONTHS,
    WEEKDAYS: WEEKDAYS,
    esc: esc,
    money: money,
    moneyDiff: moneyDiff,
    moneyText: moneyText,
    diffText: diffText,
    ltr: ltr,
    parse: parse,
    toIso: toIso,
    date: date,
    dateLong: dateLong,
    monthYear: monthYear
  };
})();

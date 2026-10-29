/* C5: review and submit the quotation request. Fake only, no network. */
(function () {
  "use strict";

  var F = window.Fmt;
  var O = window.Order;
  var order = O.load();
  var $ = function (id) { return document.getElementById(id); };

  function render() {
    var t = O.totals(order);
    var empty = t.lines.length === 0;

    $("event-ledger").innerHTML = O.eventLines(order.event).map(function (x) { return "<li>" + F.esc(x) + "</li>"; }).join("");
    $("lines").innerHTML = t.lines.map(function (l) {
      return '<li class="line"><p class="line__name">' + F.esc(l.dish.name) + "</p>" +
        '<p class="line__calc">' + F.esc(F.qty(l.qty, l.dish.unit)) + " × " + F.moneyText(l.dish.price) + "</p>" +
        '<p class="line__total"><span class="visually-hidden">סה״כ לשורה: </span>' + F.money(l.line) + "</p></li>";
    }).join("");
    $("lines").hidden = empty;
    $("totals").hidden = empty;
    $("empty").hidden = !empty;

    $("subtotal").innerHTML = F.money(t.subtotal);
    if (order.event.fulfillment === "pickup") {
      $("delivery-label").textContent = "איסוף עצמי";
      $("delivery").textContent = "ללא דמי משלוח";
    } else {
      $("delivery-label").textContent = "דמי משלוח" + (t.zone ? " ל" + t.zone.label : "");
      $("delivery").innerHTML = F.money(t.delivery);
    }
    $("total").innerHTML = F.money(t.total);
    $("send").setAttribute("aria-disabled", String(empty));
  }

  function setError(id, msg) {
    var el = $(id + "-error");
    el.hidden = !msg;
    el.textContent = msg || "";
    var input = $(id);
    if (msg) input.setAttribute("aria-invalid", "true"); else input.removeAttribute("aria-invalid");
  }

  function validate() {
    var bad = [];
    var name = $("name").value.trim();
    var digits = $("phone").value.replace(/\D/g, "");
    if (!name) { setError("name", "יש להזין שם מלא."); bad.push("name"); } else setError("name", "");
    if (digits.length < 9) { setError("phone", "יש להזין מספר טלפון תקין (לפחות 9 ספרות)."); bad.push("phone"); } else setError("phone", "");
    if (!$("ack").checked) { setError("ack", "יש לאשר שזו בקשה להצעת מחיר."); bad.push("ack"); } else setError("ack", "");
    return bad;
  }

  $("submit-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = $("send");
    if (btn.getAttribute("aria-disabled") === "true" || btn.disabled) return;
    var bad = validate();
    var summary = $("form-error");
    if (bad.length) {
      summary.textContent = "יש לתקן את הפרטים המסומנים לפני השליחה.";
      summary.hidden = false;
      $(bad[0]).focus();
      return;
    }
    summary.hidden = true;
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    btn.textContent = "שולחים…";
    window.setTimeout(function () {
      O.submit(order, { name: $("name").value.trim(), phone: $("phone").value.trim() });
      window.location.href = "c5-status.html";
    }, 900);
  });

  ["name", "phone"].forEach(function (id) {
    $(id).addEventListener("input", function () { if ($(id).hasAttribute("aria-invalid")) setError(id, ""); });
  });
  $("ack").addEventListener("change", function () { if ($("ack").checked) setError("ack", ""); });

  render();
})();

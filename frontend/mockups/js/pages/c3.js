/* C3: order summary and pricing. Fake data only, no network. */
(function () {
  "use strict";

  var F = window.Fmt;
  var order = window.Order.load();

  var $ = function (id) { return document.getElementById(id); };

  function renderEvent() {
    $("event-ledger").innerHTML = window.Order.eventLines(order.event).map(function (t) {
      return "<li>" + F.esc(t) + "</li>";
    }).join("");
  }

  function lineHtml(l) {
    var d = l.dish;
    return '<li class="line" data-id="' + d.id + '">' +
      '<p class="line__name">' + F.esc(d.name) + "</p>" +
      '<p class="line__calc">' + F.esc(F.qty(l.qty, d.unit)) + " × " + F.moneyText(d.price) + "</p>" +
      '<div class="line__qty">' + window.Stepper.html(d, l.qty, false) + "</div>" +
      '<p class="line__total"><span class="visually-hidden">סה״כ לשורה: </span>' + F.money(l.line) + "</p>" +
      "</li>";
  }

  function render() {
    var t = window.Order.totals(order);
    var empty = t.lines.length === 0;

    $("lines").innerHTML = t.lines.map(lineHtml).join("");
    $("lines").hidden = empty;
    $("empty").hidden = !empty;
    $("totals-sec").hidden = empty;
    $("edit-dishes").hidden = empty;
    $("mix-note").textContent = window.Order.mixNote(order);

    $("subtotal").innerHTML = F.money(t.subtotal);
    if (order.event.fulfillment === "pickup") {
      $("delivery-label").textContent = "איסוף עצמי";
      $("delivery").textContent = "ללא דמי משלוח";
    } else {
      $("delivery-label").textContent = "דמי משלוח" + (t.zone ? " ל" + t.zone.label : "");
      $("delivery").innerHTML = F.money(t.delivery);
    }
    $("total").innerHTML = F.money(t.total);

    var next = $("next");
    next.setAttribute("aria-disabled", String(empty));
    next.textContent = empty ? "הוסיפו מנות כדי להמשיך" : "המשך לשליחה";
  }

  window.Stepper.bind($("lines"), function () { return order; }, function (id, qty, btn) {
    order = window.Order.setQty(order, id, qty);
    render();
    // Keep focus on the same row's control; if the row is gone, move to the section heading.
    var row = $("lines").querySelector('[data-id="' + id + '"]');
    var keep = row && (row.querySelector('[data-act="' + btn.dataset.act + '"]') || row.querySelector("[data-act]"));
    (keep || $("lines-title")).focus();
  });

  $("next").addEventListener("click", function (e) {
    if (this.getAttribute("aria-disabled") === "true") e.preventDefault();
  });

  renderEvent();
  render();
})();

/* The fake "current order", shared by C1, C2 and C3.
   Kept in sessionStorage so it follows you between pages in the same tab; if storage is
   unavailable every page simply starts from the seeded sample order. No network. */
(function () {
  "use strict";

  var M = window.MOCK;
  var F = window.Fmt;
  var KEY = "mock-order-v1";

  function seed() {
    return JSON.parse(JSON.stringify({ version: 7, event: M.event, items: M.seedItems }));
  }

  function load() {
    try {
      var raw = window.sessionStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* storage blocked: fall through to the seed */ }
    return seed();
  }

  function save(order) {
    try { window.sessionStorage.setItem(KEY, JSON.stringify(order)); } catch (e) { /* ignore */ }
  }

  function dish(id) {
    return M.dishes.filter(function (d) { return d.id === id; })[0];
  }

  function qtyOf(order, id) {
    var it = order.items.filter(function (i) { return i.dishId === id; })[0];
    return it ? it.qty : 0;
  }

  // Sets one dish quantity (0 removes it) and returns the saved order.
  function setQty(order, id, qty) {
    order.items = order.items.filter(function (i) { return i.dishId !== id; });
    if (qty > 0) order.items.push({ dishId: id, qty: qty });
    order.version += 1;
    save(order);
    return order;
  }

  function setEvent(order, event) {
    order.event = Object.assign({}, event);
    save(order);
    return order;
  }

  // Pricing is the backend's job in the real app; here it is plain arithmetic on sample data.
  function totals(order) {
    var lines = order.items.map(function (i) {
      var d = dish(i.dishId);
      return { dish: d, qty: i.qty, line: d.price * i.qty };
    });
    var subtotal = lines.reduce(function (sum, l) { return sum + l.line; }, 0);
    var zone = M.zones.filter(function (z) { return z.id === order.event.zone; })[0];
    var delivery = order.event.fulfillment === "delivery" && zone ? zone.fee : 0;
    return { lines: lines, subtotal: subtotal, zone: zone, delivery: delivery, total: subtotal + delivery };
  }

  // Meat and dairy in one order is allowed (OPEN #9); we only tell the customer.
  function mixesMeatAndDairy(order) {
    var kinds = order.items.map(function (i) { return dish(i.dishId).kashrut; });
    return kinds.indexOf("meat") !== -1 && kinds.indexOf("dairy") !== -1;
  }

  function mixNote(order) {
    return mixesMeatAndDairy(order) ? "בהזמנה יש גם מנה חלבית וגם מנות בשריות. אפשר להמשיך, ומומלץ לוודא מול העסק." : "";
  }

  // Plain-text lines describing the event, for the C3 recap.
  function eventLines(ev) {
    var type = M.eventTypes.filter(function (t) { return t.id === ev.type; })[0];
    var slot = M.slots.filter(function (t) { return t.id === ev.slot; })[0];
    var zone = M.zones.filter(function (z) { return z.id === ev.zone; })[0];
    var total = ev.adults + ev.children;
    var diet = [];
    if (ev.vegetarian) diet.push(ev.vegetarian + " צמחונים");
    if (ev.vegan) diet.push(ev.vegan + " טבעונים");
    var out = [];
    out.push(type ? type.label : "סוג האירוע טרם נבחר");
    out.push(ev.date ? F.dateLong(ev.date) + (slot ? ", ⁦" + slot.label + "⁩" : "") : "תאריך טרם נבחר");
    out.push(total + " אורחים" + (diet.length ? ", מתוכם " + diet.join(" ו־") : ""));
    out.push(ev.fulfillment === "pickup" ? "איסוף עצמי מ" + M.pickupPoint : "משלוח ל" + (ev.address || (zone ? zone.label : "כתובת טרם הוזנה")));
    return out;
  }

  // "Sending" only flips the sample order to pending and freezes a copy of the prices.
  function submit(order, contact) {
    order.status = "pending";
    order.contact = contact;
    order.snapshot = {
      date: M.today,
      event: Object.assign({}, order.event),
      items: order.items.map(function (i) { return { dishId: i.dishId, qty: i.qty }; })
    };
    save(order);
    return order;
  }

  // Lines and totals for either the frozen snapshot or the live order.
  function view(order) {
    var src = order.snapshot ? { event: order.snapshot.event, items: order.snapshot.items, version: order.version } : order;
    return { event: src.event, totals: totals(src), date: order.snapshot ? order.snapshot.date : null };
  }

  window.Order = {
    submit: submit, view: view,
    load: load, save: save, dish: dish, qtyOf: qtyOf, setQty: setQty, setEvent: setEvent,
    totals: totals, mixesMeatAndDairy: mixesMeatAndDairy, mixNote: mixNote, eventLines: eventLines
  };

  /* ---------- Quantity stepper, used on dish cards (C2) and order lines (C3) ---------- */
  // html(): an "add" button when qty is 0 (and addable), otherwise a [-] qty [+] stepper.
  function html(d, qty, canAdd) {
    var name = F.esc(d.name);
    if (qty === 0 && canAdd) {
      return '<button type="button" class="btn btn--secondary btn--small" data-act="inc" data-id="' + d.id + '" aria-label="הוספה: ' + name + '">הוספה</button>';
    }
    return '<div class="counter__row" role="group" aria-label="כמות: ' + name + '">' +
      '<button type="button" class="counter__btn" data-act="dec" data-id="' + d.id + '" aria-label="הפחתת ' + name + '">−</button>' +
      '<span class="stepper__qty num">' + qty + "</span>" +
      '<button type="button" class="counter__btn" data-act="inc" data-id="' + d.id + '" aria-label="הוספת ' + name + '">+</button>' +
      "</div>";
  }

  // Delegated clicks: calls onChange(dishId, newQty) with the step already applied.
  function bind(root, getOrder, onChange) {
    root.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn || !root.contains(btn)) return;
      var d = dish(btn.dataset.id);
      var cur = qtyOf(getOrder(), d.id);
      var next = btn.dataset.act === "inc" ? cur + d.step : Math.max(0, cur - d.step);
      // Removing a dish is destructive: ask first where the list marks it (C3, C4).
      if (next === 0 && cur > 0 && root.dataset.confirmRemove === "true" &&
          !window.confirm("להסיר את " + d.name + " מההזמנה?")) return;
      onChange(d.id, next, btn);
    });
  }

  window.Stepper = { html: html, bind: bind };
})();

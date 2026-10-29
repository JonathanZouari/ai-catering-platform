/* C1: event configuration. Fake data only, no network. */
(function () {
  "use strict";

  var M = window.MOCK;
  var F = window.Fmt;
  var state;

  var $ = function (id) { return document.getElementById(id); };
  var form = $("event-form");

  var COUNTERS = [
    { key: "adults", label: "מבוגרים", hint: "אורחים בוגרים" },
    { key: "children", label: "ילדים", hint: "אורחים ילדים" },
    { key: "vegetarian", label: "צמחונים", hint: "מתוך כלל האורחים" },
    { key: "vegan", label: "טבעונים", hint: "מתוך כלל האורחים" }
  ];

  var view = { year: 2027, month: 0 };
  var pendingFocusIso = null;

  /* ---------- Rendering ---------- */

  function choiceHtml(name, id, label, checked) {
    return '<label class="choice"><input type="radio" name="' + name + '" value="' + id + '"' +
      (checked ? " checked" : "") + "> <span>" + label + "</span></label>";
  }

  function renderTypes() {
    $("type-choices").innerHTML = M.eventTypes.map(function (t) {
      return choiceHtml("type", t.id, F.esc(t.label), state.type === t.id);
    }).join("");
  }

  function renderSlots() {
    $("slot-choices").innerHTML = M.slots.map(function (s) {
      return choiceHtml("slot", s.id, F.ltr(s.label), state.slot === s.id);
    }).join("");
  }

  function renderCounters() {
    $("counters").innerHTML = COUNTERS.map(function (c) {
      return '<div class="counter">' +
        '<label class="counter__label" for="n-' + c.key + '">' + c.label + "</label>" +
        '<div class="counter__row">' +
        '<button type="button" class="counter__btn" data-step="-1" data-key="' + c.key + '" aria-label="הפחתת ' + c.label + '">−</button>' +
        '<input class="counter__value" id="n-' + c.key + '" name="' + c.key + '" type="number" inputmode="numeric" min="0" step="1" value="' + state[c.key] + '" data-key="' + c.key + '">' +
        '<button type="button" class="counter__btn" data-step="1" data-key="' + c.key + '" aria-label="הוספת ' + c.label + '">+</button>' +
        "</div>" +
        '<p class="hint">' + c.hint + "</p></div>";
    }).join("");
  }

  function renderZones() {
    $("zone").innerHTML = '<option value="">בחרו אזור</option>' + M.zones.map(function (z) {
      return '<option value="' + z.id + '"' + (state.zone === z.id ? " selected" : "") + ">" +
        F.esc(z.label) + " — " + F.moneyText(z.fee) + "</option>";
    }).join("");
  }

  function renderFulfillment() {
    var delivery = state.fulfillment === "delivery";
    form.elements.fulfillment.forEach(function (r) { r.checked = r.value === state.fulfillment; });
    $("delivery-block").hidden = !delivery;
    $("pickup-block").hidden = delivery;
    $("pickup-point").textContent = M.pickupPoint;
    renderFee();
  }

  function renderFee() {
    var label, amount = "";
    if (state.fulfillment === "pickup") {
      label = "איסוף עצמי — ללא דמי משלוח";
    } else {
      var z = M.zones.filter(function (x) { return x.id === state.zone; })[0];
      label = z ? "דמי משלוח ל" + z.label : "בחרו אזור משלוח כדי לראות את דמי המשלוח.";
      amount = z ? F.moneyText(z.fee) : "";
    }
    $("fee-label").textContent = label;
    $("fee-amount").textContent = amount;
  }

  var LRI = "\u2066", PDI = "\u2069";

  function setBand(id, text) {
    var el = $(id);
    el.textContent = text || "טרם נבחר";
    el.classList.toggle("is-empty", !text);
  }

  function ledgerItems() {
    var type = M.eventTypes.filter(function (t) { return t.id === state.type; })[0];
    var slot = M.slots.filter(function (t) { return t.id === state.slot; })[0];
    var z = M.zones.filter(function (x) { return x.id === state.zone; })[0];
    var total = state.adults + state.children;
    var items = [];

    items.push(type ? { t: type.label } : { t: "סוג האירוע טרם נבחר", empty: true });

    var when = [];
    if (state.date) when.push(F.dateLong(state.date));
    if (slot) when.push(LRI + slot.label + PDI);
    items.push(when.length ? { t: when.join(", ") } : { t: "תאריך ושעה טרם נבחרו", empty: true });

    var guests = total + " אורחים";
    var diet = [];
    if (state.vegetarian) diet.push(state.vegetarian + " צמחונים");
    if (state.vegan) diet.push(state.vegan + " טבעונים");
    if (diet.length) guests += ", מתוכם " + diet.join(" ו־");
    items.push(total ? { t: guests } : { t: "מספר האורחים טרם הוזן", empty: true });

    if (state.fulfillment === "pickup") items.push({ t: "איסוף עצמי, ללא דמי משלוח" });
    else items.push(z ? { t: "משלוח ל" + z.label + " · " + F.moneyText(z.fee) } : { t: "משלוח, אזור טרם נבחר", empty: true });
    return items;
  }

  function renderSummary() {
    var slot = M.slots.filter(function (t) { return t.id === state.slot; })[0];
    var z = M.zones.filter(function (x) { return x.id === state.zone; })[0];
    var total = state.adults + state.children;
    setBand("band-guests", total ? String(total) : "");
    setBand("band-date", state.date ? F.date(state.date) : "");
    setBand("band-slot", slot ? LRI + slot.label + PDI : "");
    setBand("band-fulfillment", state.fulfillment === "pickup" ? "איסוף עצמי" : "משלוח" + (z ? ", " + z.label : ""));

    $("ledger").innerHTML = ledgerItems().map(function (it) {
      return "<li" + (it.empty ? ' class="is-empty"' : "") + ">" + F.esc(it.t) + "</li>";
    }).join("");
  }

  function syncFields() {
    $("notes").value = state.notes;
    $("address").value = state.address;
  }

  /* ---------- Calendar ---------- */

  function disabledReason(iso) {
    if (iso < M.today) return "תאריך שעבר";
    if (F.parse(iso).getUTCDay() === 6) return "שבת";
    if (M.blockedDates.indexOf(iso) !== -1) return "תפוס";
    return "";
  }

  function monthIndex(y, m) { return y * 12 + m; }

  function inRange(y, m) {
    var r = M.calendarRange;
    return monthIndex(y, m) >= monthIndex(r.from[0], r.from[1]) && monthIndex(y, m) <= monthIndex(r.to[0], r.to[1]);
  }

  function renderCalendar() {
    var y = view.year, m = view.month;
    $("cal-title").textContent = F.monthYear(y, m);
    $("cal-prev").setAttribute("aria-disabled", String(!inRange(m === 0 ? y - 1 : y, (m + 11) % 12)));
    $("cal-next").setAttribute("aria-disabled", String(!inRange(m === 11 ? y + 1 : y, (m + 1) % 12)));

    var daysIn = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    var lead = new Date(Date.UTC(y, m, 1)).getUTCDay();
    var html = ["א", "ב", "ג", "ד", "ה", "ו", "ש"].map(function (d, i) {
      return '<div class="cal__dow" aria-hidden="true" title="יום ' + F.WEEKDAYS[i] + '">' + d + "</div>";
    }).join("");
    for (var i = 0; i < lead; i++) html += '<div class="cal__spacer"></div>';

    var firstEnabled = null;
    var tabIso = null;
    var monthPrefix = y + "-" + String(m + 1).padStart(2, "0") + "-";
    if (state.date && state.date.indexOf(monthPrefix) === 0) tabIso = state.date;

    var cells = [];
    for (var d = 1; d <= daysIn; d++) {
      var iso = monthPrefix + String(d).padStart(2, "0");
      var reason = disabledReason(iso);
      if (!reason && !firstEnabled) firstEnabled = iso;
      cells.push({ iso: iso, d: d, reason: reason });
    }
    if (!tabIso) tabIso = firstEnabled || cells[0].iso;

    html += cells.map(function (c) {
      var selected = c.iso === state.date;
      var label = F.dateLong(c.iso) + (c.reason ? " — לא זמין (" + c.reason + ")" : "");
      return '<button type="button" class="cal__day" data-iso="' + c.iso + '"' +
        ' aria-label="' + label + '"' +
        ' aria-pressed="' + selected + '"' +
        (c.reason ? ' aria-disabled="true"' : "") +
        ' tabindex="' + (c.iso === tabIso ? 0 : -1) + '"><span aria-hidden="true">' + c.d + "</span></button>";
    }).join("");
    $("cal-grid").innerHTML = html;

    if (pendingFocusIso) {
      var el = $("cal-grid").querySelector('[data-iso="' + pendingFocusIso + '"]');
      if (el) el.focus();
      pendingFocusIso = null;
    }
  }

  function renderDateStatus(msg) {
    $("date-status").textContent = msg !== undefined ? msg : (state.date ? "נבחר: " + F.dateLong(state.date) : "");
  }

  function changeMonth(delta) {
    var m = view.month + delta, y = view.year;
    if (m < 0) { m = 11; y--; }
    if (m > 11) { m = 0; y++; }
    if (!inRange(y, m)) return false;
    view.year = y; view.month = m;
    renderCalendar();
    return true;
  }

  function moveFocus(iso, days) {
    var d = F.parse(iso);
    d.setUTCDate(d.getUTCDate() + days);
    var target = F.toIso(d);
    var ty = d.getUTCFullYear(), tm = d.getUTCMonth();
    if (!inRange(ty, tm)) return;
    pendingFocusIso = target;
    if (ty !== view.year || tm !== view.month) { view.year = ty; view.month = tm; }
    renderCalendar();
  }

  $("cal-grid").addEventListener("click", function (e) {
    var btn = e.target.closest(".cal__day");
    if (!btn) return;
    var iso = btn.dataset.iso;
    var reason = disabledReason(iso);
    if (reason) {
      renderDateStatus(F.date(iso) + " אינו זמין (" + reason + "). בחרו תאריך אחר.");
      return;
    }
    state.date = iso;
    clearError("date");
    renderCalendar();
    renderDateStatus();
    var again = $("cal-grid").querySelector('[data-iso="' + iso + '"]');
    if (again) again.focus();
  });

  $("cal-grid").addEventListener("keydown", function (e) {
    var btn = e.target.closest(".cal__day");
    if (!btn) return;
    // In RTL the visually-right neighbour is the previous day.
    var map = { ArrowRight: -1, ArrowLeft: 1, ArrowUp: -7, ArrowDown: 7 };
    if (e.key in map) { e.preventDefault(); moveFocus(btn.dataset.iso, map[e.key]); }
    else if (e.key === "PageUp") { e.preventDefault(); if (changeMonth(-1)) focusFirstTab(); }
    else if (e.key === "PageDown") { e.preventDefault(); if (changeMonth(1)) focusFirstTab(); }
  });

  function focusFirstTab() {
    var el = $("cal-grid").querySelector('.cal__day[tabindex="0"]');
    if (el) el.focus();
  }

  $("cal-prev").addEventListener("click", function () { changeMonth(-1); });
  $("cal-next").addEventListener("click", function () { changeMonth(1); });

  /* ---------- Errors ---------- */

  var ERR_EL = {
    type: "type-error", date: "date-error", slot: "slot-error", guests: "guests-error",
    address: "address-error", zone: "zone-error"
  };

  function showError(key, msg) {
    var el = $(ERR_EL[key]);
    el.textContent = msg;
    el.hidden = false;
    if (key === "address") $("address").setAttribute("aria-invalid", "true");
    if (key === "zone") $("zone").setAttribute("aria-invalid", "true");
    if (key === "guests") {
      COUNTERS.forEach(function (c) {
        var inp = $("n-" + c.key);
        inp.setAttribute("aria-invalid", "true");
        inp.setAttribute("aria-describedby", "guests-error");
      });
    }
  }

  function clearError(key) {
    var el = $(ERR_EL[key]);
    el.hidden = true;
    el.textContent = "";
    if (key === "address") $("address").removeAttribute("aria-invalid");
    if (key === "zone") $("zone").removeAttribute("aria-invalid");
    if (key === "guests") {
      COUNTERS.forEach(function (c) {
        var inp = $("n-" + c.key);
        inp.removeAttribute("aria-invalid");
        inp.removeAttribute("aria-describedby");
      });
    }
    if (!$("error-list").children.length) return;
    var li = $("error-list").querySelector('[data-key="' + key + '"]');
    if (li) li.remove();
    if (!$("error-list").children.length) $("error-summary").hidden = true;
  }

  function validate() {
    var errs = [];
    if (!state.type) errs.push({ key: "type", target: "type-group", msg: "יש לבחור סוג אירוע." });
    if (!state.date) errs.push({ key: "date", target: "cal-grid", msg: "יש לבחור תאריך לאירוע." });
    if (!state.slot) errs.push({ key: "slot", target: "slot-group", msg: "יש לבחור שעה מבוקשת." });
    var total = state.adults + state.children;
    if (total < 1) {
      errs.push({ key: "guests", target: "n-adults", msg: "יש להזין לפחות אורח אחד." });
    } else if (state.vegetarian + state.vegan > total) {
      errs.push({ key: "guests", target: "n-vegetarian", msg: "מספר הצמחונים והטבעונים (" + (state.vegetarian + state.vegan) + ") גדול ממספר האורחים (" + total + ")." });
    }
    if (state.fulfillment === "delivery") {
      if (!state.address.trim()) errs.push({ key: "address", target: "address", msg: "יש להזין כתובת למשלוח." });
      if (!state.zone) errs.push({ key: "zone", target: "zone", msg: "יש לבחור אזור משלוח." });
    }
    return errs;
  }

  function targetFocus(id) {
    var el = $(id);
    if (!el) return;
    if (id === "type-group" || id === "slot-group") el = el.querySelector("input");
    else if (id === "cal-grid") el = el.querySelector('.cal__day[tabindex="0"]');
    if (el) el.focus();
  }

  function showErrors(errs) {
    Object.keys(ERR_EL).forEach(function (k) {
      $(ERR_EL[k]).hidden = true;
      $(ERR_EL[k]).textContent = "";
    });
    $("address").removeAttribute("aria-invalid");
    $("zone").removeAttribute("aria-invalid");
    COUNTERS.forEach(function (c) { $("n-" + c.key).removeAttribute("aria-invalid"); });

    errs.forEach(function (er) { showError(er.key, er.msg); });
    $("error-list").innerHTML = errs.map(function (er) {
      return '<li data-key="' + er.key + '"><a href="#' + er.target + '" data-target="' + er.target + '">' + F.esc(er.msg) + "</a></li>";
    }).join("");
    $("error-summary").hidden = errs.length === 0;
    if (errs.length) {
      $("error-summary").focus();
      $("error-summary").scrollIntoView({ block: "start" });
    }
  }

  $("error-list").addEventListener("click", function (e) {
    var a = e.target.closest("a");
    if (!a) return;
    e.preventDefault();
    targetFocus(a.dataset.target);
  });

  /* ---------- Inputs ---------- */

  function setCount(key, value) {
    var n = parseInt(value, 10);
    state[key] = isNaN(n) || n < 0 ? 0 : n;
  }

  $("counters").addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-step]");
    if (!btn) return;
    var key = btn.dataset.key;
    setCount(key, state[key] + Number(btn.dataset.step));
    $("n-" + key).value = state[key];
    clearError("guests");
  });

  $("counters").addEventListener("input", function (e) {
    var inp = e.target.closest("input[data-key]");
    if (!inp) return;
    setCount(inp.dataset.key, inp.value);
    clearError("guests");
  });

  $("counters").addEventListener("change", function (e) {
    var inp = e.target.closest("input[data-key]");
    if (inp) inp.value = state[inp.dataset.key];
  });

  $("type-choices").addEventListener("change", function (e) {
    state.type = e.target.value;
    clearError("type");
  });

  $("slot-choices").addEventListener("change", function (e) {
    state.slot = e.target.value;
    clearError("slot");
  });

  $("notes").addEventListener("input", function (e) { state.notes = e.target.value; });

  $("address").addEventListener("input", function (e) {
    state.address = e.target.value;
    if (state.address.trim()) clearError("address");
  });

  $("zone").addEventListener("change", function (e) {
    state.zone = e.target.value;
    if (state.zone) clearError("zone");
    renderFee();
  });

  Array.prototype.forEach.call(form.elements.fulfillment, function (r) {
    r.addEventListener("change", function () {
      state.fulfillment = r.value;
      if (r.value === "pickup") { clearError("address"); clearError("zone"); }
      renderFulfillment();
    });
  });

  form.addEventListener("input", renderSummary);
  form.addEventListener("change", renderSummary);
  $("cal-grid").addEventListener("click", function () { setTimeout(renderSummary, 0); });
  $("counters").addEventListener("click", renderSummary);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var errs = validate();
    showErrors(errs);
    if (!errs.length) {
      window.Order.setEvent(order, state);
      window.location.href = "c2-catalog.html";
    }
  });

  /* ---------- Init and demo controls ---------- */

  function init(initial) {
    state = Object.assign({}, initial);
    if (state.date) {
      var d = F.parse(state.date);
      view.year = d.getUTCFullYear();
      view.month = d.getUTCMonth();
    }
    renderTypes();
    renderSlots();
    renderCounters();
    renderZones();
    syncFields();
    renderFulfillment();
    renderCalendar();
    renderDateStatus();
    renderSummary();
    showErrors([]);
  }

  $("demo-reset").addEventListener("click", function () { init(M.event); });

  $("demo-errors").addEventListener("click", function () {
    init(Object.assign({}, M.event, {
      type: "", date: "", slot: "", adults: 2, children: 1, vegetarian: 5, vegan: 2, address: "", zone: ""
    }));
    showErrors(validate());
  });

  var order = window.Order.load();
  init(order.event);
})();

/* C4: AI assistant. A scripted fake chat, no backend, no network.
   Rule kept from the spec: the order changes ONLY when the customer approves a proposal.
   Reject, expire and the demo switcher never touch the order. */
(function () {
  "use strict";

  var M = window.MOCK;
  var F = window.Fmt;
  var O = window.Order;
  var order = O.load();

  var $ = function (id) { return document.getElementById(id); };
  var dlg = $("chat");
  var cards = [];
  var nextId = 1;

  /* ---------- Order column (left of the chat on desktop) ---------- */

  function lineHtml(l) {
    var d = l.dish;
    return '<li class="line" data-id="' + d.id + '">' +
      '<p class="line__name">' + F.esc(d.name) + "</p>" +
      '<p class="line__calc">' + F.esc(F.qty(l.qty, d.unit)) + " × " + F.moneyText(d.price) + "</p>" +
      '<div class="line__qty">' + window.Stepper.html(d, l.qty, false) + "</div>" +
      '<p class="line__total"><span class="visually-hidden">סה״כ לשורה: </span>' + F.money(l.line) + "</p></li>";
  }

  function renderOrder() {
    var t = O.totals(order);
    $("lines").innerHTML = t.lines.map(lineHtml).join("");
    $("subtotal").innerHTML = F.money(t.subtotal);
    if (order.event.fulfillment === "pickup") {
      $("delivery-label").textContent = "איסוף עצמי";
      $("delivery").textContent = "ללא דמי משלוח";
    } else {
      $("delivery-label").textContent = "דמי משלוח" + (t.zone ? " ל" + t.zone.label : "");
      $("delivery").innerHTML = F.money(t.delivery);
    }
    $("total").innerHTML = F.money(t.total);
  }

  window.Stepper.bind($("lines"), function () { return order; }, function (id, qty, btn) {
    order = O.setQty(order, id, qty);
    renderOrder();
    expireStale();
    var row = $("lines").querySelector('[data-id="' + id + '"]');
    var keep = row && (row.querySelector('[data-act="' + btn.dataset.act + '"]') || row.querySelector("[data-act]"));
    (keep || $("order-title")).focus();
  });

  /* ---------- Proposals ---------- */

  var STATE = {
    pending: { glyph: "●", label: "ממתינה לאישורכם" },
    applying: { glyph: "…", label: "מתעדכנת" },
    applied: { glyph: "✓", label: "בוצעה" },
    rejected: { glyph: "✕", label: "נדחתה" },
    expired: { glyph: "!", label: "פגה" }
  };

  // changes: [{ dishId, to }]. Rows and totals are computed here, never by the "model".
  function makeProposal(changes) {
    var rows = [];
    var copy = JSON.parse(JSON.stringify(order));
    changes.forEach(function (c) {
      var from = O.qtyOf(order, c.dishId);
      if (from !== c.to) rows.push({ dish: O.dish(c.dishId), from: from, to: c.to });
      copy.items = copy.items.filter(function (i) { return i.dishId !== c.dishId; });
      if (c.to > 0) copy.items.push({ dishId: c.dishId, qty: c.to });
    });
    var before = O.totals(order).total;
    var after = O.totals(copy).total;
    return { id: nextId++, changes: changes, rows: rows, before: before, after: after, baseVersion: order.version, real: "pending", demo: null };
  }

  function stateOf(c) { return c.demo || c.real; }

  function rowHtml(r) {
    var d = r.dish;
    var what = r.from === 0
      ? "הוספה · " + F.esc(d.name) + " · " + F.esc(F.qty(r.to, d.unit))
      : F.esc(d.name) + " · " + r.from + " ← " + F.esc(F.qty(r.to, d.unit));
    return "<li><span>" + what + '</span><span class="diff__amt">' + F.moneyDiff((r.to - r.from) * d.price) + "</span></li>";
  }

  function messageFor(st) {
    return {
      pending: "",
      applying: "מעדכן את ההזמנה…",
      applied: "השינוי בוצע. ההזמנה עודכנה.",
      rejected: "ההצעה נדחתה. ההזמנה לא השתנתה.",
      expired: "ההזמנה השתנתה, בקשו שוב."
    }[st];
  }

  function actionsHtml(st) {
    if (st === "pending" || st === "applying") {
      var off = st === "applying" ? " disabled" : "";
      return '<button type="button" class="btn btn--secondary btn--small" data-pact="reject"' + off + ">דחייה</button>" +
        '<button type="button" class="btn btn--small" data-pact="approve"' + off + ">אישור</button>";
    }
    if (st === "expired") return '<button type="button" class="btn btn--small" data-pact="renew">בקשו הצעה חדשה</button>';
    return "";
  }

  function cardHtml(c) {
    var st = stateOf(c);
    var diff = c.after - c.before;
    return '<article class="proposal" id="proposal-' + c.id + '" data-id="' + c.id + '" data-state="' + st + '" tabindex="-1"' +
      ' aria-labelledby="proposal-' + c.id + '-t"' + (st === "applying" ? ' aria-busy="true"' : "") + ">" +
      '<header class="proposal__head"><h3 id="proposal-' + c.id + '-t">הצעה לשינוי</h3>' +
      '<p class="proposal__state"><span aria-hidden="true">' + STATE[st].glyph + "</span> " + STATE[st].label + "</p></header>" +
      (c.demo ? '<p class="proposal__demo">תצוגת דמו: המראה בלבד</p>' : "") +
      '<ul class="diff">' + c.rows.map(rowHtml).join("") + "</ul>" +
      '<p class="proposal__total"><span>סה״כ</span><span>' + F.money(c.before) + " ← " + F.money(c.after) + " (" + F.moneyDiff(diff) + ")</span></p>" +
      (messageFor(st) ? '<p class="proposal__msg">' + messageFor(st) + "</p>" : "") +
      '<div class="proposal__actions">' + actionsHtml(st) + "</div></article>";
  }

  function renderCard(c, focus) {
    var el = $("proposal-" + c.id);
    el.outerHTML = cardHtml(c);
    if (focus) $("proposal-" + c.id).focus();
  }

  function announce(text) { $("sr").textContent = text; }

  /* ---------- Chat log ---------- */

  function addMessage(role, text, card) {
    var li = document.createElement("li");
    li.className = "msg msg--" + role;
    li.innerHTML = '<p class="msg__who">' + (role === "bot" ? "העוזר" : "אתם") + "</p>" +
      '<p class="msg__text">' + F.esc(text) + "</p>" + (card ? cardHtml(card) : "");
    $("log").appendChild(li);
    $("log").scrollTop = $("log").scrollHeight;
  }

  // The standing suggestion: built from real catalog dishes only.
  function suggestChanges() { return [{ dishId: "veg", to: 2 }, { dishId: "falafel", to: 4 }]; }

  function hasPending() {
    return cards.some(function (c) { return c.real === "pending" || c.real === "applying"; });
  }

  function propose(intro) {
    var c = makeProposal(suggestChanges());
    if (c.rows.length === 0) { addMessage("bot", "ההזמנה כבר כוללת את מה שהייתי מציע. אין הצעה חדשה כרגע."); return; }
    cards.push(c);
    addMessage("bot", intro, c);
    announce("הצעה חדשה לשינוי ממתינה לאישורכם");
  }

  // Only the three scripted questions are answered. Matching is exact, not by keyword:
  // the old keyword regex missed "האלרגנים" (it was written with a final-nun letter).
  var SCRIPTED = {
    "מה חסר לי בתפריט": function () {
      if (hasPending()) { addMessage("bot", "יש כבר הצעה פתוחה. אשרו או דחו אותה, ואז אציע שוב."); return; }
      propose("לפי 55 אורחים כדאי להוסיף ירקות קלויים ולהגדיל את כמות הפלאפל. זו הצעה, והיא תתבצע רק אם תאשרו:");
    },
    "יש מספיק לצמחונים": function () {
      var veg = O.totals(order).lines.filter(function (l) { return l.dish.veg; }).map(function (l) { return l.dish.name; });
      addMessage("bot", "יש באירוע 8 אורחים צמחונים וטבעונים. המנות בהזמנה שמסומנות כצמחוניות או טבעוניות: " + veg.join(", ") + ". כדאי לבדוק שהכמויות מספיקות להם.");
    },
    "מה האלרגנים בתבשיל הבקר": function () {
      addMessage("bot", "לתבשיל בקר ברוזמרין אין מידע מאומת על אלרגנים. אי אפשר להניח שהמנה נקייה מאלרגנים, ומומלץ לבדוק מול העסק.");
    }
  };

  function reply(q) {
    var answer = SCRIPTED[q.replace(/[?\s]+$/, "").trim()];
    if (answer) answer();
    else addMessage("bot", "בגרסת הדמו אפשר לשאול רק את השאלות המוכנות");
  }

  function send(text) {
    text = text.trim();
    if (!text) return;
    addMessage("user", text);
    window.setTimeout(function () { reply(text); }, 450);
  }

  $("chat-form").addEventListener("submit", function (e) {
    e.preventDefault();
    send($("msg").value);
    $("msg").value = "";
    $("msg").focus();
  });

  $("suggest").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-q]");
    if (b) send(b.dataset.q);
  });

  /* ---------- Proposal actions: approve is the only path that changes the order ---------- */

  function expireStale() {
    cards.forEach(function (c) {
      if (c.real === "pending" && c.baseVersion !== order.version) {
        c.real = "expired";
        renderCard(c, false);
        announce("ההצעה פגה: ההזמנה השתנתה");
      }
    });
  }

  function approve(c) {
    if (c.real !== "pending") return;
    c.real = "applying";
    renderCard(c, true);
    announce("מעדכן את ההזמנה");
    window.setTimeout(function () {
      if (order.version !== c.baseVersion) {
        c.real = "expired";
        announce("ההצעה פגה: ההזמנה השתנתה");
      } else {
        c.changes.forEach(function (ch) { O.setQty(order, ch.dishId, ch.to); });
        c.real = "applied";
        renderOrder();
        announce("השינוי בוצע. הסכום החדש הוא " + F.moneyText(O.totals(order).total));
      }
      renderCard(c, true);
      expireStale();
    }, 1200);
  }

  function reject(c) {
    if (c.real !== "pending") return;
    c.real = "rejected";
    renderCard(c, true);
    announce("ההצעה נדחתה. ההזמנה לא השתנתה");
  }

  $("log").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-pact]");
    if (!b || b.disabled) return;
    var c = cards.filter(function (x) { return x.id === Number(b.closest(".proposal").dataset.id); })[0];
    if (!c) return;
    if (b.dataset.pact === "approve") approve(c);
    else if (b.dataset.pact === "reject") reject(c);
    else if (b.dataset.pact === "renew") {
      if (hasPending()) return;
      propose("הנה הצעה מעודכנת לפי ההזמנה כפי שהיא עכשיו:");
    }
  });

  /* ---------- Demo switcher: changes how the latest card LOOKS, never the order ---------- */

  $("chat").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-demo]");
    if (!b) return;
    var c = cards[cards.length - 1];
    if (!c) return;
    c.demo = b.dataset.demo === "real" ? null : b.dataset.demo;
    renderCard(c, false);
    $("demo-status").textContent = c.demo ? "תצוגת דמו פעילה: המצב מוצג בלבד וההזמנה לא השתנתה." : "";
    $("proposal-" + c.id).scrollIntoView({ block: "nearest" });
  });

  /* ---------- Side panel on desktop, bottom sheet on phone ---------- */

  var desktop = window.matchMedia("(min-width: 1024px)");

  function toEnd() { $("log").scrollTop = $("log").scrollHeight; }

  // If the reader is at the newest message, stay there when the log's size changes (rotation, keyboard).
  var pinned = true;
  $("log").addEventListener("scroll", function () {
    var l = $("log");
    pinned = l.scrollHeight - l.clientHeight - l.scrollTop < 40;
  });
  if (window.ResizeObserver) new ResizeObserver(function () { if (pinned) toEnd(); }).observe($("log"));

  // On desktop the panel is simply "open" (no focus grab on page load); on phones it is a modal sheet.
  function place() {
    if (dlg.open) dlg.close();
    if (desktop.matches) { dlg.setAttribute("open", ""); toEnd(); }
  }

  $("fab").addEventListener("click", function () { if (!dlg.open) { dlg.showModal(); toEnd(); } });
  $("chat-close").addEventListener("click", function () { dlg.close(); });
  if (desktop.addEventListener) desktop.addEventListener("change", place);

  /* ---------- Start: a short scripted conversation ---------- */

  renderOrder();
  addMessage("bot", "שלום! אני העוזר של המטבח של סבתא. אפשר לשאול אותי על המנות, או לבקש הצעות לשינוי בהזמנה. כל שינוי יוצג לכם לאישור לפני שהוא מתבצע.");
  addMessage("user", "מה חסר לי בתפריט?");
  propose("לפי 55 אורחים כדאי להוסיף ירקות קלויים ולהגדיל את כמות הפלאפל. זו הצעה, והיא תתבצע רק אם תאשרו:");
  place();
})();

/* C2: dish catalog. Fake data only, no network. */
(function () {
  "use strict";

  var M = window.MOCK;
  var F = window.Fmt;
  var order = window.Order.load();
  var cat = "all";

  var $ = function (id) { return document.getElementById(id); };

  var KASHRUT = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };
  var VEG = { vegan: "טבעוני", vegetarian: "צמחוני" };

  function renderChips() {
    var all = [{ id: "all", label: "הכל" }].concat(M.categories);
    $("chips").innerHTML = all.map(function (c) {
      return '<button type="button" class="chip" data-cat="' + c.id + '" aria-pressed="' + (c.id === cat) + '">' + F.esc(c.label) + "</button>";
    }).join("");
  }

  function photoHtml(d) {
    if (!d.photo) return '<div class="dish__photo" aria-hidden="true"></div>';
    return '<div class="dish__photo"><img src="' + d.photo.src + '" width="800" height="1200" alt="' + F.esc(d.photo.alt) +
      '" loading="lazy" decoding="async" style="object-position: ' + d.photo.pos + '"></div>';
  }

  function badgesHtml(d) {
    var b = ['<li title="סוג המנה">' + KASHRUT[d.kashrut] + "</li>"];
    if (d.veg) b.push("<li>" + VEG[d.veg] + "</li>");
    return '<ul class="badges">' + b.join("") + "</ul>";
  }

  function allergensText(d) {
    return d.allergens ? "אלרגנים: " + d.allergens.join(", ") : "אלרגנים: מידע לא מאומת, יש לבדוק מול העסק";
  }

  function cardHtml(d) {
    return '<li class="dish" data-id="' + d.id + '">' + photoHtml(d) +
      '<div class="dish__body">' +
      '<h3 class="dish__name">' + F.esc(d.name) + "</h3>" +
      '<p class="dish__desc">' + F.esc(d.desc) + "</p>" +
      badgesHtml(d) +
      '<p class="dish__allergens' + (d.allergens ? "" : " is-unknown") + '">' + F.esc(allergensText(d)) + "</p>" +
      '<div class="dish__buy">' +
      '<p class="dish__price">' + F.money(d.price) + " " + F.UNIT_PER[d.unit] + "</p>" +
      '<div class="dish__ctl">' + window.Stepper.html(d, window.Order.qtyOf(order, d.id), true) + "</div>" +
      "</div></div></li>";
  }

  function renderDishes() {
    var list = M.dishes.filter(function (d) { return cat === "all" || d.cat === cat; });
    $("dishes").innerHTML = list.map(cardHtml).join("");
  }

  function renderCart() {
    var t = window.Order.totals(order);
    var n = t.lines.length;
    $("cart-sum").textContent = n === 0 ? "עדיין לא נבחרו מנות" :
      (n === 1 ? "מנה אחת" : n + " מנות") + " · " + F.moneyText(t.subtotal);
    var next = $("cart-next");
    next.setAttribute("aria-disabled", String(n === 0));
    next.textContent = n === 0 ? "בחרו לפחות מנה אחת" : "המשך לסיכום";
    $("mix-note").textContent = window.Order.mixNote(order);
  }

  $("chips").addEventListener("click", function (e) {
    var b = e.target.closest("button[data-cat]");
    if (!b) return;
    cat = b.dataset.cat;
    renderChips();
    renderDishes();
    var again = $("chips").querySelector('[data-cat="' + cat + '"]');
    if (again) again.focus();
  });

  window.Stepper.bind($("dishes"), function () { return order; }, function (id, qty, btn) {
    order = window.Order.setQty(order, id, qty);
    var card = btn.closest(".dish");
    card.querySelector(".dish__ctl").innerHTML = window.Stepper.html(window.Order.dish(id), qty, true);
    // Keep keyboard focus on the same kind of control after the swap.
    var keep = card.querySelector('[data-act="' + btn.dataset.act + '"]') || card.querySelector("[data-act]");
    if (keep) keep.focus();
    renderCart();
  });

  $("cart-next").addEventListener("click", function (e) {
    if (this.getAttribute("aria-disabled") === "true") e.preventDefault();
  });

  renderChips();
  renderDishes();
  renderCart();
})();

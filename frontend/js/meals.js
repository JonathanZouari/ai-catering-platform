// Order flow: event details, then a whole meal or up to two dishes per category, plus drinks, extras and delivery.
// shortcut: demo totals and storage in the browser, move to backend orders and pricing (ADR 0003) with the catalog API.
const ORDER_KEY = "yummai-order";
const EVENT_KEY = "yummai-event";
const DEFAULT_GUESTS = 40;
const DELIVERY = 120;
const LIMIT = 2; // dishes per category

const eventForm = document.getElementById("event-form"); // event page only
const menu = document.getElementById("menu"); // menu page only
const orderPage = document.getElementById("order-page"); // my order page only
const needsEvent = Boolean(orderPage || document.getElementById("quote"));
const fmt = (n) => `‎₪${n.toLocaleString("en-US")}`;
const all = (selector, root = document) => [...root.querySelectorAll(selector)];
const qty = (el) => Math.max(0, Math.floor(Number(el.value) || 0));

const storageWorks = (() => {
  try {
    sessionStorage.setItem("yummai-test", "1");
    sessionStorage.removeItem("yummai-test");
    return true;
  } catch {
    return false;
  }
})();

function read(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key));
  } catch {
    return null;
  }
}

function write(key, value) {
  if (storageWorks) sessionStorage.setItem(key, JSON.stringify(value));
}

const guestCount = (event) => (event ? Number(event.adults) + Number(event.kids) : DEFAULT_GUESTS);

function eventSummary(event) {
  const date = event.date.split("-").reverse().join(".");
  const handover = event.delivery === "pickup" ? "איסוף עצמי" : "משלוח";
  return `${event.typeLabel} · ${date} · ${guestCount(event)} אורחים · ${handover}`;
}

// Menu page

const line = (el, count, kind) => ({ name: el.dataset.name, price: Number(el.dataset.price), qty: count, kind });
const counted = (selector, kind) =>
  all(selector, menu)
    .filter((el) => qty(el) > 0)
    .map((el) => line(el, qty(el), kind ?? el.dataset.extra));

function readOrder(guests) {
  const extras = counted("[data-extra]");
  if (!document.getElementById("meal-add").checked) {
    return { lines: [...all("[data-pick]:checked", menu).map((el) => line(el, guests, "food")), ...extras], notes: "" };
  }
  const cuisine = menu.querySelector('input[name="cuisine"]:checked');
  const drinks = counted(`.meal[data-cuisine="${cuisine.value}"] [data-drink]`, "drink");
  const notes = document.getElementById("meal-notes").value;
  return { lines: [line(cuisine, guests, "food"), ...drinks, ...extras], notes };
}

function readForm() {
  return {
    cuisine: menu.querySelector('input[name="cuisine"]:checked').value,
    added: document.getElementById("meal-add").checked,
    notes: document.getElementById("meal-notes").value,
    picks: all("[data-pick]:checked", menu).map((el) => el.id),
    amounts: Object.fromEntries(all("[data-drink], [data-extra]", menu).map((el) => [el.id, qty(el)])),
  };
}

function restoreForm(form) {
  const cuisine = all('input[name="cuisine"]', menu).find((el) => el.value === form.cuisine);
  if (cuisine) cuisine.checked = true;
  document.getElementById("meal-add").checked = form.added;
  document.getElementById("meal-notes").value = form.notes;
  all("[data-pick]", menu).forEach((el) => (el.checked = form.picks.includes(el.id)));
  all("[data-drink], [data-extra]", menu).forEach((el) => (el.value = form.amounts[el.id] ?? 0));
}

function limitPicks() {
  const sections = all("#pick .cat-section", menu);
  let picked = 0;
  sections.forEach((section) => {
    const boxes = all("[data-pick]", section);
    const count = boxes.filter((el) => el.checked).length;
    picked += count;
    boxes.forEach((el) => (el.disabled = !el.checked && count >= LIMIT));
    section.querySelector("[data-count]").textContent = `נבחרו ${count} מתוך ${LIMIT}`;
  });
  const goal = sections.length * LIMIT;
  document.getElementById("pick-progress").textContent =
    picked === goal ? `הארוחה שלכם מוכנה: ${goal} מנות נבחרו` : `נבחרו ${picked} מתוך ${goal} מנות`;
}

function showGuestPrices(guests) {
  all('input[name="cuisine"]', menu).forEach((cuisine) => {
    const label = menu.querySelector(`.meal[data-cuisine="${cuisine.value}"] .price small`);
    label.textContent = `לסועד · ${guests} אורחים: ${fmt(cuisine.dataset.price * guests)}`;
  });
}

// My order page

function renderLines(id, lines, emptyText) {
  document.getElementById(id).replaceChildren(
    ...(lines.length ? lines : [{ name: emptyText }]).map((item) => {
      const row = document.createElement("li");
      const cell = (text, className) => {
        const span = document.createElement("span");
        span.textContent = text;
        if (className) span.className = className;
        return span;
      };
      row.append(cell(item.name));
      if (item.qty) row.append(cell(`${item.qty} × ${fmt(item.price)}`, "calc"), cell(fmt(item.price * item.qty), "amt"));
      return row;
    }),
  );
}

function renderEventDetails(event) {
  const rows = [
    ["סוג האירוע", event.typeLabel],
    ["תאריך", event.date.split("-").reverse().join(".")],
    ["שעת הגעה", event.slot],
    ["אורחים", `${guestCount(event)} (מתוכם ${event.kids} ילדים)`],
    ["מה אוכלים", `${event.omnivores} אוכלים הכול, ${event.vegetarians} צמחונים, ${event.vegans} טבעונים`],
    ["הערות", event.notes || "אין"],
  ];
  document.getElementById("event-details").replaceChildren(
    ...rows.flatMap(([term, value]) => {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = value;
      return [dt, dd];
    }),
  );
}

function renderOrderPage(order, event) {
  const ofKind = (kind) => order.lines.filter((item) => item.kind === kind);
  const food = ofKind("food");
  renderEventDetails(event);
  renderLines("lines-food", food, "עדיין לא נבחרו מנות");
  renderLines("lines-drink", ofKind("drink"), "עדיין לא הוספתם משקאות");
  renderLines("lines-tools", ofKind("tools"), "עדיין לא הוספתם כלים או אביזרים");

  const note = document.getElementById("meal-note");
  note.hidden = !order.notes;
  note.textContent = order.notes ? `הערות לארוחה: ${order.notes}` : "";

  document.getElementById("address-field").hidden = event.delivery === "pickup";
  const send = document.getElementById("send-order");
  send.href = food.length ? "/customer/quote.html" : "/customer/menu.html";
  send.textContent = food.length ? "שליחת ההזמנה" : "בחירת מנות";
}

function bindDelivery(event) {
  all('input[name="delivery"]', orderPage).forEach((el) => (el.checked = el.value === event.delivery));
  const address = document.getElementById("address");
  address.value = event.address;
  orderPage.addEventListener("input", () => {
    event.delivery = orderPage.querySelector('input[name="delivery"]:checked').value;
    event.address = address.value;
    write(EVENT_KEY, event);
    render();
  });
}

// All pages

function render() {
  const event = read(EVENT_KEY);
  const guests = guestCount(event);
  if (menu) {
    limitPicks();
    showGuestPrices(guests);
  }
  const order = menu ? readOrder(guests) : read(ORDER_KEY)?.order ?? { lines: [], notes: "" };
  if (menu) write(ORDER_KEY, { order, form: readForm() });

  const subtotal = order.lines.reduce((sum, item) => sum + item.price * item.qty, 0);
  const fee = order.lines.length && event?.delivery !== "pickup" ? DELIVERY : 0;
  const values = {
    subtotal: fmt(subtotal),
    fee: fmt(fee),
    grand: fmt(subtotal + fee),
    label: `סה"כ משוער · ${order.lines.length} פריטים`,
  };
  all("[data-total]").forEach((el) => (el.textContent = values[el.dataset.total]));
  if (event) all("[data-event]").forEach((el) => (el.textContent = (el.dataset.prefix ?? "") + eventSummary(event)));
  if (orderPage) renderOrderPage(order, event);
}

if (needsEvent && storageWorks && !read(EVENT_KEY)) location.replace("/customer/#event");

if (eventForm) {
  const saved = read(EVENT_KEY);
  if (saved) {
    Object.entries(saved).forEach(([name, value]) => {
      if (eventForm.elements[name]) eventForm.elements[name].value = value;
    });
  }
  eventForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const typeLabel = eventForm.querySelector('input[name="type"]:checked').parentElement.textContent.trim();
    write(EVENT_KEY, { ...Object.fromEntries(new FormData(eventForm)), typeLabel });
    location.href = eventForm.getAttribute("action");
  });
}

if (menu) {
  if (read(EVENT_KEY) || !storageWorks) {
    all("[data-next]").forEach((link) => {
      link.href = "/customer/order.html";
      link.textContent = link.dataset.next;
    });
  }
  const saved = read(ORDER_KEY);
  if (saved?.form) restoreForm(saved.form);
  menu.addEventListener("input", render);
}

if (orderPage && read(EVENT_KEY)) bindDelivery(read(EVENT_KEY));
if (!eventForm && (!needsEvent || read(EVENT_KEY))) render();

// Customer ordering, one page for every caterer. The private token stays in the URL fragment.
import { api } from "/js/api.js";
import { chatButton, mountChat, syncChat } from "/js/customer/chat.js";
import { attempt, field, h, notify, select, textOrNull } from "/js/ui.js";

const slug = location.pathname.split("/")[2];
const app = document.getElementById("app");
const state = { order: null, token: null, step: "details", panelOpen: false };

const EVENT_TYPES = ["יום הולדת", "בר/בת מצווה", "ברית", "שבת משפחתית", "אירוע משפחתי", "אחר"];
const UNITS = { per_tray: "למגש", per_guest: "לסועד", per_item: "ליחידה", per_weight: "לפי משקל" };
const KASHRUT = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };
const STATUS = {
  draft: "טיוטה",
  pending_approval: "ממתין לאישור הקייטרינג",
  approved: "ההזמנה אושרה",
  rejected: "ההזמנה נדחתה",
};
const STATUS_HELP = {
  pending_approval: "התשובה תופיע כאן. פתחו את הקישור הפרטי שוב כדי לבדוק.",
  approved: "התשלום מתואם ישירות מול העסק.",
  rejected: "אפשר לפנות לעסק כדי לבדוק אפשרות אחרת.",
};
let refreshSheet = null;
let categoryWatcher = null;
const STEPS = [["details", "פרטי האירוע"], ["menu", "תפריט"], ["summary", "סיכום"]];

const shekel = (value) => `₪${Number(value).toFixed(2)}`;
const money = (value) => h("bdi", {}, shekel(value));

function orderApi(path, options = {}) {
  const headers = { "X-Order-Token": state.token };
  return api(`/api/orders/${state.order.id}${path}`, { ...options, headers });
}

const privateLink = () =>
  `${location.origin}/c/${slug}/#order=${state.order.id}.${state.token}`;

function useBrand(caterer) {
  document.title = caterer.name;
  const color = caterer.brand_color;
  if (color && contrastWithWhite(color) >= 4.5) {
    document.documentElement.style.setProperty("--color-accent", color);
  }
}

function contrastWithWhite(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05);
}

const photoUrl = (path) =>
  (path && state.config.storage_public_url ? `${state.config.storage_public_url}/${path}` : null);
const icon = (name) => h("span", { className: `icon icon-${name}`, "aria-hidden": "true" });
const dateText = (value) => new Date(`${value}T12:00`).toLocaleDateString("he-IL");
const isDraft = () => !state.order || state.order.status === "draft";

function steps() {
  return h("ol", { className: "steps" }, STEPS.map(([key, label]) => {
    if (key === state.step) return h("li", { "aria-current": "step" }, h("span", {}, label));
    return h("li", {}, state.order
      ? h("button", { type: "button", onclick: () => leaveStep(key) }, label)
      : h("span", {}, label));
  }));
}

// Leaving the details form saves it first, so edits aren't lost.
function leaveStep(key) {
  const form = document.querySelector("form.card");
  if (state.step !== "details" || !form) return go(key);
  state.nextStep = key;
  form.requestSubmit();
  state.nextStep = null;
}

const yummaiLabel = () => h("img", { className: "yummai-label", src: "/img/yummai-logo.svg", alt: "Yummai" });

function sideColumn(extra) {
  const { caterer } = state;
  const logo = photoUrl(caterer.logo_path);
  return h("aside", { className: "side" },
    yummaiLabel(),
    h("div", { className: "logo" }, logo ? h("img", { src: logo, alt: "" }) : caterer.name[0]),
    h("h1", {}, `ברוכים הבאים ל${caterer.name}`),
    h("p", {}, `כשרות: ${caterer.kashrut_status ?? "לא צוין"}`),
    isDraft() ? steps() : null,
    extra,
    h("p", { className: "side-footer" }, `© ${caterer.name}`));
}

function frame(content, { nav = null, action = null } = {}) {
  const hasOrderColumn = isDraft();
  app.replaceChildren(h("div", { className: hasOrderColumn ? "frame" : "frame two" },
    sideColumn(nav),
    h("div", { className: "middle" }, content.filter(Boolean)),
    hasOrderColumn ? orderPanel(action) : null),
  hasOrderColumn && state.order ? bottomBar(action) : "");
  window.scrollTo(0, 0);
}

function setPanelOpen(isOpen) {
  state.panelOpen = isOpen;
  document.querySelector(".order-panel")?.classList.toggle("open", isOpen);
}

function renderStep() {
  if (state.order && state.order.status !== "draft") return renderStatus();
  if (state.step === "menu") return renderMenu();
  if (state.step === "summary") return renderSummary();
  return renderDetails();
}

function render() {
  renderStep();
  refreshSheet?.();
  syncChat(state.order?.status === "draft" && state.step !== "details");
}

function applyOrder(order) {
  const position = window.scrollY;
  state.order = order;
  render();
  window.scrollTo(0, position);
}

function numberField(label, value, hint) {
  const input = h("input", { type: "number", min: "0", inputMode: "numeric", value: value ?? 0 });
  return { input, element: field(label, input, hint) };
}

function renderDetails() {
  const { availability, cities, order } = state;
  const name = h("input", { required: true, minLength: 2, maxLength: 120, autocomplete: "name", value: order?.customer.full_name ?? "" });
  const phone = h("input", { type: "tel", required: true, dir: "ltr", autocomplete: "tel", pattern: "[0-9+\\-\\s]{9,20}", value: order?.customer.phone ?? "" });
  const eventType = select(EVENT_TYPES.map((type) => [type, type]), order?.event.event_type);
  const date = h("input", { type: "date", required: true, min: availability.earliest_date, value: order?.event.event_date ?? "" });
  const adults = numberField("מבוגרים", order?.event.adults);
  const children = numberField("ילדים", order?.event.children);
  const vegetarian = numberField("צמחונים", order?.event.vegetarian_guests);
  const vegan = numberField("טבעונים", order?.event.vegan_guests);
  const restricted = numberField("הגבלות אחרות", order?.event.restricted_guests);
  const notes = h("textarea", { rows: 2, maxLength: 1000, value: order?.event.dietary_notes ?? "" });
  const type = select([["pickup", "איסוף עצמי"], ["delivery", "משלוח"]], order?.fulfillment_type);
  const slot = h("select", { required: true });
  const city = select([["", "בחרו עיר"], ...cities.map((c) => [c.city, `${c.city} (${shekel(c.fee)})`])], order?.delivery_city ?? "");
  const address = h("input", { maxLength: 300, autocomplete: "street-address", value: order?.delivery_address ?? "" });
  const deliveryFields = h("div", {}, field("עיר", city), field("כתובת", address));

  const refreshSlots = () => {
    deliveryFields.hidden = type.value !== "delivery";
    // getDay() matches our convention: 0 = Sunday. Noon avoids timezone edges.
    const weekday = date.value ? new Date(`${date.value}T12:00`).getDay() : null;
    const options = availability.slots.filter((s) => s.fulfillment_type === type.value
      && (s.weekday === null || s.weekday === weekday));
    const current = slot.value || order?.time_slot_id;
    slot.replaceChildren(
      h("option", { value: "" }, date.value ? "בחרו שעה" : "בחרו קודם תאריך"),
      ...options.map((s) => h("option", { value: s.id }, `${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)}`)));
    slot.value = options.some((s) => s.id === current) ? current : "";
  };
  date.addEventListener("change", refreshSlots);
  type.addEventListener("change", refreshSlots);
  refreshSlots();

  const form = h("form", {
    className: "card",
    onsubmit: async (event) => {
      event.preventDefault();
      const nextStep = state.nextStep ?? "menu";
      const guests = Number(adults.input.value) + Number(children.input.value);
      const diets = Number(vegetarian.input.value) + Number(vegan.input.value) + Number(restricted.input.value);
      if (guests === 0) return notify("יש להזין לפחות סועד אחד", true);
      if (diets > guests) return notify("הצמחונים, הטבעונים וההגבלות נספרים מתוך מספר הסועדים, ולכן הם לא יכולים לעבור אותו", true);
      const delivery = type.value === "delivery";
      const details = {
        customer: { full_name: name.value.trim(), phone: phone.value.trim() },
        event: {
          event_type: eventType.value,
          event_date: date.value,
          adults: Number(adults.input.value),
          children: Number(children.input.value),
          vegetarian_guests: Number(vegetarian.input.value),
          vegan_guests: Number(vegan.input.value),
          restricted_guests: Number(restricted.input.value),
          dietary_notes: textOrNull(notes.value),
        },
        fulfillment_type: type.value,
        time_slot_id: slot.value,
        delivery_city: delivery ? city.value : null,
        delivery_address: delivery ? textOrNull(address.value) : null,
      };
      const saved = await attempt(() => (state.order
        ? orderApi("", { method: "PATCH", body: JSON.stringify({ ...details, version: state.order.version }) })
        : api(`/api/c/${slug}/orders`, { method: "POST", body: JSON.stringify(details) })));
      if (!saved) return;
      if (saved.token) {
        state.token = saved.token;
        state.order = saved.order;
        history.replaceState(null, "", `#order=${state.order.id}.${state.token}`);
      } else {
        state.order = saved;
      }
      go(nextStep);
    },
  },
  h("h2", {}, "פרטי האירוע"),
  field("שם מלא", name),
  field("טלפון", phone),
  field("סוג האירוע", eventType),
  h("h3", {}, "מספר סועדים"),
  h("div", { className: "grid" }, adults.element, children.element),
  h("p", { className: "muted" }, "מתוך הסועדים שלמעלה, כמה הם:"),
  h("div", { className: "grid" }, vegetarian.element, vegan.element, restricted.element),
  field("הערות תזונה ואלרגיות", notes, "ההערות מגיעות לעסק ולעוזר ה-AI, ואינן מבטיחות התאמה. אל תכתבו כאן שמות"),
  h("h3", {}, "מתי ואיך"),
  field("איסוף או משלוח", type),
  field("תאריך", date),
  field("שעה", slot),
  deliveryFields,
  h("button", { type: "submit" }, "המשך לתפריט"));

  frame([form]);
}

function allergenInfo(dish) {
  const statuses = Object.fromEntries(dish.allergens.map((a) => [a.allergen_id, a.status]));
  const named = (status) => state.allergens.filter((a) => (statuses[a.id] ?? "unknown") === status).map((a) => a.name);
  const row = (label, names) => (names.length ? h("p", {}, `${label}: ${names.join(", ")}`) : null);
  return h("section", { className: "sheet-allergens" },
    h("h3", {}, "מידע על אלרגנים"),
    row("מכיל", named("contains")),
    row("לא מכיל", named("free")),
    row("לא ידוע (לא אומת)", named("unknown")),
    h("p", { className: "muted" }, "מידע שלא אומת אינו אומר שהמנה בטוחה. באלרגיה חמורה בדקו עם העסק לפני ההזמנה."));
}

function dishFacts(dish) {
  const { kashrut_class: kashrut, is_vegetarian: vegetarian, is_vegan: vegan } = dish.dietary ?? {};
  const diet = (name, label) => h("span", { className: "diet", title: label }, icon(name), h("span", { className: "visually-hidden" }, label));
  return h("div", { className: "dish-meta" },
    vegan === true ? diet("sprout", "טבעוני") : null,
    vegetarian === true && vegan !== true ? diet("leaf", "צמחוני") : null,
    h("span", {}, `כשרות: ${KASHRUT[kashrut] ?? "לא צוין"} · קלוריות: ${dish.calories_per_portion ?? "לא צוין"}`));
}

// The page re-renders after a change, so focus returns to the same control where it still exists.
function restoreFocus(dishId, label, areaSelector) {
  const area = areaSelector ? document.querySelector(areaSelector) : document;
  const same = [...area.querySelectorAll("button")].find((button) => button.getAttribute("aria-label") === label && !button.disabled);
  const target = same ?? area.querySelector(`[data-more="${dishId}"]`) ?? area.querySelector("button");
  target?.focus({ preventScroll: true });
}

async function setQuantity(dish, quantity) {
  const path = `/items/${dish.id}`;
  const pressed = document.activeElement;
  const label = pressed?.getAttribute("aria-label");
  const areaSelector = ["dialog.dish-sheet", ".order-panel"].find((selector) => pressed?.closest(selector));
  const updated = await attempt(() => (quantity > 0
    ? orderApi(path, { method: "PUT", body: JSON.stringify({ quantity: String(quantity), version: state.order.version }) })
    : orderApi(`${path}?version=${state.order.version}`, { method: "DELETE" })));
  if (updated) {
    const position = window.scrollY;
    const panelPosition = document.querySelector(".order-panel")?.scrollTop ?? 0;
    state.order = updated;
    render();
    window.scrollTo(0, position);
    const panel = document.querySelector(".order-panel");
    if (panel) panel.scrollTop = panelPosition;
    restoreFocus(dish.id, label, areaSelector);
  }
}

function quantityStep(dish) {
  return dish.pricing_unit === "per_weight" ? 0.5 : 1;
}

function stepper(dish, quantity) {
  const step = quantityStep(dish);
  return h("div", { className: "stepper" },
    h("button", { type: "button", "aria-label": `פחות ${dish.name}`, disabled: quantity === 0, onclick: () => setQuantity(dish, quantity - step) }, "−"),
    h("output", { "aria-label": `כמות ${dish.name}` }, String(quantity)),
    h("button", { type: "button", "aria-label": `עוד ${dish.name}`, "data-more": dish.id, onclick: () => setQuantity(dish, quantity + step) }, "+"));
}

function quantityControl(dish) {
  const line = state.order.lines.find((item) => item.dish_id === dish.id);
  const quantity = Number(line?.quantity ?? 0);
  return h("div", { className: "qty" },
    line?.recommended_quantity ? h("span", { className: "muted" }, `מומלץ: ${Number(line.recommended_quantity)}`) : null,
    stepper(dish, quantity),
    quantity === 0
      ? h("button", { type: "button", className: "bag", "aria-label": `הוספת ${dish.name}`, onclick: () => setQuantity(dish, quantityStep(dish)) }, icon("bag"))
      : h("span", { className: "bag in-order" }, icon("bag")));
}

function price(dish) {
  return h("div", { className: "dish-price" },
    h("strong", {}, money(dish.unit_price)),
    h("small", {}, `${UNITS[dish.pricing_unit]}${dish.unit_label ? ` (${dish.unit_label})` : ""}`));
}

// Quantity changes re-render the page behind the sheet, so the sheet refreshes its own control.
function openDish(dish) {
  const photo = photoUrl(dish.image_path);
  const quantity = h("div", {}, quantityControl(dish));
  const notice = document.getElementById("notice");
  const noticeHome = notice.parentElement;
  const dialog = h("dialog", { className: "dish-sheet", "aria-label": dish.name },
    photo ? h("img", { className: "sheet-photo", src: photo, alt: "" }) : null,
    h("div", { className: "sheet-body" },
      h("h2", {}, dish.name),
      dishFacts(dish),
      dish.description ? h("p", { className: "muted" }, dish.description) : null,
      price(dish),
      quantity,
      allergenInfo(dish),
      h("div", { className: "actions" },
        h("button", { type: "button", className: "secondary", onclick: () => dialog.close() }, "סגירה"))));
  refreshSheet = () => quantity.replaceChildren(quantityControl(dish));
  dialog.addEventListener("close", () => {
    refreshSheet = null;
    noticeHome.append(notice);
    dialog.remove();
    document.querySelector(`[data-dish="${dish.id}"]`)?.focus();
  });
  document.body.append(dialog);
  // A modal dialog covers the page, so errors have to show from inside it.
  dialog.append(notice);
  dialog.showModal();
}

function dishCard(dish) {
  const photo = photoUrl(dish.image_path);
  return h("article", { className: "dish" },
    // Pointer shortcut only: the name below is the keyboard and screen reader route.
    h("button", { type: "button", className: "dish-media", tabIndex: -1, "aria-hidden": "true", onclick: () => openDish(dish) },
      photo ? h("img", { src: photo, alt: "", loading: "lazy" }) : dish.name[0]),
    h("div", { className: "dish-body" },
      h("div", { className: "dish-top" },
        h("h3", {}, h("button", { type: "button", className: "dish-open", "data-dish": dish.id, onclick: () => openDish(dish) }, dish.name)),
        price(dish)),
      dish.description ? h("p", { className: "muted dish-description" }, dish.description) : null,
      dishFacts(dish),
      h("div", { className: "dish-foot" },
        h("button", { type: "button", className: "text-link", onclick: () => openDish(dish) }, "מידע על אלרגנים"),
        quantityControl(dish))));
}

function matchesFilters(dish) {
  const { filters } = state;
  return (!filters.vegetarian || dish.dietary?.is_vegetarian === true)
    && (!filters.vegan || dish.dietary?.is_vegan === true);
}

function filterChip(label, key) {
  const box = h("input", {
    type: "checkbox",
    checked: state.filters[key],
    onchange: () => {
      state.filters[key] = box.checked;
      render();
    },
  });
  return h("label", {}, box, label);
}

function categorySection({ category, dishes }) {
  const count = dishes.length === 1 ? "מנה אחת" : `${dishes.length} מנות`;
  return h("section", { className: "menu-section", "data-category": category.id },
    h("div", { className: "category-title" }, h("h2", {}, category.name), h("span", {}, count)),
    dishes.map(dishCard));
}

// Scrolls by code: a link would replace the private token in the URL fragment.
function categoryNav(sections) {
  const scrollTo = (id) => document.querySelector(`[data-category="${id}"]`)?.scrollIntoView();
  return h("nav", { className: "category-nav", "aria-label": "קטגוריות" },
    sections.map(({ category }) => h("button", { type: "button", "data-for": category.id, onclick: () => scrollTo(category.id) }, category.name)));
}

function watchCategories() {
  categoryWatcher?.disconnect();
  categoryWatcher = new IntersectionObserver((entries) => {
    const visible = entries.find((entry) => entry.isIntersecting);
    if (!visible) return;
    document.querySelectorAll(".category-nav button").forEach((button) => {
      button.setAttribute("aria-current", String(button.dataset.for === visible.target.dataset.category));
    });
  }, { rootMargin: "0px 0px -70% 0px" });
  document.querySelectorAll("[data-category]").forEach((section) => categoryWatcher.observe(section));
}

function orderLine(line) {
  const dish = state.dishes.find((item) => item.id === line.dish_id);
  const photo = photoUrl(dish?.image_path);
  const quantity = Number(line.quantity);
  return h("li", { className: "order-line" },
    h("div", { className: "line-photo" },
      photo ? h("img", { src: photo, alt: "", loading: "lazy" }) : null,
      h("span", { className: "line-count" }, String(quantity))),
    h("strong", {}, line.name),
    h("span", { className: "price" }, money(line.line_total)),
    dish ? stepper(dish, quantity) : h("span", {}),
    // Offered even for a dish no longer on the menu, or the customer couldn't remove it.
    h("button", { type: "button", className: "line-remove", "aria-label": `הסרת ${line.name}`, onclick: () => setQuantity({ id: line.dish_id }, 0) }, icon("trash")));
}

function menuPhoto() {
  const photo = photoUrl(state.dishes.find((dish) => dish.image_path)?.image_path);
  return photo ? h("img", { className: "panel-photo", src: photo, alt: "" }) : null;
}

function chosenDishes(order) {
  const pictured = order.lines
    .map((line) => ({ line, photo: photoUrl(state.dishes.find((dish) => dish.id === line.dish_id)?.image_path) }))
    .filter(({ photo }) => photo);
  return pictured.length
    ? h("div", { className: "chosen" }, pictured.map(({ line, photo }) => h("figure", {},
      h("img", { src: photo, alt: "" }), h("figcaption", {}, line.name))))
    : null;
}

function orderPanel(action) {
  const { order } = state;
  return h("aside", { className: state.panelOpen ? "order-panel open" : "order-panel", "aria-label": "ההזמנה שלי" },
    order ? h("div", { className: "panel-person" }, h("span", {}, order.customer.full_name), h("span", { className: "icon-box" }, icon("person"))) : null,
    h("div", { className: "panel-title" },
      h("h2", {}, "ההזמנה שלי"),
      h("button", { type: "button", className: "secondary phone-only", onclick: () => setPanelOpen(false) }, "סגירה")),
    order ? h("p", { className: "date-label" }, order.fulfillment_type === "delivery" ? "משלוח" : "איסוף עצמי") : null,
    order ? h("button", { type: "button", className: "date-box", "aria-label": "שינוי פרטי האירוע", onclick: () => go("details") },
      dateText(order.event.event_date), icon("calendar")) : null,
    order?.lines.length ? null : menuPhoto(),
    order?.lines.length
      ? h("ul", { className: "order-lines" }, order.lines.map(orderLine))
      : h("p", { className: "empty order-lines" }, "עדיין לא נבחרו מנות."),
    order ? totals(order) : null,
    action ? h("button", { className: "checkout", disabled: action.disabled, onclick: action.run }, action.label) : null,
    order ? chatButton() : null);
}

function bottomBar(action) {
  const { order } = state;
  return h("div", { className: "total-bar" },
    h("div", { className: "total-sum" }, "סה״כ ", h("strong", {}, money(order.total))),
    h("button", { type: "button", className: "secondary", onclick: () => setPanelOpen(true) }, `ההזמנה שלי (${order.lines.length})`),
    h("div", { className: "actions" },
      chatButton(),
      action && state.step !== "summary" ? h("button", { onclick: action.run }, action.label) : null));
}

function renderMenu() {
  const visible = state.dishes.filter(matchesFilters);
  const sections = state.categories
    .map((category) => ({ category, dishes: visible.filter((dish) => dish.category_id === category.id) }))
    .filter(({ dishes }) => dishes.length);

  frame([
    h("div", { className: "chips" }, filterChip("צמחוני", "vegetarian"), filterChip("טבעוני", "vegan")),
    ...(sections.length
      ? sections.map(categorySection)
      : [h("p", { className: "empty" }, "אין מנות שמתאימות לסינון.")]),
  ], { nav: categoryNav(sections), action: { label: "לסיכום", run: () => go("summary") } });
  watchCategories();
}

function go(step) {
  state.step = step;
  state.panelOpen = false;
  render();
}

function linesTable(order) {
  return h("table", { className: "lines" },
    h("thead", {}, h("tr", {}, h("th", {}, "מנה"), h("th", { className: "num" }, "כמות"), h("th", { className: "num" }, "סכום"))),
    h("tbody", {}, order.lines.map((line) => h("tr", {},
      h("td", {}, line.name, line.recommended_quantity && Number(line.recommended_quantity) !== Number(line.quantity)
        ? h("div", { className: "muted" }, `מומלץ: ${Number(line.recommended_quantity)}`) : null),
      h("td", { className: "num" }, h("bdi", {}, `${Number(line.quantity)} × ${shekel(line.unit_price)}`)),
      h("td", { className: "num" }, money(line.line_total))))));
}

function totals(order) {
  const row = (label, value, extra = "") => h("div", { className: `sum ${extra}` }, h("span", {}, label), money(value));
  return [
    row("סכום המנות", order.subtotal),
    order.fulfillment_type === "delivery" ? row("משלוח", order.delivery_fee) : null,
    row("סה״כ כולל מע״מ", order.total, "total"),
  ];
}

function linkActions() {
  const link = privateLink();
  const share = `https://wa.me/?text=${encodeURIComponent(link)}`;
  return h("section", { className: "card" },
    h("h2", {}, "הקישור הפרטי להזמנה"),
    h("p", { className: "private-link", dir: "ltr" }, link),
    h("p", { className: "muted" }, "שמרו את הקישור, ואל תשתפו אותו. כל מי שמחזיק בו יכול לראות את ההזמנה ואת הפרטים שלכם. אין דרך לשחזר אותו אם יאבד."),
    h("div", { className: "actions" },
      h("button", { className: "secondary", onclick: () => attempt(() => navigator.clipboard.writeText(link), "הקישור הועתק") }, "העתקת הקישור"),
      h("a", { className: "button-link", href: share, target: "_blank", rel: "noopener noreferrer" }, "שליחה לעצמי בוואטסאפ")));
}

function renderSummary() {
  const { order } = state;
  const { status, has_unknown: hasUnknown } = order.kashrut;
  const acknowledge = h("input", { type: "checkbox" });

  const submit = async () => {
    const body = { version: order.version, acknowledge_kashrut_warning: acknowledge.checked };
    const updated = await attempt(() => orderApi("/submit", { method: "POST", body: JSON.stringify(body) }));
    if (updated) {
      state.order = updated;
      render();
    }
  };

  const canSubmit = status !== "blocked" && order.lines.length > 0;
  frame([
    chosenDishes(order),
    h("section", { className: "card phone-only" },
      h("h2", {}, "סיכום ההזמנה"),
      order.lines.length ? linesTable(order) : h("p", { className: "empty" }, "עדיין לא נבחרו מנות."),
      totals(order)),
    status === "blocked"
      ? h("p", { className: "alert blocked", role: "alert" }, "העסק לא מאפשר הזמנה שמערבת מנות בשריות וחלביות. הסירו אחת מהן כדי להמשיך.")
      : null,
    status === "warn"
      ? h("div", { className: "alert" }, h("p", {}, "ההזמנה כוללת מנות בשריות וחלביות יחד."),
        h("label", {}, acknowledge, " הבנתי ואני רוצה להמשיך"))
      : null,
    hasUnknown ? h("p", { className: "alert" }, "לחלק מהמנות לא צוינה כשרות. בדקו עם העסק אם זה חשוב לכם.") : null,
    linkActions(),
    h("p", { className: "muted" }, "שליחת הבקשה אינה הזמנה סופית. ההזמנה תאושר רק לאחר בדיקה של העסק."),
    h("div", { className: "actions" },
      h("button", { className: "secondary", onclick: () => go("menu") }, "חזרה לתפריט"),
      h("button", { className: "phone-only", disabled: !canSubmit, onclick: submit }, "שליחת בקשה להצעת מחיר")),
  ], { action: { label: "שליחת בקשה להצעת מחיר", run: submit, disabled: !canSubmit } });
}

async function refresh() {
  const updated = await attempt(() => orderApi(""));
  if (updated) {
    state.order = updated;
    render();
  }
}

function renderStatus() {
  const { order } = state;
  const phone = state.caterer.contact_phone;
  frame([
    h("section", { className: "card" },
      h("h2", {}, "סטטוס ההזמנה"),
      h("div", { className: `status-banner ${order.status}` },
        h("p", { className: "status" }, STATUS[order.status]),
        h("p", {}, STATUS_HELP[order.status])),
      order.decision_note ? h("p", {}, h("strong", {}, "הערת העסק: "), order.decision_note) : null,
      phone ? h("p", {}, "טלפון העסק: ", h("a", { href: `tel:${phone.replace(/\s/g, "")}` }, h("bdi", {}, phone))) : null,
      h("button", { className: "secondary", onclick: refresh }, "בדיקת עדכון")),
    h("section", { className: "card" },
      h("h2", {}, "פרטי ההזמנה"),
      linesTable(order),
      totals(order)),
    linkActions(),
  ]);
}

function renderUnavailable() {
  app.replaceChildren(h("section", { className: "card" },
    yummaiLabel(),
    h("h1", {}, "העמוד אינו זמין"),
    h("p", {}, "לא מצאנו את הקייטרינג שחיפשתם. בדקו את הקישור מול העסק.")));
}

async function loadOrder() {
  const match = location.hash.match(/^#order=([^.]+)\.(.+)$/);
  if (!match) return;
  [, , state.token] = match;
  state.order = { id: match[1] };
  try {
    state.order = await orderApi("");
    state.step = "menu";
  } catch {
    state.order = null;
    state.token = null;
    notify("הקישור להזמנה אינו תקין", true);
  }
}

async function start() {
  try {
    const base = `/api/c/${slug}`;
    state.caterer = await api(base);
    [state.config, state.allergens, state.categories, state.dishes, state.availability, state.cities] = await Promise.all([
      api("/api/config"),
      api("/api/allergens"),
      api(`${base}/catalog/categories`),
      api(`${base}/catalog/dishes`),
      api(`${base}/availability`),
      api(`${base}/delivery-cities`),
    ]);
  } catch {
    renderUnavailable();
    return;
  }
  state.filters = { vegetarian: false, vegan: false };
  useBrand(state.caterer);
  mountChat(orderApi, applyOrder);
  await loadOrder();
  render();
}

start();

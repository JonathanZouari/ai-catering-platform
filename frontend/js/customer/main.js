// Customer ordering, one page for every caterer. The private token stays in the URL fragment.
import { api } from "/js/api.js";
import { attempt, field, h, notify, select, textOrNull } from "/js/ui.js";

const slug = location.pathname.split("/")[2];
const app = document.getElementById("app");
const state = { order: null, token: null, step: "details" };

const EVENT_TYPES = ["יום הולדת", "בר/בת מצווה", "ברית", "שבת משפחתית", "אירוע משפחתי", "אחר"];
const UNITS = { per_tray: "למגש", per_guest: "לסועד", per_item: "ליחידה", per_weight: "לפי משקל" };
const KASHRUT = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };
const STATUS = {
  draft: "טיוטה",
  pending_approval: "ממתין לאישור הקייטרינג",
  approved: "אושר",
  rejected: "נדחה",
};
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

function header() {
  const { caterer, config } = state;
  return h("header", {},
    h("div", { className: "brand" },
      caterer.logo_path && config.storage_public_url
        ? h("img", { src: `${config.storage_public_url}/${caterer.logo_path}`, alt: "" })
        : null,
      h("h1", {}, caterer.name)),
    h("p", { className: "muted" }, `כשרות: ${caterer.kashrut_status ?? "לא צוין"}`));
}

function steps() {
  return h("ol", { className: "steps" }, STEPS.map(([key, label]) =>
    h("li", key === state.step ? { "aria-current": "step" } : {}, label)));
}

function show(...content) {
  app.replaceChildren(header(), ...content.filter(Boolean));
  window.scrollTo(0, 0);
}

function render() {
  if (state.order && state.order.status !== "draft") return renderStatus();
  if (state.step === "menu") return renderMenu();
  if (state.step === "summary") return renderSummary();
  return renderDetails();
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
      state.step = "menu";
      render();
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
  field("הערות תזונה ואלרגיות", notes, "ההערות מגיעות לעסק, ואינן מבטיחות התאמה"),
  h("h3", {}, "מתי ואיך"),
  field("איסוף או משלוח", type),
  field("תאריך", date),
  field("שעה", slot),
  deliveryFields,
  h("button", { type: "submit" }, "המשך לתפריט"));

  show(steps(), form);
}

function allergenDetails(dish) {
  const statuses = Object.fromEntries(dish.allergens.map((a) => [a.allergen_id, a.status]));
  const named = (status) => state.allergens.filter((a) => (statuses[a.id] ?? "unknown") === status).map((a) => a.name);
  const row = (label, names) => (names.length ? h("p", {}, `${label}: ${names.join(", ")}`) : null);
  return h("details", {},
    h("summary", {}, "מידע על אלרגנים"),
    row("מכיל", named("contains")),
    row("לא מכיל", named("free")),
    row("לא ידוע (לא אומת)", named("unknown")),
    h("p", { className: "muted" }, "מידע שלא אומת אינו אומר שהמנה בטוחה. באלרגיה חמורה בדקו עם העסק לפני ההזמנה."));
}

function badges(dish) {
  const { kashrut_class: kashrut, is_vegetarian: vegetarian, is_vegan: vegan } = dish.dietary ?? {};
  const badge = (text) => h("span", { className: "badge" }, text);
  return h("div", { className: "badges" },
    badge(`כשרות: ${KASHRUT[kashrut] ?? "לא צוין"}`),
    vegan === true ? badge("טבעוני") : null,
    vegetarian === true && vegan !== true ? badge("צמחוני") : null,
    badge(`קלוריות: ${dish.calories_per_portion ?? "לא צוין"}`));
}

async function setQuantity(dish, quantity) {
  const path = `/items/${dish.id}`;
  const updated = await attempt(() => (quantity > 0
    ? orderApi(path, { method: "PUT", body: JSON.stringify({ quantity: String(quantity), version: state.order.version }) })
    : orderApi(`${path}?version=${state.order.version}`, { method: "DELETE" })));
  if (updated) {
    const position = window.scrollY;
    state.order = updated;
    render();
    window.scrollTo(0, position);
  }
}

function stepper(dish) {
  const line = state.order.lines.find((item) => item.dish_id === dish.id);
  const quantity = Number(line?.quantity ?? 0);
  const step = dish.pricing_unit === "per_weight" ? 0.5 : 1;
  return h("div", { className: "stepper" },
    h("button", { type: "button", className: "secondary", "aria-label": `פחות ${dish.name}`, disabled: quantity === 0, onclick: () => setQuantity(dish, quantity - step) }, "−"),
    h("output", { "aria-label": `כמות ${dish.name}` }, String(quantity)),
    h("button", { type: "button", className: "secondary", "aria-label": `עוד ${dish.name}`, onclick: () => setQuantity(dish, quantity + step) }, "+"),
    line?.recommended_quantity ? h("span", { className: "muted" }, `מומלץ: ${Number(line.recommended_quantity)}`) : null);
}

function dishCard(dish) {
  const { storage_public_url: storage } = state.config;
  return h("article", { className: "dish" },
    dish.image_path && storage ? h("img", { src: `${storage}/${dish.image_path}`, alt: "", loading: "lazy" }) : null,
    h("h3", {}, dish.name),
    dish.description ? h("p", { className: "muted" }, dish.description) : null,
    h("p", {}, money(dish.unit_price), ` ${UNITS[dish.pricing_unit]}`, dish.unit_label ? ` (${dish.unit_label})` : ""),
    badges(dish),
    allergenDetails(dish),
    stepper(dish));
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

function renderMenu() {
  const visible = state.dishes.filter(matchesFilters);
  const sections = state.categories
    .map((category) => ({ category, dishes: visible.filter((dish) => dish.category_id === category.id) }))
    .filter(({ dishes }) => dishes.length);

  show(
    steps(),
    h("div", { className: "chips" }, filterChip("צמחוני", "vegetarian"), filterChip("טבעוני", "vegan")),
    ...(sections.length
      ? sections.map(({ category, dishes }) => h("section", { className: "card" }, h("h2", {}, category.name), dishes.map(dishCard)))
      : [h("p", { className: "empty" }, "אין מנות שמתאימות לסינון.")]),
    h("div", { className: "total-bar" },
      h("div", {}, "סה״כ ", h("strong", {}, money(state.order.total))),
      h("div", { className: "actions" },
        h("button", { className: "secondary", onclick: () => go("details") }, "חזרה"),
        h("button", { onclick: () => go("summary") }, "לסיכום"))),
  );
}

function go(step) {
  state.step = step;
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
    h("p", { className: "private-link" }, h("bdi", { dir: "ltr" }, link)),
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

  show(
    steps(),
    h("section", { className: "card" },
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
      h("button", { disabled: status === "blocked" || !order.lines.length, onclick: submit }, "שליחת בקשה להצעת מחיר")),
  );
}

function renderStatus() {
  const { order } = state;
  show(
    h("section", { className: "card" },
      h("h2", {}, "סטטוס ההזמנה"),
      h("p", { className: "status" }, STATUS[order.status]),
      order.decision_note ? h("p", {}, order.decision_note) : null,
      linesTable(order),
      totals(order)),
    linkActions(),
  );
}

function renderUnavailable() {
  app.replaceChildren(h("section", { className: "card" },
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
  await loadOrder();
  render();
}

start();

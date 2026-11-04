// The customer site: homepage, event details, menu, summary and order status.
// One page for the site's caterer ("/", SITE_CATERER) and for /c/{slug}/.
// The private order token stays in the URL fragment, so in-page navigation never uses "#" links.
import { api } from "/js/api.js";
import { chatButton, mountChat, syncChat } from "/js/customer/chat.js";
import { startHero } from "/js/customer/hero.js";
import { attempt, h, notify, textOrNull } from "/js/ui.js";

const app = document.getElementById("app");
const state = {
  slug: null,
  order: null,
  token: null,
  step: "home",
  panelOpen: false,
  filters: { category: "all", diets: new Set() },
  draft: null, // event details typed but not saved yet
  errors: {},
  pendingDish: null, // a dish the customer tried to add before giving event details
};

const EVENT_TYPES = ["יום הולדת", "בר/בת מצווה", "ברית", "שבת משפחתית", "אירוע משפחתי", "אירוע עסקי", "אחר"];
const UNITS = { per_tray: "למגש", per_guest: "לסועד", per_item: "ליחידה", per_weight: "לפי משקל" };
const KASHRUT = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };
const STATUS = {
  draft: "טיוטה",
  pending_approval: "ממתין לאישור הקייטרינג",
  approved: "ההזמנה אושרה",
  rejected: "ההזמנה נדחתה",
};
const STATUS_HELP = {
  pending_approval: "קיבלנו את הבקשה. התשובה תופיע כאן, פתחו את הקישור הפרטי שוב כדי לבדוק.",
  approved: "התשלום מתואם ישירות מול העסק.",
  rejected: "אפשר לפנות לעסק כדי לבדוק אפשרות אחרת.",
};
const STATUS_ICON = { pending_approval: "hourglass_empty", approved: "check_circle", rejected: "cancel" };
const STEPS = [["details", "פרטי האירוע", "edit_calendar"], ["menu", "תפריט מנות", "restaurant_menu"], ["summary", "סיכום והזמנה", "receipt_long"]];
// Filters match only what a dish's own data confirms. Unknown never matches.
const DIET_FILTERS = [
  ["meat", "בשרי", (dish) => dish.dietary?.kashrut_class === "meat"],
  ["dairy", "חלבי", (dish) => dish.dietary?.kashrut_class === "dairy"],
  ["pareve", "פרווה", (dish) => dish.dietary?.kashrut_class === "pareve"],
  ["vegetarian", "צמחוני", (dish) => dish.dietary?.is_vegetarian === true],
  ["vegan", "טבעוני", (dish) => dish.dietary?.is_vegan === true],
  ["gluten_free", "ללא גלוטן", (dish) => allergenStatus(dish, glutenId()) === "free"],
];

let refreshSheet = null;
let stopHero = null;

const shekel = (value) => `₪${Number(value).toFixed(2)}`;
const money = (value) => h("bdi", {}, shekel(value));
const icon = (name, extra = "") => h("span", { className: `icon icon-${name} ${extra}`.trim(), "aria-hidden": "true" });
const dateText = (value) => new Date(`${value}T12:00`).toLocaleDateString("he-IL");
const isDraft = () => !state.order || state.order.status === "draft";
const count = (n, one, many) => (n === 1 ? one : `${n} ${many}`);
const glutenId = () => state.allergens.find((a) => a.name === "גלוטן")?.id;
const allergenStatus = (dish, id) => dish.allergens.find((a) => a.allergen_id === id)?.status ?? "unknown";
const photoUrl = (path) =>
  (path && state.config.storage_public_url ? `${state.config.storage_public_url}/${path}` : null);
const quantityOf = (dish) => Number(state.order?.lines.find((line) => line.dish_id === dish.id)?.quantity ?? 0);

function orderApi(path, options = {}) {
  const headers = { "X-Order-Token": state.token };
  return api(`/api/orders/${state.order.id}${path}`, { ...options, headers });
}

// The site's own caterer is at "/", any other caterer at /c/{slug}/.
const privateLink = () => `${location.origin}${state.slug === state.config.site_caterer ? "/" : `/c/${state.slug}/`}#order=${state.order.id}.${state.token}`;

function useBrand(caterer) {
  document.title = `${caterer.name} | קייטרינג לאירועים`;
  const color = caterer.brand_color;
  if (color && contrastWithWhite(color) >= 4.5) document.documentElement.style.setProperty("--secondary", color);
}

function contrastWithWhite(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 1.05 / (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05);
}

// ---------- Navigation ----------

// Steps live in history, so the browser's back button works, and the URL (with its token) never changes.
function go(step, { push = true, focus = true, target = null } = {}) {
  if (!isDraft() && step !== "home") step = "status";
  if (step === "summary" && !state.order) step = "details";
  if (step === state.step && !target) return render();
  if (step !== state.step) state.errors = {};
  state.step = step;
  state.panelOpen = false;
  if (push) history.pushState({ step }, "", location.href);
  render();
  if (target) document.getElementById(target)?.scrollIntoView();
  else window.scrollTo(0, 0);
  if (focus) (document.querySelector("#main h1") ?? document.getElementById("main"))?.focus({ preventScroll: true });
}

window.addEventListener("popstate", (event) => {
  state.step = event.state?.step ?? (state.order ? "menu" : "home");
  if (!isDraft() && state.step !== "home") state.step = "status";
  state.panelOpen = false;
  render();
});

// Leaving the details form of an existing order saves it first, so edits aren't lost.
// Without an order yet, what was typed stays in state.draft until the customer comes back.
function leaveTo(step) {
  const form = document.querySelector("form.details-form");
  if (state.step !== "details" || !form || !state.order) return go(step);
  state.nextStep = step;
  form.requestSubmit();
}

function render() {
  if (state.step !== "home") { stopHero?.(); stopHero = null; }
  const view = VIEWS[state.step] ?? renderHome;
  app.replaceChildren(header(), ...view(), footer());
  if (state.step === "home") stopHero = startHero(document.querySelector(".hero-media"));
  refreshSheet?.();
  syncChat(state.order?.status === "draft" && state.step !== "home" && state.step !== "details");
}

function applyOrder(order) {
  const position = window.scrollY;
  state.order = order;
  render();
  window.scrollTo(0, position);
}

// ---------- Shell ----------

function logo(size = "") {
  const src = photoUrl(state.caterer.logo_path) ?? "/img/brand/logo.jpg";
  return h("img", { className: `brand-logo ${size}`.trim(), src, alt: "", width: 72, height: 48 });
}

function header() {
  const { caterer } = state;
  const inFlow = ["details", "menu"].includes(state.step);
  const inOrder = ["summary", "status"].includes(state.step);
  const navButton = (label, isCurrent, onclick) => h("button", {
    type: "button", className: "nav-link", onclick, ...(isCurrent ? { "aria-current": "page" } : {}),
  }, label);
  const phone = caterer.contact_phone;
  return h("header", { className: "site-header" },
    h("div", { className: "site-header-inner" },
      h("button", { type: "button", className: "brand", onclick: () => go("home"), "aria-label": `${caterer.name}, דף הבית` },
        logo(),
        h("span", { className: "brand-text" },
          h("strong", {}, caterer.name),
          caterer.kashrut_status ? h("small", {}, icon("verified"), caterer.kashrut_status) : null)),
      h("nav", { className: "site-nav", "aria-label": "ניווט ראשי" },
        navButton("תפריט ואירוע", inFlow, () => leaveTo("menu")),
        navButton("ההזמנה שלי", inOrder, () => leaveTo(state.order ? "summary" : "details")),
        navButton("אודות", false, () => go("home", { target: "about" }))),
      phone
        ? h("a", { className: "phone-pill", href: `tel:${phone.replace(/\s/g, "")}` },
          icon("call"), h("bdi", {}, phone), h("span", { className: "phone-label" }, "מוקד הזמנות"))
        : null));
}

function footer() {
  const { caterer } = state;
  return h("footer", { className: "site-footer" },
    h("div", { className: "site-footer-inner" },
      h("div", { className: "footer-brand" },
        h("strong", {}, `${caterer.name} – קייטרינג לאירועים`),
        caterer.kashrut_status ? h("span", {}, `כשרות: ${caterer.kashrut_status}`) : null),
      h("div", { className: "footer-links" },
        caterer.contact_phone ? h("a", { href: `tel:${caterer.contact_phone.replace(/\s/g, "")}` }, "שירות לקוחות: ", h("bdi", {}, caterer.contact_phone)) : null,
        h("span", {}, `© ${new Date().getFullYear()} ${caterer.name}`))));
}

// ---------- Homepage ----------

function renderHome() {
  const { caterer, dishes } = state;
  const video = h("video", {
    className: "hero-video is-hidden",
    muted: true,
    playsInline: true,
    preload: "none",
    poster: "/media/hero-poster.jpg",
    disablePictureInPicture: true,
    tabIndex: -1,
    "data-src": "/media/hero.mp4",
    disableremoteplayback: "",
  });
  const pictured = dishes.filter((dish) => dish.image_path).slice(0, 3);
  const features = [
    ["local_florist", "100% טריות יומיומית", "חומרי גלם מובחרים וטריים"],
    ["menu_book", "תפריט בהתאמה אישית", "צמחוני, טבעוני וחלבי/בשרי"],
    caterer.kashrut_status ? ["verified", "כשרות", caterer.kashrut_status] : null,
    ["schedule", "עמידה מדויקת בזמנים", state.cities.length ? "איסוף עצמי או משלוח לאירוע" : "איסוף עצמי בשעה שנקבעה"],
  ].filter(Boolean);
  const hasOrder = Boolean(state.order);

  return [h("main", { id: "main", tabIndex: -1, className: "home" },
    h("section", { className: "hero", "aria-labelledby": "hero-title" },
      h("div", { className: "hero-media", "aria-hidden": "true" },
        h("img", { className: "hero-poster", src: "/media/hero-poster.jpg", alt: "", width: 1376, height: 768, fetchPriority: "high" }),
        video,
        h("div", { className: "hero-scrim" }),
        h("div", { className: "hero-fade" })),
      h("div", { className: "hero-content" },
        h("p", { className: "hero-chip" },
          h("span", { className: "dot", "aria-hidden": "true" }),
          icon("stars"),
          h("span", {}, "חוויית קולינריה עילית לאירועים", caterer.kashrut_status ? ` • ${caterer.kashrut_status}` : "")),
        h("p", { className: "hero-sub" }, icon("dinner_dining"), `${caterer.name} • קייטרינג לאירועים בוטיק בהתאמה אישית`),
        h("h1", { id: "hero-title", tabIndex: -1 }, "אמנות הטעמים,", h("br"), h("span", {}, "בכל אירוע מחדש.")),
        h("p", { className: "hero-lead" }, "קייטרינג מוקפד לאירועים פרטיים ועסקיים"),
        h("div", { className: "hero-actions" },
          h("button", { type: "button", className: "accent pill hero-primary", onclick: () => go("menu") },
            "לצפייה בתפריט", icon("arrow_forward")),
          h("button", { type: "button", className: "pill hero-secondary", onclick: () => go(hasOrder ? "menu" : "details") },
            icon("edit_calendar"), hasOrder ? "להמשך ההזמנה שלכם" : "לתכנון האירוע שלכם")))),
    h("section", { className: "features", "aria-label": `למה ${caterer.name}` },
      h("ul", {}, features.map(([name, title, text]) => h("li", {},
        h("span", { className: "icon-tile" }, icon(name)),
        h("span", {}, h("strong", {}, title), h("small", {}, text)))))),
    pictured.length
      ? h("section", { id: "about", className: "home-section", "aria-labelledby": "taste-title" },
        h("div", { className: "section-head" },
          h("p", { className: "eyebrow" }, "מהמטבח שלנו"),
          h("h2", { id: "taste-title" }, "טעימה מהתפריט"),
          h("p", { className: "muted" }, `${caterer.name} מכינים כל מגש לאירוע שלכם. אלה כמה מהמנות שבתפריט היום.`)),
        h("ul", { className: "taste-grid" }, pictured.map((dish) => h("li", {},
          h("button", { type: "button", className: "taste-card", onclick: () => go("menu") },
            h("img", { src: photoUrl(dish.image_path), alt: "", loading: "lazy" }),
            h("span", { className: "taste-text" }, h("strong", {}, dish.name), h("span", {}, money(dish.unit_price), ` ${UNITS[dish.pricing_unit]}`)))))))
      : h("span", { id: "about" }),
    h("section", { className: "plan-card", "aria-labelledby": "plan-title" },
      h("span", { className: "icon-tile dark" }, icon("room_service")),
      h("div", {},
        h("h2", { id: "plan-title" }, "מתכננים אירוע בקרוב?"),
        h("p", {}, "בנו תפריט לאירוע ב-3 צעדים ושלחו בקשה להצעת מחיר. ההזמנה נקבעת רק אחרי אישור שלנו.")),
      h("button", { type: "button", onclick: () => go(hasOrder ? "menu" : "details") },
        hasOrder ? "חזרה להזמנה" : "הרכבת תפריט לאירוע", icon("chevron_left"))))];
}

// ---------- Ordering layout ----------

function steps(variant) {
  return h("ol", { className: `steps ${variant}` }, STEPS.map(([key, label, iconName], index) => {
    const isCurrent = key === state.step;
    const isDone = (key === "details" && state.order) || (key === "menu" && state.order?.lines.length && state.step === "summary");
    const enabled = key !== "summary" || state.order;
    return h("li", {},
      h("button", {
        type: "button",
        className: isCurrent ? "step current" : "step",
        disabled: !enabled,
        ...(isCurrent ? { "aria-current": "step" } : {}),
        onclick: () => leaveTo(key),
      },
      h("span", { className: "step-mark", "aria-hidden": "true" }, isDone && !isCurrent ? icon("done") : String(index + 1)),
      icon(iconName, "step-icon"),
      h("span", { className: "step-label" }, label)));
  }));
}

function sideColumn() {
  const { caterer } = state;
  const showCategories = state.step === "menu";
  return h("aside", { className: "side", "aria-label": "פרטי העסק והשלבים" },
    h("div", { className: "side-brand" },
      h("span", { className: "side-logo" }, logo("round")),
      h("p", { className: "side-title" }, `ברוכים הבאים ל${caterer.name}`),
      caterer.kashrut_status ? h("p", { className: "side-kashrut" }, icon("verified"), `כשרות: ${caterer.kashrut_status}`) : null),
    isDraft() ? h("nav", { "aria-label": "שלבי ההזמנה" }, steps("vertical")) : null,
    showCategories ? h("div", { className: "side-categories" },
      h("p", { className: "side-heading" }, "מחלקות התפריט"),
      categoryButtons("list")) : null,
    caterer.contact_phone ? h("div", { className: "help-card" },
      h("p", { className: "help-title" }, icon("room_service"), "מענה אישי לאירוע"),
      h("p", {}, "מתלבטים לגבי כמויות? שוחחו איתנו לתכנון מושלם."),
      h("a", { href: `tel:${caterer.contact_phone.replace(/\s/g, "")}` }, icon("call"), "חייגו עכשיו ", h("bdi", {}, caterer.contact_phone))) : null);
}

function layout(content, { action = null, panel = true } = {}) {
  const showPanel = panel && isDraft();
  return [
    h("div", { className: "flow-top" },
      isDraft() ? h("nav", { "aria-label": "שלבי ההזמנה", className: "step-strip" }, steps("horizontal")) : null),
    h("div", { className: showPanel ? "flow" : "flow two" },
      sideColumn(),
      h("main", { id: "main", tabIndex: -1, className: "middle" }, content.filter(Boolean)),
      showPanel ? orderPanel(action) : null),
    showPanel && state.order ? bottomBar(action) : null,
  ].filter(Boolean);
}

function pageHead(eyebrow, title, extra = null) {
  return h("div", { className: "page-head" },
    h("div", {}, h("p", { className: "eyebrow" }, eyebrow), h("h1", { tabIndex: -1 }, title)),
    extra);
}

function setPanelOpen(isOpen) {
  state.panelOpen = isOpen;
  const panel = document.querySelector(".order-panel");
  panel?.classList.toggle("open", isOpen);
  document.body.classList.toggle("sheet-open", isOpen);
  if (isOpen) panel?.querySelector("h2")?.focus();
  else document.querySelector(".total-bar .open-panel")?.focus();
}

// ---------- Event details ----------

function detailsFromOrder(order) {
  return {
    full_name: order?.customer.full_name ?? "",
    phone: order?.customer.phone ?? "",
    event_type: order?.event.event_type ?? EVENT_TYPES[0],
    event_date: order?.event.event_date ?? "",
    adults: order?.event.adults ?? 0,
    children: order?.event.children ?? 0,
    vegetarian_guests: order?.event.vegetarian_guests ?? 0,
    vegan_guests: order?.event.vegan_guests ?? 0,
    restricted_guests: order?.event.restricted_guests ?? 0,
    dietary_notes: order?.event.dietary_notes ?? "",
    fulfillment_type: order?.fulfillment_type ?? "pickup",
    time_slot_id: order?.time_slot_id ?? "",
    delivery_city: order?.delivery_city ?? "",
    delivery_address: order?.delivery_address ?? "",
  };
}

function validate(d) {
  const errors = {};
  const guests = Number(d.adults) + Number(d.children);
  const diets = Number(d.vegetarian_guests) + Number(d.vegan_guests) + Number(d.restricted_guests);
  if (d.full_name.trim().length < 2) errors.full_name = "כתבו שם מלא (לפחות 2 תווים)";
  if (!/^[0-9+\-\s]{9,20}$/.test(d.phone.trim())) errors.phone = "כתבו מספר טלפון תקין, למשל 050-1234567";
  if (!d.event_date) errors.event_date = "בחרו תאריך לאירוע";
  else if (d.event_date < state.availability.earliest_date) errors.event_date = `התאריך המוקדם ביותר להזמנה הוא ${dateText(state.availability.earliest_date)}`;
  if (!d.time_slot_id) errors.time_slot_id = d.event_date ? "בחרו שעה" : "בחרו קודם תאריך, ואז שעה";
  if (guests === 0) errors.adults = "יש להזין לפחות סועד אחד";
  for (const key of ["adults", "children", "vegetarian_guests", "vegan_guests", "restricted_guests"]) {
    if (!Number.isInteger(Number(d[key])) || Number(d[key]) < 0) errors[key] = "מספר שלם, 0 ומעלה";
  }
  if (!errors.adults && diets > guests) errors.vegetarian_guests = "הצמחונים, הטבעונים וההגבלות נספרים מתוך מספר הסועדים, ולכן הם לא יכולים לעבור אותו";
  if (d.fulfillment_type === "delivery" && !d.delivery_city) errors.delivery_city = "בחרו עיר למשלוח";
  return errors;
}

let fieldCount = 0;
// A labelled field with an inline Hebrew error, linked for screen readers.
function formField(label, control, { key, hint, required = false } = {}) {
  control.id ||= `f-${++fieldCount}`;
  const error = key ? state.errors[key] : null;
  const errorId = `${control.id}-error`;
  const hintId = `${control.id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ");
  if (describedBy) control.setAttribute("aria-describedby", describedBy);
  if (error) control.setAttribute("aria-invalid", "true");
  if (required) control.setAttribute("aria-required", "true");
  // The asterisk stays outside the label, so the field's name is just its label.
  return h("div", { className: "field" },
    h("span", { className: "label-row" }, h("label", { htmlFor: control.id }, label),
      required ? h("span", { className: "required", "aria-hidden": "true" }, "*") : null),
    control,
    error ? h("p", { className: "error-text", id: errorId }, icon("error"), error) : null,
    hint ? h("small", { id: hintId }, hint) : null);
}

function choice(options, value) {
  const control = h("select", {}, options.map(([optionValue, label]) => h("option", { value: optionValue }, label)));
  control.value = value;
  return control;
}

function counter(key, label) {
  const d = state.draft;
  const input = h("input", { type: "number", inputMode: "numeric", min: "0", step: "1", value: d[key], name: key, "aria-label": label });
  const change = (delta) => {
    input.value = Math.max(0, (Number(input.value) || 0) + delta);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };
  const control = h("div", { className: "stepper counter" },
    h("button", { type: "button", "aria-label": `פחות ${label}`, onclick: () => change(-1) }, "−"),
    input,
    h("button", { type: "button", "aria-label": `עוד ${label}`, onclick: () => change(1) }, "+"));
  input.id = `f-${key}`;
  const error = state.errors[key];
  if (error) input.setAttribute("aria-invalid", "true");
  return h("div", { className: "field" },
    h("label", { htmlFor: input.id }, label),
    control,
    error ? h("p", { className: "error-text", id: `${input.id}-error` }, icon("error"), error) : null);
}

function renderDetails() {
  const { availability, cities, order } = state;
  state.draft ??= detailsFromOrder(order);
  const d = state.draft;

  const name = h("input", { name: "full_name", maxLength: 120, autocomplete: "name", value: d.full_name, placeholder: "למשל: דניאל לוי" });
  const phone = h("input", { name: "phone", type: "tel", dir: "ltr", autocomplete: "tel", inputMode: "tel", value: d.phone, placeholder: "050-0000000" });
  const eventType = choice(EVENT_TYPES.map((type) => [type, type]), d.event_type);
  eventType.name = "event_type";
  const date = h("input", { name: "event_date", type: "date", min: availability.earliest_date, value: d.event_date });
  const type = choice([["pickup", "איסוף עצמי"], ...(cities.length ? [["delivery", "משלוח"]] : [])], d.fulfillment_type);
  type.name = "fulfillment_type";
  const slot = h("select", { name: "time_slot_id" });
  const city = choice([["", "בחרו עיר"], ...cities.map((c) => [c.city, `${c.city} (${shekel(c.fee)})`])], d.delivery_city);
  city.name = "delivery_city";
  const address = h("input", { name: "delivery_address", maxLength: 300, autocomplete: "street-address", value: d.delivery_address, placeholder: "רחוב, מספר בית, קומה" });
  const notes = h("textarea", { name: "dietary_notes", rows: 3, maxLength: 1000, value: d.dietary_notes, placeholder: "פרטו רגישויות (גלוטן, בוטנים, לקטוז) או העדפות מיוחדות" });
  const deliveryFields = h("div", { className: "grid" },
    formField("עיר", city, { key: "delivery_city", required: true }),
    formField("כתובת", address, { key: "delivery_address" }));
  const totalGuests = h("span", { className: "badge" });

  const refreshSlots = () => {
    deliveryFields.hidden = type.value !== "delivery";
    // getDay() matches our convention: 0 = Sunday. Noon avoids timezone edges.
    const weekday = date.value ? new Date(`${date.value}T12:00`).getDay() : null;
    const options = availability.slots.filter((s) => s.fulfillment_type === type.value
      && (s.weekday === null || s.weekday === weekday));
    const current = slot.value || d.time_slot_id;
    slot.replaceChildren(
      h("option", { value: "" }, date.value ? (options.length ? "בחרו שעה" : "אין שעות פנויות ביום הזה") : "בחרו קודם תאריך"),
      ...options.map((s) => h("option", { value: s.id }, `${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)}`)));
    slot.value = options.some((s) => s.id === current) ? current : "";
    d.time_slot_id = slot.value;
  };

  const form = h("form", {
    className: "details-form",
    noValidate: true,
    oninput: (event) => {
      const field = event.target.name;
      if (field && field in d) d[field] = event.target.value;
      totalGuests.textContent = `סה״כ סועדים: ${(Number(d.adults) || 0) + (Number(d.children) || 0)}`;
    },
    onchange: (event) => {
      if (event.target === date || event.target === type) refreshSlots();
      const field = event.target.name;
      if (field && field in d) d[field] = event.target.value;
    },
    onsubmit: async (event) => {
      event.preventDefault();
      const nextStep = state.nextStep ?? "menu";
      state.nextStep = null;
      state.errors = validate(d);
      if (Object.keys(state.errors).length) {
        render();
        const first = document.querySelector("[aria-invalid='true']");
        first?.focus();
        notify("יש לתקן את השדות המסומנים", true);
        return;
      }
      const delivery = d.fulfillment_type === "delivery";
      const details = {
        customer: { full_name: d.full_name.trim(), phone: d.phone.trim() },
        event: {
          event_type: d.event_type,
          event_date: d.event_date,
          adults: Number(d.adults),
          children: Number(d.children),
          vegetarian_guests: Number(d.vegetarian_guests),
          vegan_guests: Number(d.vegan_guests),
          restricted_guests: Number(d.restricted_guests),
          dietary_notes: textOrNull(d.dietary_notes),
        },
        fulfillment_type: d.fulfillment_type,
        time_slot_id: d.time_slot_id,
        delivery_city: delivery ? d.delivery_city : null,
        delivery_address: delivery ? textOrNull(d.delivery_address) : null,
      };
      submit.disabled = true;
      submit.classList.add("is-busy");
      const saved = await attempt(() => (state.order
        ? orderApi("", { method: "PATCH", body: JSON.stringify({ ...details, version: state.order.version }) })
        : api(`/api/c/${state.slug}/orders`, { method: "POST", body: JSON.stringify(details) })));
      submit.disabled = false;
      submit.classList.remove("is-busy");
      if (!saved) return;
      if (saved.token) {
        state.token = saved.token;
        state.order = saved.order;
        history.replaceState({ step: state.step }, "", `#order=${state.order.id}.${state.token}`);
      } else {
        state.order = saved;
      }
      state.draft = null;
      if (state.pendingDish) {
        const dish = state.dishes.find((item) => item.id === state.pendingDish);
        state.pendingDish = null;
        const updated = dish && await attempt(() => orderApi(`/items/${dish.id}`, {
          method: "PUT", body: JSON.stringify({ quantity: String(quantityStep(dish)), version: state.order.version }),
        }), `${dish.name} נוספה להזמנה`);
        if (updated) state.order = updated;
      }
      go(nextStep);
    },
  },
  h("section", { className: "card form-card" },
    h("div", { className: "card-header" }, h("h2", {}, "פרטי הלקוח"), h("span", { className: "icon-tile" }, icon("person"))),
    formField("שם מלא", name, { key: "full_name", required: true }),
    formField("טלפון ליצירת קשר", phone, { key: "phone", required: true }),
    formField("סוג האירוע", eventType)),
  h("section", { className: "card form-card" },
    h("div", { className: "card-header" }, h("h2", {}, "מספר סועדים"), totalGuests),
    h("div", { className: "grid two" }, counter("adults", "מבוגרים"), counter("children", "ילדים")),
    h("p", { className: "muted" }, "מתוך הסועדים שלמעלה, כמה הם:"),
    h("div", { className: "grid three" },
      formField("צמחונים", h("input", { name: "vegetarian_guests", type: "number", inputMode: "numeric", min: "0", value: d.vegetarian_guests }), { key: "vegetarian_guests" }),
      formField("טבעונים", h("input", { name: "vegan_guests", type: "number", inputMode: "numeric", min: "0", value: d.vegan_guests }), { key: "vegan_guests" }),
      formField("הגבלות אחרות", h("input", { name: "restricted_guests", type: "number", inputMode: "numeric", min: "0", value: d.restricted_guests }), { key: "restricted_guests" }))),
  h("section", { className: "card form-card" },
    formField("הערות תזונה ואלרגיות", notes, {
      hint: "ההערות מגיעות לעסק ולעוזר ה-AI, ואינן מבטיחות התאמה. אל תכתבו כאן שמות.",
    })),
  h("section", { className: "card form-card" },
    h("div", { className: "card-header" }, h("h2", {}, "מתי ואיך"), h("span", { className: "icon-tile" }, icon("local_shipping"))),
    h("div", { className: "grid two" },
      formField("איסוף או משלוח", type),
      formField("תאריך האירוע", date, { key: "event_date", required: true })),
    h("div", { className: "grid two" },
      formField("שעת איסוף או הגשה", slot, { key: "time_slot_id", required: true })),
    deliveryFields));
  const submit = h("button", { type: "submit", className: "submit-wide" }, state.order ? "שמירה והמשך לתפריט" : "המשך לבחירת תפריט", icon("arrow_forward"));
  form.append(h("div", { className: "form-actions" }, submit));
  refreshSlots();
  totalGuests.textContent = `סה״כ סועדים: ${(Number(d.adults) || 0) + (Number(d.children) || 0)}`;

  const intro = state.pendingDish
    ? h("p", { className: "alert info", role: "status" }, icon("info"), h("span", {}, "כדי להוסיף מנות להזמנה, נתחיל בפרטי האירוע. המנה שבחרתם תתווסף מיד אחרי השמירה."))
    : null;
  return layout([pageHead("שלב 1 מתוך 3", "פרטי האירוע", h("span", { className: "icon-tile big" }, icon("edit_calendar"))), intro, form]);
}

// ---------- Menu ----------

function allergenInfo(dish) {
  const statuses = Object.fromEntries(dish.allergens.map((a) => [a.allergen_id, a.status]));
  const named = (status) => state.allergens.filter((a) => (statuses[a.id] ?? "unknown") === status).map((a) => a.name);
  const row = (label, names, kind) => (names.length ? h("p", { className: `allergen-row ${kind}` }, h("strong", {}, `${label}: `), names.join(", ")) : null);
  return h("section", { className: "sheet-allergens" },
    h("h3", {}, "מידע על אלרגנים"),
    row("מכיל", named("contains"), "contains"),
    row("לא מכיל", named("free"), "free"),
    row("לא ידוע (לא אומת)", named("unknown"), "unknown"),
    h("p", { className: "muted" }, "מידע שלא אומת אינו אומר שהמנה בטוחה. באלרגיה חמורה בדקו עם העסק לפני ההזמנה."));
}

function dishFacts(dish) {
  const { kashrut_class: kashrut, is_vegetarian: vegetarian, is_vegan: vegan } = dish.dietary ?? {};
  return h("div", { className: "dish-tags" },
    vegan === true ? h("span", { className: "tag green" }, icon("psychiatry"), "טבעוני") : null,
    vegetarian === true && vegan !== true ? h("span", { className: "tag green" }, icon("eco"), "צמחוני") : null,
    h("span", { className: "tag" }, `כשרות: ${KASHRUT[kashrut] ?? "לא צוין"}`),
    h("span", { className: "tag" }, `קלוריות: ${dish.calories_per_portion ? `${dish.calories_per_portion} למנה` : "לא צוין"}`));
}

// The page re-renders after a change, so focus returns to the same control where it still exists.
function restoreFocus(dishId, label, areaSelector) {
  const area = areaSelector ? document.querySelector(areaSelector) : document;
  if (!area) return;
  const same = [...area.querySelectorAll("button")].find((button) => button.getAttribute("aria-label") === label && !button.disabled);
  const target = same ?? area.querySelector(`[data-more="${dishId}"]`) ?? area.querySelector(`[data-dish="${dishId}"]`) ?? area.querySelector("button");
  target?.focus({ preventScroll: true });
}

async function setQuantity(dish, quantity) {
  if (!state.order) {
    // No order yet: remember the dish, ask for event details, then add it.
    state.pendingDish = dish.id;
    return go("details");
  }
  const path = `/items/${dish.id}`;
  const pressed = document.activeElement;
  const label = pressed?.getAttribute("aria-label");
  const areaSelector = ["dialog.dish-sheet", ".order-panel"].find((selector) => pressed?.closest(selector));
  pressed?.closest(".qty, .order-line")?.classList.add("is-busy");
  const updated = await attempt(() => (quantity > 0
    ? orderApi(path, { method: "PUT", body: JSON.stringify({ quantity: String(quantity), version: state.order.version }) })
    : orderApi(`${path}?version=${state.order.version}`, { method: "DELETE" })));
  document.querySelectorAll(".is-busy").forEach((element) => element.classList.remove("is-busy"));
  if (updated) {
    const position = window.scrollY;
    const panelPosition = document.querySelector(".order-panel")?.scrollTop ?? 0;
    state.order = updated;
    render();
    window.scrollTo(0, position);
    const panel = document.querySelector(".order-panel");
    if (panel) panel.scrollTop = panelPosition;
    restoreFocus(dish.id, label, areaSelector);
    announce(quantity > 0 ? `${dish.name}: ${quantity} בהזמנה` : `${dish.name} הוסרה מההזמנה`);
  }
}

function announce(message) {
  const live = document.getElementById("live");
  if (live) live.textContent = message;
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
  const quantity = quantityOf(dish);
  const line = state.order?.lines.find((item) => item.dish_id === dish.id);
  return h("div", { className: "qty" },
    line?.recommended_quantity ? h("span", { className: "recommended" }, `מומלץ: ${Number(line.recommended_quantity)}`) : null,
    quantity === 0
      ? h("button", { type: "button", className: "saffron add", "aria-label": `הוספת ${dish.name}`, onclick: () => setQuantity(dish, quantityStep(dish)) },
        icon("add"), "הוסף להזמנה")
      : [stepper(dish, quantity), h("span", { className: "added" }, icon("shopping_bag"), "בהזמנה")]);
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
  const dialog = h("dialog", { className: "dish-sheet", "aria-labelledby": "sheet-title" },
    photo ? h("img", { className: "sheet-photo", src: photo, alt: "" }) : null,
    h("div", { className: "sheet-body" },
      h("div", { className: "sheet-top" }, h("h2", { id: "sheet-title" }, dish.name), price(dish)),
      dishFacts(dish),
      dish.description ? h("p", { className: "muted" }, dish.description) : null,
      dish.portion_description ? h("p", { className: "muted" }, dish.portion_description) : null,
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
  const kashrut = KASHRUT[dish.dietary?.kashrut_class];
  return h("article", { className: "dish" },
    h("div", { className: "dish-body" },
      h("div", { className: "dish-top" },
        h("h3", {}, h("button", { type: "button", className: "dish-open", "data-dish": dish.id, onclick: () => openDish(dish) }, dish.name)),
        price(dish)),
      dish.description ? h("p", { className: "dish-description" }, dish.description) : null,
      dishFacts(dish),
      h("div", { className: "dish-foot" },
        h("button", { type: "button", className: "link", onclick: () => openDish(dish) }, icon("info"), "מידע על אלרגנים"),
        quantityControl(dish))),
    // Pointer shortcut only: the name above is the keyboard and screen reader route.
    h("button", { type: "button", className: "dish-media", tabIndex: -1, "aria-hidden": "true", onclick: () => openDish(dish) },
      photo ? h("img", { src: photo, alt: "", loading: "lazy" }) : h("span", { className: "dish-letter" }, dish.name[0]),
      kashrut ? h("span", { className: "media-badge" }, kashrut) : null,
      dish.unit_label ? h("span", { className: "media-badge unit" }, dish.unit_label) : null));
}

function visibleDishes() {
  const { category, diets } = state.filters;
  const tests = DIET_FILTERS.filter(([key]) => diets.has(key)).map(([, , test]) => test);
  return state.dishes.filter((dish) => (category === "all" || dish.category_id === category)
    && tests.every((test) => test(dish)));
}

function setCategory(id) {
  state.filters.category = id;
  const position = window.scrollY;
  render();
  window.scrollTo(0, position);
  document.querySelector(`.category-tabs [data-category="${id}"]`)?.focus({ preventScroll: true });
}

function categoryButtons(variant) {
  const counts = (id) => state.dishes.filter((dish) => id === "all" || dish.category_id === id).length;
  const items = [["all", "הכל"], ...state.categories.filter((c) => counts(c.id)).map((c) => [c.id, c.name])];
  return h("div", { className: `category-${variant}`, role: "group", "aria-label": "מחלקות התפריט" },
    items.map(([id, name]) => h("button", {
      type: "button",
      className: "category-button",
      "data-category": id,
      "aria-pressed": String(state.filters.category === id),
      onclick: () => setCategory(id),
    }, h("span", {}, name), h("span", { className: "count" }, String(counts(id))))));
}

function dietChips() {
  return h("div", { className: "diet-chips", role: "group", "aria-label": "סינון לפי כשרות ותזונה" },
    h("span", { className: "chips-label" }, icon("tune"), "סינון:"),
    DIET_FILTERS.map(([key, label]) => h("button", {
      type: "button",
      className: "chip",
      "aria-pressed": String(state.filters.diets.has(key)),
      onclick: () => {
        const { diets } = state.filters;
        if (diets.has(key)) diets.delete(key); else diets.add(key);
        const position = window.scrollY;
        render();
        window.scrollTo(0, position);
        document.querySelector(`.diet-chips .chip:nth-of-type(${DIET_FILTERS.findIndex(([k]) => k === key) + 1})`)?.focus({ preventScroll: true });
      },
    }, label)));
}

function categorySection({ category, dishes }) {
  return h("section", { className: "menu-section", "data-section": category.id, "aria-labelledby": `cat-${category.id}` },
    h("div", { className: "category-title" },
      h("h2", { id: `cat-${category.id}` }, category.name),
      h("span", { className: "badge" }, count(dishes.length, "מנה אחת", "מנות"))),
    dishes.map(dishCard));
}

function renderMenu() {
  const visible = visibleDishes();
  const sections = state.categories
    .map((category) => ({ category, dishes: visible.filter((dish) => dish.category_id === category.id) }))
    .filter(({ dishes }) => dishes.length);
  const filtered = state.filters.category !== "all" || state.filters.diets.size > 0;
  const status = filtered
    ? `מוצגות ${visible.length} מתוך ${state.dishes.length} מנות`
    : `${state.dishes.length} מנות בתפריט`;
  const eventPill = state.order
    ? h("button", { type: "button", className: "event-pill", onclick: () => go("details"), "aria-label": "שינוי פרטי האירוע" },
      icon("calendar_month"), h("span", {}, `האירוע של ${state.order.customer.full_name}`), h("small", {}, `${dateText(state.order.event.event_date)} · ${state.order.event.adults + state.order.event.children} סועדים`))
    : null;

  return layout([
    pageHead("שלב 2 מתוך 3", "התפריט שלנו", eventPill),
    state.order ? null : h("div", { className: "alert info" }, icon("info"),
      h("div", {}, h("p", {}, "אפשר לעיין בתפריט כבר עכשיו. כדי להוסיף מנות להזמנה, נמלא קודם את פרטי האירוע."),
        h("button", { type: "button", className: "link", onclick: () => go("details") }, "למילוי פרטי האירוע"))),
    h("div", { className: "card toolbar" },
      categoryButtons("tabs"),
      dietChips(),
      h("p", { className: "filter-status", role: "status" }, status)),
    ...(sections.length
      ? sections.map(categorySection)
      : [h("div", { className: "card empty-state" },
        h("span", { className: "icon-tile big" }, icon("search")),
        h("h2", {}, "אין מנות שמתאימות לסינון"),
        h("p", { className: "muted" }, "מנה מוצגת רק כשהנתונים שלה מאשרים את הסינון. נסו להסיר חלק מהסינונים."),
        h("button", {
          type: "button",
          className: "secondary",
          onclick: () => { state.filters = { category: "all", diets: new Set() }; render(); },
        }, "ניקוי הסינון"))]),
  ], { action: state.order ? { label: "לסיכום ההזמנה", run: () => go("summary") } : null });
}

// ---------- Order column ----------

function orderLine(line) {
  const dish = state.dishes.find((item) => item.id === line.dish_id);
  const photo = photoUrl(dish?.image_path);
  const quantity = Number(line.quantity);
  return h("li", { className: "order-line" },
    h("div", { className: "line-photo" },
      photo ? h("img", { src: photo, alt: "", loading: "lazy" }) : h("span", {}, line.name[0]),
      h("span", { className: "line-count" }, String(quantity))),
    h("div", { className: "line-text" },
      h("strong", {}, line.name),
      h("span", { className: "price" }, money(line.line_total))),
    h("div", { className: "line-controls" },
      dish ? stepper(dish, quantity) : h("span", {}),
      // Offered even for a dish no longer on the menu, or the customer couldn't remove it.
      h("button", { type: "button", className: "line-remove", "aria-label": `הסרת ${line.name}`, onclick: () => setQuantity(dish ?? { id: line.dish_id, name: line.name }, 0) }, icon("delete"))));
}

function totals(order) {
  const row = (label, value, extra = "") => h("div", { className: `sum ${extra}` }, h("span", {}, label), money(value));
  return h("div", { className: "totals" },
    row("סכום המנות", order.subtotal),
    order.fulfillment_type === "delivery" ? row("משלוח", order.delivery_fee) : null,
    row("סה״כ כולל מע״מ", order.total, "total"));
}

function orderPanel(action) {
  const { order } = state;
  const lines = order?.lines ?? [];
  const firstPhoto = photoUrl(state.dishes.find((dish) => dish.image_path)?.image_path);
  return h("aside", { className: state.panelOpen ? "order-panel open" : "order-panel", "aria-labelledby": "panel-title" },
    order ? h("div", { className: "panel-person" },
      h("span", { className: "icon-tile round" }, icon("person")),
      h("div", {}, h("strong", {}, order.customer.full_name),
        h("small", {}, icon(order.fulfillment_type === "delivery" ? "local_shipping" : "storefront"), order.fulfillment_type === "delivery" ? `משלוח ל${order.delivery_city}` : "איסוף עצמי"))) : null,
    h("div", { className: "panel-title" },
      h("h2", { id: "panel-title", tabIndex: -1 }, "ההזמנה שלי"),
      h("span", { className: "badge" }, lines.length === 1 ? "פריט אחד" : `${lines.length} פריטים`),
      h("button", { type: "button", className: "icon-button sheet-close", "aria-label": "סגירת ההזמנה", onclick: () => setPanelOpen(false) }, icon("close"))),
    order ? h("button", { type: "button", className: "date-box", "aria-label": "שינוי פרטי האירוע", onclick: () => go("details") },
      icon("calendar_month"), h("span", {}, "תאריך האירוע"), h("strong", {}, dateText(order.event.event_date))) : null,
    lines.length
      ? h("ul", { className: "order-lines" }, lines.map(orderLine))
      : h("div", { className: "panel-empty" },
        !order && firstPhoto ? h("img", { className: "panel-photo", src: firstPhoto, alt: "" }) : null,
        h("span", { className: "icon-tile round" }, icon("shopping_basket")),
        h("p", { className: "empty-title" }, "עדיין לא נבחרו מנות"),
        h("p", { className: "muted" }, order ? "בחרו מנות מהתפריט והן יופיעו כאן." : "מלאו את פרטי האירוע כדי לעבור לתפריט המותאם עבורכם.")),
    order ? totals(order) : null,
    action ? h("button", { type: "button", className: "checkout", disabled: action.disabled, onclick: action.run }, action.label, icon(action.icon ?? "arrow_forward")) : null,
    order ? chatButton() : null);
}

function bottomBar(action) {
  const { order } = state;
  return h("div", { className: "total-bar" },
    h("div", { className: "total-sum" }, h("span", {}, "סה״כ לתשלום:"), h("strong", {}, money(order.total))),
    h("button", { type: "button", className: "secondary open-panel", "aria-expanded": String(state.panelOpen), onclick: () => setPanelOpen(true) },
      icon("shopping_bag"), `ההזמנה שלי (${order.lines.length})`),
    h("div", { className: "actions" },
      action && state.step !== "summary" ? h("button", { type: "button", onclick: action.run }, action.label, icon("arrow_forward")) : null,
      chatButton()));
}

// ---------- Summary and status ----------

function linesTable(order) {
  return h("table", { className: "lines" },
    h("thead", {}, h("tr", {}, h("th", {}, "מנה"), h("th", { className: "num" }, "כמות"), h("th", { className: "num" }, "סכום"))),
    h("tbody", {}, order.lines.map((line) => h("tr", {},
      h("td", {}, line.name, line.recommended_quantity && Number(line.recommended_quantity) !== Number(line.quantity)
        ? h("div", { className: "muted" }, `מומלץ: ${Number(line.recommended_quantity)}`) : null),
      h("td", { className: "num" }, h("bdi", {}, `${Number(line.quantity)} × ${shekel(line.unit_price)}`)),
      h("td", { className: "num" }, money(line.line_total))))));
}

function chosenDishes(order) {
  const pictured = order.lines
    .map((line) => ({ line, photo: photoUrl(state.dishes.find((dish) => dish.id === line.dish_id)?.image_path) }))
    .filter(({ photo }) => photo);
  return pictured.length
    ? h("ul", { className: "chosen", "aria-label": "המנות שבחרתם" }, pictured.map(({ line, photo }) => h("li", {},
      h("img", { src: photo, alt: "" }), h("span", {}, line.name))))
    : null;
}

function eventSummary(order) {
  const { event } = order;
  const delivery = order.fulfillment_type === "delivery";
  const fact = (iconName, label, value) => h("li", {}, icon(iconName), h("span", {}, label), h("strong", {}, value));
  return h("section", { className: "card event-card" },
    h("div", { className: "card-header" },
      h("h2", {}, "פרטי האירוע"),
      isDraft() ? h("button", { type: "button", className: "secondary", onclick: () => go("details") }, icon("edit"), "עריכה") : null),
    h("ul", { className: "facts" },
      fact("celebration", "סוג האירוע", event.event_type),
      fact("calendar_month", "תאריך", dateText(event.event_date)),
      fact("group", "סועדים", `${event.adults} מבוגרים, ${event.children} ילדים`),
      fact(delivery ? "local_shipping" : "storefront", "אספקה", delivery ? `משלוח ל${order.delivery_city}${order.delivery_address ? `, ${order.delivery_address}` : ""}` : "איסוף עצמי")));
}

function linkActions() {
  const link = privateLink();
  const share = `https://wa.me/?text=${encodeURIComponent(link)}`;
  return h("section", { className: "card link-card" },
    h("div", { className: "card-header" }, h("h2", {}, icon("link"), " הקישור הפרטי להזמנה")),
    h("p", { className: "private-link", dir: "ltr" }, link),
    h("p", { className: "muted" }, "שמרו את הקישור, ואל תשתפו אותו. כל מי שמחזיק בו יכול לראות את ההזמנה ואת הפרטים שלכם. אין דרך לשחזר אותו אם יאבד."),
    h("div", { className: "actions" },
      h("button", { type: "button", className: "secondary", onclick: () => attempt(() => navigator.clipboard.writeText(link), "הקישור הועתק") }, icon("content_copy"), "העתקת הקישור"),
      h("a", { className: "button secondary", href: share, target: "_blank", rel: "noopener noreferrer" }, icon("chat"), "שליחה לעצמי בוואטסאפ")));
}

function renderSummary() {
  const { order } = state;
  const { status, has_unknown: hasUnknown } = order.kashrut;
  const acknowledge = h("input", { type: "checkbox", id: "ack" });
  let sending = false;

  const submit = async () => {
    if (sending) return;
    sending = true;
    document.querySelectorAll(".submit-order").forEach((button) => { button.disabled = true; button.classList.add("is-busy"); });
    const body = { version: order.version, acknowledge_kashrut_warning: acknowledge.checked };
    const updated = await attempt(() => orderApi("/submit", { method: "POST", body: JSON.stringify(body) }));
    sending = false;
    if (updated) {
      state.order = updated;
      notify("הבקשה נשלחה לעסק");
      go("status", { push: false });
    } else {
      document.querySelectorAll(".submit-order").forEach((button) => { button.disabled = false; button.classList.remove("is-busy"); });
    }
  };

  const canSubmit = status !== "blocked" && order.lines.length > 0;
  return layout([
    pageHead("שלב 3 מתוך 3", "סיכום והזמנה"),
    chosenDishes(order),
    eventSummary(order),
    h("section", { className: "card narrow-only" },
      h("h2", {}, "המנות שבחרתם"),
      order.lines.length ? linesTable(order) : h("p", { className: "empty" }, "עדיין לא נבחרו מנות."),
      totals(order)),
    order.lines.length ? null : h("p", { className: "alert info" }, icon("info"), h("span", {}, "עדיין לא נבחרו מנות. חזרו לתפריט כדי לבחור.")),
    status === "blocked"
      ? h("p", { className: "alert blocked", role: "alert" }, icon("warning"), h("span", {}, "העסק לא מאפשר הזמנה שמערבת מנות בשריות וחלביות. הסירו אחת מהן כדי להמשיך."))
      : null,
    status === "warn"
      ? h("div", { className: "alert" }, icon("warning"), h("div", {}, h("p", {}, "ההזמנה כוללת מנות בשריות וחלביות יחד."),
        h("label", { className: "check", htmlFor: "ack" }, acknowledge, "הבנתי ואני רוצה להמשיך")))
      : null,
    hasUnknown ? h("p", { className: "alert" }, icon("info"), h("span", {}, "לחלק מהמנות לא צוינה כשרות. בדקו עם העסק אם זה חשוב לכם.")) : null,
    linkActions(),
    h("p", { className: "alert info" }, icon("info"), h("span", {}, "שליחת הבקשה אינה הזמנה סופית. ההזמנה תאושר רק לאחר בדיקה של העסק.")),
    h("div", { className: "form-actions" },
      h("button", { type: "button", className: "secondary", onclick: () => go("menu") }, icon("arrow_back"), "חזרה לתפריט"),
      h("button", { type: "button", className: "narrow-only submit-order", disabled: !canSubmit, onclick: submit }, "שליחת בקשה להצעת מחיר", icon("send", "flip"))),
  ], { action: { label: "שליחת בקשה להצעת מחיר", run: submit, disabled: !canSubmit, icon: "send" } });
}

async function refresh() {
  const updated = await attempt(() => orderApi(""));
  if (updated) {
    state.order = updated;
    render();
    notify("הסטטוס עודכן");
  }
}

function renderStatus() {
  const { order } = state;
  const phone = state.caterer.contact_phone;
  return layout([
    h("section", { className: `card status-card ${order.status}` },
      h("span", { className: "status-icon" }, icon(STATUS_ICON[order.status] ?? "info")),
      h("p", { className: "eyebrow" }, "סטטוס ההזמנה"),
      h("h1", { className: "status", tabIndex: -1 }, STATUS[order.status]),
      h("p", {}, STATUS_HELP[order.status]),
      order.decision_note ? h("p", { className: "decision-note" }, h("strong", {}, "הערת העסק: "), order.decision_note) : null,
      h("div", { className: "actions" },
        h("button", { type: "button", className: "secondary", onclick: refresh }, icon("refresh"), "בדיקת עדכון"),
        phone ? h("a", { className: "button secondary", href: `tel:${phone.replace(/\s/g, "")}` }, icon("call"), "טלפון העסק: ", h("bdi", {}, phone)) : null)),
    eventSummary(order),
    h("section", { className: "card" },
      h("h2", {}, "פרטי ההזמנה"),
      linesTable(order),
      totals(order)),
    linkActions(),
  ], { panel: false });
}

function renderUnavailable() {
  app.replaceChildren(h("main", { id: "main", className: "unavailable" },
    h("section", { className: "card" },
      h("img", { className: "brand-logo", src: "/img/brand/logo.jpg", alt: "", width: 120, height: 80 }),
      h("h1", {}, "העמוד אינו זמין"),
      h("p", {}, "לא מצאנו את הקייטרינג שחיפשתם. בדקו את הקישור מול העסק."),
      h("button", { type: "button", onclick: () => location.reload() }, icon("refresh"), "ניסיון נוסף"))));
}

const VIEWS = { home: renderHome, details: renderDetails, menu: renderMenu, summary: renderSummary, status: renderStatus };

// ---------- Start ----------

async function loadOrder() {
  const match = location.hash.match(/^#order=([^.]+)\.(.+)$/);
  if (!match) return;
  [, , state.token] = match;
  state.order = { id: match[1] };
  try {
    state.order = await orderApi("");
    state.step = state.order.status === "draft" ? "menu" : "status";
  } catch {
    state.order = null;
    state.token = null;
    history.replaceState(null, "", location.pathname);
    notify("הקישור להזמנה אינו תקין", true);
    state.step = "details";
  }
}

async function start() {
  const pathSlug = location.pathname.split("/")[1] === "c" ? location.pathname.split("/")[2] : null;
  try {
    state.config = await api("/api/config");
    state.slug = pathSlug || state.config.site_caterer;
    if (!state.slug) throw new Error("no caterer");
    const base = `/api/c/${state.slug}`;
    [state.caterer, state.allergens, state.categories, state.dishes, state.availability, state.cities] = await Promise.all([
      api(base),
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
  useBrand(state.caterer);
  mountChat(orderApi, applyOrder);
  await loadOrder();
  history.replaceState({ step: state.step }, "", location.href);
  const live = h("div", { id: "live", className: "visually-hidden", "aria-live": "polite" });
  document.body.append(live);
  render();
}

// A button, not an <a href="#main">: the URL fragment holds the private token.
// Pressed while the page is still loading, it moves focus once the content is there.
document.querySelector(".skip-link")?.addEventListener("click", () => {
  const main = document.getElementById("main");
  if (main) main.focus();
  else started.then(() => document.getElementById("main")?.focus());
});
const started = start();

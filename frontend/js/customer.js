// Menu + agent screen (C2 + C4). All data is mock (js/mock/menu.js) until the API exists.
import { h } from "./dom.js";
import { ils, reducedMotion, wait } from "./format.js";
import {
  CATEGORIES, DISHES, EVENT, INITIAL_ORDER, SCRIPTED_PROPOSALS, DEMO_REPLY, dishById, orderTotal,
} from "./mock/menu.js";
import { loadEvent, describeEvent } from "./event-store.js";
import { createDishCard } from "./components/dish-card.js";
import { createOrderSummary } from "./components/order-summary.js";
import { createProposalCard } from "./components/proposal-card.js";
import { createAgentPanel } from "./components/agent-panel.js";
import { bindBottomSheet } from "./components/bottom-sheet.js";
import { flyPill } from "./components/fly-pill.js";

const state = { order: { ...INITIAL_ORDER }, version: 0, busy: false, filter: { cat: "all", vegetarian: false, vegan: false } };
const cards = new Map();
const pending = new Set(); // { proposal, card } awaiting a decision
let scriptIndex = 0;

// ---- summary + agent
const summary = createOrderSummary();
const barTotal = document.getElementById("bar-total");
summary.mirror(barTotal);

const agent = createAgentPanel({ summaryEl: summary.el, onSend });
document.getElementById("menu-layout").append(agent.el);
const openBtn = document.getElementById("open-agent");
const hintBtn = document.getElementById("agent-hint");
const sheet = bindBottomSheet({
  panel: agent.el,
  openBtn,
  closeBtn: agent.closeBtn,
  backdrop: document.getElementById("backdrop"),
  onChange: () => updateHint(),
});
hintBtn.addEventListener("click", () => sheet.open());

// Mobile only (CSS): while a proposal awaits a decision and the sheet is closed, say so above the bar.
function updateHint() {
  const waiting = [...pending].at(-1);
  const show = Boolean(waiting) && !document.body.classList.contains("sheet-open");
  hintBtn.hidden = !show;
  openBtn.querySelector(".btn-agent__dot").hidden = !waiting;
  if (waiting) hintBtn.textContent = waiting.hint;
}
summary.foot.append(h("a", { class: "btn btn-secondary btn-lg summary__cta", href: "/customer/summary.html" }, "לסיכום ושליחה לאישור"));

// ---- catalog
const grid = document.getElementById("dish-grid");
const chips = document.getElementById("chips");

function renderCatalog() {
  const { cat, vegetarian, vegan } = state.filter;
  const visible = DISHES.filter((d) => (cat === "all" || d.cat === cat) && (!vegetarian || d.vegetarian) && (!vegan || d.vegan));
  grid.replaceChildren();
  cards.clear();
  for (const dish of visible) {
    const card = createDishCard(dish, state.order[dish.id] ?? 0, (qty) => setQty(dish.id, qty));
    cards.set(dish.id, card);
    grid.append(card.el);
  }
  if (!visible.length) grid.append(h("p", { class: "muted" }, "אין מנות שמתאימות לסינון."));
}

function renderChips() {
  const chip = (label, pressed, onClick) =>
    h("button", { type: "button", class: "chip", "aria-pressed": String(pressed), onClick }, label);
  chips.replaceChildren(
    chip("הכול", state.filter.cat === "all", () => setFilter({ cat: "all" })),
    ...CATEGORIES.map((c) => chip(c.name, state.filter.cat === c.id, () => setFilter({ cat: c.id }))),
    h("span", { class: "chips__sep", "aria-hidden": "true" }),
    chip("צמחוני", state.filter.vegetarian, () => setFilter({ vegetarian: !state.filter.vegetarian })),
    chip("טבעוני", state.filter.vegan, () => setFilter({ vegan: !state.filter.vegan })),
  );
}

function setFilter(patch) {
  Object.assign(state.filter, patch);
  renderChips();
  renderCatalog();
}

// ---- order
function syncSteppers() {
  for (const [id, card] of cards) card.setQty(state.order[id] ?? 0);
}

async function setQty(id, qty) {
  if (state.busy) return syncSteppers();
  const added = qty > (state.order[id] ?? 0);
  if (qty > 0) state.order[id] = qty; else delete state.order[id];
  state.version++;
  for (const item of pending) expire(item);
  syncSteppers();
  // Manual "+": a small dot flies from the card to the total, then the total rolls.
  if (added && !reducedMotion() && cards.has(id)) {
    await flyPill({ from: cards.get(id).stepperEl.getBoundingClientRect(), to: visibleTotal().getBoundingClientRect() });
  }
  summary.update(state.order);
}

function expire(item) {
  pending.delete(item);
  item.card.setState("expired");
  updateHint();
}

// ---- agent proposals (mock backend: totals computed deterministically, not by the "model")
function buildProposal(script) {
  const changes = script.changes.map((c) => ({ ...c, from: state.order[c.dishId] ?? 0 }));
  const after = { ...state.order };
  for (const c of changes) after[c.dishId] = c.to;
  return { baseVersion: state.version, changes, before: orderTotal(state.order), after: orderTotal(after) };
}

function showScripted(script) {
  agent.message("agent", script.message);
  const proposal = buildProposal(script);
  const card = createProposalCard(proposal, {
    onApprove: () => approve(item),
    onReject: () => { pending.delete(item); card.setState("rejected"); updateHint(); },
  });
  const item = { proposal, card, hint: script.hint };
  pending.add(item);
  agent.card(card.el);
  updateHint();
}

function visibleTotal() {
  const fits = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth;
  };
  return [summary.totalEl, barTotal].find(fits) ?? summary.totalEl;
}

async function approve(item) {
  const { proposal, card } = item;
  if (state.busy) return;
  if (proposal.baseVersion !== state.version) return expire(item);
  state.busy = true;
  pending.delete(item);
  updateHint();
  card.setState("applying");
  await wait(reducedMotion() ? 0 : 450);

  // "Backend executes" the approved change against the current version, then the UI choreography follows.
  const ids = proposal.changes.map((c) => c.dishId);
  for (const c of proposal.changes) state.order[c.dishId] = c.to;
  state.version++;
  for (const other of [...pending]) expire(other);
  card.setState("applied");

  if (!reducedMotion()) {
    const first = dishById(ids[0]).name;
    await flyPill({
      label: ids.length > 1 ? `${first} ועוד ${ids.length - 1}` : first,
      from: card.rowEl(0).getBoundingClientRect(),
      to: visibleTotal().getBoundingClientRect(),
    });
  }
  summary.open();
  summary.update(state.order, { highlight: ids });
  syncSteppers();
  if (!reducedMotion()) ids.forEach((id) => cards.get(id)?.pulse());
  state.busy = false;
}

async function onSend(text) {
  agent.message("user", text);
  await wait(reducedMotion() ? 0 : 500);
  if (scriptIndex < SCRIPTED_PROPOSALS.length) showScripted(SCRIPTED_PROPOSALS[scriptIndex++]);
  else agent.message("agent", DEMO_REPLY);
}

// ---- event strip + boot
document.getElementById("event-strip").textContent = describeEvent(loadEvent() ?? EVENT);

renderChips();
renderCatalog();
summary.update(state.order);
agent.message("agent", "שלום! אני יכול להמליץ על מנות מהתפריט, לשפר כמויות ולהסביר את השפעת השינוי על המחיר. כל שינוי יוצג לאישורכם לפני שהוא נכנס להזמנה.");
setTimeout(() => showScripted(SCRIPTED_PROPOSALS[scriptIndex++]), reducedMotion() ? 0 : 600);

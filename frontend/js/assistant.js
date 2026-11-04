// AI assistant panel (C4) on the dish screen. The assistant only proposes: the order changes when
// the customer accepts the card, through the same proposals API as the owner's (ADR 0003).
// Model text is shown via textContent only, never as HTML.
import { call } from "/js/customer-session.js";

const OP = { add_item: ["נוספה", "add"], set_quantity: ["שינוי", "chg"], remove_item: ["הוסרה", "chg"] };
const ERRORS = {
  assistant_limit: "הגעתם למספר ההודעות המרבי ליממה. אפשר להמשיך לבחור מנות בעצמכם.",
  assistant_failed: "העוזר לא הצליח לענות. נסו שוב בעוד רגע.",
  assistant_unavailable: "העוזר לא זמין כרגע.",
  invalid_transition: "ההזמנה כבר נשלחה, ולכן העוזר לא יכול לשנות אותה.",
  proposal_expired: "ההזמנה השתנתה מאז ההצעה, ולכן היא כבר לא בתוקף. בקשו מהעוזר הצעה חדשה.",
  proposal_not_pending: "ההצעה כבר לא פתוחה.",
};

const $ = (id) => document.getElementById(id);
const money = (v) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v);
const num = (v) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(v);

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

let orderId;
let hooks; // { beforeAnswer, afterAccept } from the dish screen

const bubble = (role, text) => el("p", { className: `msg ${role === "user" ? "me" : "bot"}`, textContent: text });

function card(p) {
  const delta = Number(p.price_after) - Number(p.price_before);
  const list = el("ul", { className: "diff" }, ...p.changes.map((c) => {
    const [label, cls] = OP[c.op];
    const amounts = c.op === "set_quantity" ? ` ${num(c.from_quantity)} → ${num(c.to_quantity)}`
      : c.op === "add_item" ? ` × ${num(c.to_quantity)}` : "";
    return el("li", {}, el("span", { className: `op ${cls}`, textContent: label }), `${c.name}${amounts}`);
  }));
  const node = el("div", { className: "proposal" },
    el("h4", { textContent: "העוזר מציע שינוי" }), list,
    el("p", { className: "diff-total" }, `סה"כ ${money(p.price_before)} → ${money(p.price_after)} `,
      el("span", { textContent: `(${delta >= 0 ? "+" : ""}${money(delta)})` })));
  if (p.note) node.append(el("p", { className: "why", textContent: p.note }));
  const decline = el("button", { type: "button", className: "btn ghost", textContent: "דחייה" });
  const accept = el("button", { type: "button", className: "btn primary", textContent: "אישור השינוי" });
  const status = el("p", { className: "help", role: "status" });
  const answer = async (action) => {
    accept.disabled = decline.disabled = true;
    status.textContent = action === "accept" ? "מעדכנים את ההזמנה…" : "";
    try {
      if (action === "accept") await hooks.beforeAnswer();
      await call(`/api/orders/${orderId}/proposals/${p.id}/${action}`, { method: "POST", body: action === "decline" ? "{}" : undefined });
      node.classList.add(action === "accept" ? "is-applied" : "is-rejected");
      status.textContent = action === "accept" ? "השינוי נכנס להזמנה." : "ההצעה נדחתה. ההזמנה לא השתנתה.";
      if (action === "accept") await hooks.afterAccept();
    } catch (err) {
      if (err.status === 401) { location.href = "/customer/"; return; }
      node.classList.add("is-rejected");
      status.className = "help error";
      status.textContent = ERRORS[err.code] ?? "לא הצלחנו לעדכן. נסו שוב.";
    }
    node.querySelector(".proposal-actions")?.remove();
  };
  accept.addEventListener("click", () => answer("accept"));
  decline.addEventListener("click", () => answer("decline"));
  node.append(el("div", { className: "proposal-actions" }, decline, accept), status);
  return node;
}

function render(view) {
  const items = view.messages.map((m) => bubble(m.role, m.text));
  if (!items.length) items.push(bubble("assistant", "שלום! אני יכול להציע מנות וכמויות לאירוע שלכם, ולענות על שאלות על התפריט. במה אפשר לעזור?"));
  if (view.proposal) items.push(card(view.proposal));
  $("ai-log").replaceChildren(...items);
  $("ai-log").scrollTop = $("ai-log").scrollHeight;
  $("ai-left").textContent = `נותרו ${view.remaining_today} הודעות ליממה.`;
}

async function send(e) {
  e.preventDefault();
  const input = $("ai-text");
  const text = input.value.trim();
  if (!text) return;
  const button = $("ai-form").querySelector("button");
  input.disabled = button.disabled = true;
  $("ai-log").append(bubble("user", text), bubble("assistant", "חושב…"));
  $("ai-log").scrollTop = $("ai-log").scrollHeight;
  try {
    render(await call(`/api/orders/${orderId}/chat`, { method: "POST", body: JSON.stringify({ message: text }) }));
    input.value = "";
  } catch (err) {
    if (err.status === 401) { location.href = "/customer/"; return; }
    $("ai-log").lastChild.remove();
    $("ai-log").append(el("p", { className: "help error", role: "alert", textContent: ERRORS[err.code] ?? "משהו השתבש. נסו שוב." }));
  } finally {
    input.disabled = button.disabled = false;
    input.focus();
  }
}

function setOpen(open) {
  $("ai").classList.toggle("open", open);
  $("ai-fab").setAttribute("aria-expanded", String(open));
  if (open) $("ai-text").focus();
  else $("ai-fab").focus();
}

/** Shows the panel if the assistant is available for this draft; quietly does nothing if not. */
export async function initAssistant(id, screenHooks) {
  orderId = encodeURIComponent(id);
  hooks = screenHooks;
  let view;
  try {
    view = await call(`/api/orders/${orderId}/chat`);
  } catch {
    return;
  }
  if (!view.available) return;
  render(view);
  $("ai-form").addEventListener("submit", send);
  $("ai-fab").addEventListener("click", () => setOpen(!$("ai").classList.contains("open")));
  $("ai-close").addEventListener("click", () => setOpen(false));
  $("ai").addEventListener("keydown", (e) => { if (e.key === "Escape" && $("ai").classList.contains("open")) setOpen(false); });
  $("ai").hidden = false;
  $("ai-fab").hidden = false;
}

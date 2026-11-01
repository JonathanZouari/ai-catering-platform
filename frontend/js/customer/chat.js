// The AI chat on the customer page. It only proposes; the customer approves each card here.
import { attempt, h, notify } from "/js/ui.js";

const DETAILS = {
  adults: "מבוגרים",
  children: "ילדים",
  vegetarian_guests: "צמחונים",
  vegan_guests: "טבעונים",
  restricted_guests: "הגבלות אחרות",
  dietary_notes: "הערות תזונה",
};

const panel = h("aside", { className: "chat", hidden: true, "aria-label": "עוזר להזמנה" });
const toggle = h("button", {
  className: "chat-toggle",
  hidden: true,
  onclick: () => setOpen(panel.hidden),
}, "שאלו את העוזר");
let orderApi;
let onOrder;
let chat = null;

function setOpen(isOpen) {
  panel.hidden = !isOpen;
  if (isOpen) panel.querySelector("input")?.focus();
}

const shekel = (value) => h("bdi", {}, `₪${Number(value).toFixed(2)}`);

function describe(change) {
  if (change.type === "update_details") {
    return `${DETAILS[change.field]}: ${change.before ?? "—"} ← ${change.after ?? "—"}`;
  }
  if (change.type === "remove_item") return `הסרה: ${change.name}`;
  if (change.type === "add_item" && change.before === null) {
    return `הוספה: ${change.name} × ${Number(change.after)}`;
  }
  return `${change.name}: ${Number(change.before ?? 0)} ← ${Number(change.after)}`;
}

async function decide(proposal, action) {
  const result = await attempt(() => orderApi(`/proposals/${proposal.id}/${action}`, { method: "POST" }));
  if (result) onOrder(result.order);
  await load();
}

function card(proposal) {
  const difference = Number(proposal.price_after) - Number(proposal.price_before);
  return h("article", { className: "proposal" },
    h("strong", {}, "הצעה לשינוי"),
    h("p", {}, proposal.rationale),
    h("ul", {}, proposal.changes.map((change) => h("li", {}, describe(change)))),
    h("p", {}, "סה״כ: ", shekel(proposal.price_before), " ← ", shekel(proposal.price_after),
      difference ? ` (${difference > 0 ? "+" : "−"}₪${Math.abs(difference).toFixed(2)})` : ""),
    h("div", { className: "actions" },
      h("button", { onclick: () => decide(proposal, "approve") }, "אישור השינוי"),
      h("button", { className: "secondary", onclick: () => decide(proposal, "reject") }, "דחייה")));
}

function draw() {
  const messages = h("div", { className: "chat-log", role: "log" },
    chat.messages.map(({ role, text }) => h("p", { className: `bubble ${role}` }, text)),
    chat.proposals.map(card));
  const input = h("input", { maxLength: 1000, required: true, "aria-label": "הודעה לעוזר", disabled: !chat.available });
  const send = h("button", { type: "submit", disabled: !chat.available }, "שליחה");
  const form = h("form", {
    className: "chat-form",
    onsubmit: async (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      input.disabled = true;
      send.disabled = true;
      chat.messages.push({ role: "user", text: message });
      draw();
      try {
        const answer = await orderApi("/chat", { method: "POST", body: JSON.stringify({ message }) });
        chat.messages.push({ role: "assistant", text: answer.reply });
        chat.proposals = answer.proposals;
      } catch (error) {
        chat.messages.pop();
        if (error.code === "ai_limit_reached") chat.available = false;
        notify(error.message, true);
      }
      draw();
    },
  }, input, send);

  panel.replaceChildren(
    h("header", { className: "screen-header" },
      h("h2", {}, "עוזר להזמנה"),
      h("button", { className: "secondary", onclick: () => setOpen(false) }, "סגירה")),
    messages,
    h("p", { className: "muted" }, chat.available
      ? "העוזר מציע, ואתם מאשרים. התשובות נוצרות על ידי AI. אל תכתבו כאן פרטים אישיים."
      : "העוזר אינו זמין כרגע. אפשר להמשיך להזמין בתפריט."),
    form);
  messages.scrollTop = messages.scrollHeight;
  if (!panel.hidden) form.querySelector("input").focus();
}

async function load() {
  const loaded = await attempt(() => orderApi("/chat"));
  if (loaded) {
    chat = loaded;
    draw();
  }
}

export function mountChat(api, onOrderChanged) {
  orderApi = api;
  onOrder = onOrderChanged;
  document.body.append(toggle, panel);
}

export function syncChat(isVisible) {
  toggle.hidden = !isVisible;
  if (!isVisible) panel.hidden = true;
  else if (!chat) load();
}

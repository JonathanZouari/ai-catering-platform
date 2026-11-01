import { h } from "../dom.js";

// Agent side panel / bottom sheet content: note, message log, input. Order summary is slotted in.
export function createAgentPanel({ summaryEl, onSend }) {
  const log = h("div", { class: "agent__log", role: "log", "aria-live": "polite", "aria-label": "שיחה עם העוזר" });
  const input = h("input", { class: "agent__input", type: "text", "aria-label": "הודעה לעוזר", placeholder: "שאלו על מנה או בקשו הצעה", autocomplete: "off" });
  const form = h("form", {
    class: "agent__form",
    onSubmit: (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      onSend(text);
    },
  }, input, h("button", { type: "submit", class: "btn btn-primary" }, "שליחה"));
  const closeBtn = h("button", { type: "button", class: "agent__close link", "aria-label": "סגירת העוזר" }, "סגירה");
  const el = h("aside", { id: "agent", class: "agent card", "aria-label": "עוזר התפריט" },
    h("header", { class: "agent__head" },
      h("div", {},
        h("h2", {}, "הסוכן"),
        h("p", { class: "muted" }, "מציע רק מנות מהתפריט של העסק, ולא משנה כלום בלי אישור שלך")),
      h("span", { class: "pill pill-draft" }, "הדגמה"),
      closeBtn),
    log, form,
    h("div", { class: "agent__summary" }, summaryEl),
  );

  let delay = 0;
  const add = (node) => {
    node.classList.add("fade-up");
    node.style.animationDelay = `${delay}ms`;
    delay = Math.min(delay + 200, 600);
    setTimeout(() => (delay = 0), 800);
    log.append(node);
    log.scrollTop = log.scrollHeight;
  };
  return {
    el, closeBtn,
    message(role, text) { add(h("p", { class: `msg msg--${role}` }, text)); },
    card(node) { add(node); },
  };
}

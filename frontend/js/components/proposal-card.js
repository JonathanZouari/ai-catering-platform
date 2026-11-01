import { h } from "../dom.js";
import { ils } from "../format.js";
import { UNITS, dishById } from "../mock/menu.js";

const STATE_NOTE = {
  applying: "מעדכן…",
  applied: "✓ נוסף להזמנה",
  rejected: "ההצעה נדחתה. ההזמנה לא השתנתה.",
  expired: "ההזמנה השתנתה. אפשר לבקש הצעה חדשה.",
};

// Diff card (UX_UI_SPEC C4). Approve is the only path to change the order.
// States: pending → applying → applied | rejected | expired.
export function createProposalCard(proposal, { onApprove, onReject }) {
  const rows = proposal.changes.map((c) => {
    const dish = dishById(c.dishId);
    const unit = UNITS[dish.unit];
    return h("li", { class: "proposal__row" },
      h("span", {}, dish.name),
      h("span", { class: "num" }, h("span", { dir: "rtl" }, `${c.from} ← ${c.to}`), ` ${unit.many}`));
  });
  const reject = h("button", { type: "button", class: "btn btn-secondary", onClick: () => onReject() }, "לא עכשיו");
  const approve = h("button", { type: "button", class: "btn btn-primary", onClick: () => onApprove() }, "אישור");
  const note = h("p", { class: "proposal__note", role: "status" });
  const actions = h("div", { class: "proposal__actions" }, reject, approve);
  const el = h("section", { class: "proposal card", "data-state": "pending", "aria-label": "שינוי מוצע" },
    h("h4", {}, "שינוי מוצע"),
    h("ul", { class: "proposal__rows" }, rows),
    h("p", { class: "proposal__total" },
      h("span", {}, "סה״כ"),
      h("span", { class: "num" }, h("span", { dir: "rtl" }, `${ils(proposal.before)} ← ${ils(proposal.after)}`))),
    actions, note);

  return {
    el,
    rowEl: (i = 0) => rows[i],
    setState(state) {
      el.dataset.state = state;
      actions.hidden = state !== "pending";
      note.textContent = STATE_NOTE[state] ?? "";
    },
  };
}

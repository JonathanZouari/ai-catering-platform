// A1: submitted orders, and the caterer's decision on each one.
import { adminApi, postJson } from "/js/admin/auth.js";
import { attempt, field, h, openDialog, select, textOrNull } from "/js/ui.js";

const STATUS = {
  pending_approval: "ממתין לאישור",
  approved: "אושר",
  rejected: "נדחה",
};
const FILTERS = [["pending_approval", "ממתינות לאישור"], ["approved", "מאושרות"], ["rejected", "נדחו"], ["", "כל ההזמנות"]];

let filter = "pending_approval";

const shekel = (value) => h("bdi", {}, `₪${Number(value).toFixed(2)}`);
const dateText = (value) => new Date(`${value}T12:00`).toLocaleDateString("he-IL");
const timeText = (value) => new Date(value).toLocaleTimeString("he-IL", {
  hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jerusalem",
});

export async function renderOrders(view) {
  const query = filter ? `?status=${filter}` : "";
  const orders = await adminApi(`/api/admin/orders${query}`);
  const status = select(FILTERS, filter);
  status.addEventListener("change", () => {
    filter = status.value;
    attempt(() => renderOrders(view));
  });

  view.replaceChildren(
    h("h1", {}, "הזמנות"),
    h("section", { className: "card" },
      field("סינון", status),
      orders.length
        ? h("ul", { className: "rows" }, orders.map((order) => h("li", {},
          h("div", {},
            h("strong", {}, order.customer_name),
            h("span", { className: "badge" }, STATUS[order.status]),
            h("div", { className: "muted" },
              `${dateText(order.event_date)} · ${order.guests} סועדים · `, shekel(order.total))),
          h("div", { className: "actions" },
            h("button", {
              className: "secondary",
              "aria-label": `פתיחת ההזמנה של ${order.customer_name}`,
              onclick: () => attempt(() => renderDetail(view, order.id)),
            }, "פתיחה")))))
        : h("p", { className: "empty" }, "אין הזמנות להצגה.")),
  );
}

function decide(view, order, action, title, isNoteRequired) {
  const note = h("textarea", { rows: 3, maxLength: 1000, required: isNoteRequired });
  const hint = isNoteRequired ? "הלקוח יראה את ההערה בעמוד ההזמנה" : "לא חובה. הלקוח יראה את ההערה";
  openDialog(title, field("הערה ללקוח", note, hint), async () => {
    await postJson(`/api/admin/orders/${order.id}/${action}`, {
      version: order.version,
      note: textOrNull(note.value),
    });
    await renderDetail(view, order.id);
  }, title);
}

function row(label, value) {
  return value === null || value === "" ? null : h("p", {}, h("strong", {}, `${label}: `), value);
}

function dietCounts({ vegetarian_guests: vegetarian, vegan_guests: vegan, restricted_guests: restricted }) {
  return [[vegetarian, "צמחונים"], [vegan, "טבעונים"], [restricted, "הגבלות אחרות"]]
    .filter(([count]) => count > 0)
    .map(([count, label]) => `${count} ${label}`)
    .join(", ");
}

async function renderDetail(view, id) {
  const order = await adminApi(`/api/admin/orders/${id}`);
  const { customer, event } = order;
  const delivery = order.fulfillment_type === "delivery";

  const sections = [
    h("button", { className: "secondary", onclick: () => attempt(() => renderOrders(view)) }, "חזרה לרשימה"),
    h("h1", {}, `הזמנה של ${customer.full_name}`),
    h("p", {}, h("span", { className: "badge" }, STATUS[order.status])),
    h("section", { className: "card" },
      h("h2", {}, "פרטי לקוח ואירוע"),
      h("p", {}, h("strong", {}, "טלפון: "), h("a", { href: `tel:${customer.phone.replace(/\s/g, "")}` }, h("bdi", {}, customer.phone))),
      row("סוג האירוע", event.event_type),
      row("תאריך", dateText(event.event_date)),
      row("שעה", timeText(order.requested_at)),
      row("סועדים", `${event.adults} מבוגרים, ${event.children} ילדים`),
      row("תזונה", dietCounts(event)),
      row("הערות הלקוח", event.dietary_notes),
      row("אספקה", delivery ? `משלוח: ${order.delivery_address}, ${order.delivery_city}` : "איסוף עצמי"),
      order.kashrut_warning_acknowledged
        ? h("p", { className: "alert" }, "הלקוח אישר שההזמנה מערבת מנות בשריות וחלביות.")
        : null),
    h("section", { className: "card" },
      h("h2", {}, "מנות"),
      h("ul", { className: "rows" }, order.lines.map((line) => h("li", {},
        h("div", {}, h("strong", {}, line.name),
          h("div", { className: "muted" }, h("bdi", {}, `${Number(line.quantity)} × ₪${Number(line.unit_price).toFixed(2)}`))),
        shekel(line.line_total)))),
      delivery ? h("p", {}, "משלוח: ", shekel(order.delivery_fee)) : null,
      h("p", {}, h("strong", {}, "סה״כ כולל מע״מ: "), shekel(order.total))),
    order.decision_note ? h("section", { className: "card" }, h("h2", {}, "ההערה שנשלחה ללקוח"), h("p", {}, order.decision_note)) : null,
    order.status === "pending_approval"
      ? h("div", { className: "actions" },
        h("button", { onclick: () => decide(view, order, "approve", "אישור ההזמנה", false) }, "אישור ההזמנה"),
        h("button", { className: "secondary danger", onclick: () => decide(view, order, "reject", "דחיית ההזמנה", true) }, "דחיית ההזמנה"))
      : null,
  ];
  view.replaceChildren(...sections.filter(Boolean));
  window.scrollTo(0, 0);
}

import { api } from "../../js/api.js";
import { h, clear, showToast } from "./dom.js";
import { DISH_UNITS } from "./schema.js";

const STATUS = { pending_approval: "ממתינה לאישור", approved: "אושרה", rejected: "נדחתה", draft: "טיוטה" };
const money = (minor) => new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format((minor ?? 0) / 100);

export async function submitDecision({ client, orderId, decision, expectedVersion, note, isAlive = () => true }) {
  const { data, error } = await client.auth.getSession();
  if (!isAlive()) return null;
  if (error || !data?.session?.access_token) {
    throw Object.assign(new Error("נדרשת כניסה מחדש לחשבון הבעלים."), { status: 401 });
  }
  return api(`/api/admin/orders/${orderId}/decision`, {
    method: "POST", cache: "no-store",
    headers: { Authorization: `Bearer ${data.session.access_token}` },
    body: JSON.stringify({ decision, expected_version: expectedVersion, note: note.trim() }),
  });
}

export function openOrderDecision({ client, row, customerName, isSessionAlive, onSaved, onSessionLost, registerDialog }) {
  let open = true;
  let saving = false;
  let loaded = false;
  let conflicted = false;
  let attempt = null; // Preserve the exact payload when a response is lost.
  const isAlive = () => open && isSessionAlive();
  const details = h("div", { class: "stack" }, "טוען את פרטי ההזמנה…");
  const message = h("div", { role: "status", "aria-live": "polite" });
  const note = h("textarea", { class: "input", id: "decision-note", maxlength: "2000", rows: "3" });
  const approve = h("button", { class: "btn btn-primary", type: "button", disabled: true, onclick: () => save("approved") }, "אישור ההזמנה");
  const reject = h("button", { class: "btn btn-secondary", type: "button", disabled: true, onclick: () => save("rejected") }, "דחיית הבקשה");
  const closeButton = h("button", { class: "btn btn-ghost", type: "button", onclick: () => { if (!saving) close(); } }, "סגירה");
  const pending = row.status === "pending_approval";
  const dialog = h("dialog", {
    class: "row-dialog", "aria-labelledby": "decision-title",
    oncancel: (event) => { event.preventDefault(); if (!saving) close(); },
  },
    h("header", { class: "dialog-head" }, h("h2", { id: "decision-title" }, `בדיקת הזמנה ${row.id}`),
      h("p", {}, customerName || `לקוח ${row.customer_id}`), h("p", {}, STATUS[row.status] ?? row.status)),
    details,
    pending ? h("div", { class: "form-field" }, h("label", { for: "decision-note" }, "הודעה ללקוח (רשות)"), note,
      h("p", { class: "muted" }, "ההחלטה סופית בשלב זה. האישור מתייחס לפריטים ולמחיר המקורי המוצגים כאן."))
      : h("p", {}, row.decision_note || "אין הודעה מהעסק."),
    message,
    h("div", { class: "form-actions" }, pending ? [approve, reject] : [], closeButton),
  );
  function close() {
    open = false;
    dialog.close();
    dialog.remove();
    registerDialog(null);
  }
  function controls() {
    approve.disabled = saving || !loaded || conflicted || (attempt && attempt.decision !== "approved");
    reject.disabled = saving || !loaded || conflicted || (attempt && attempt.decision !== "rejected");
    note.disabled = saving || Boolean(attempt) || conflicted;
    closeButton.disabled = saving;
  }
  async function save(decision) {
    if (!isAlive() || saving || !loaded || conflicted || !pending) return;
    if (attempt && attempt.decision !== decision) return;
    attempt ??= { decision, note: note.value ?? "" };
    saving = true;
    controls();
    message.textContent = "שומר את ההחלטה…";
    try {
      const result = await submitDecision({ client, orderId: row.id, expectedVersion: row.version, ...attempt, isAlive });
      if (!isAlive() || !result) return;
      close();
      onSaved();
      showToast("ההחלטה נשמרה. הלקוח יראה אותה בבדיקת המצב הבאה.");
    } catch (error) {
      if (!isAlive()) return;
      if (error.status === 401 || error.status === 403) {
        message.textContent = "אין הרשאה לשמור החלטה. יש להיכנס מחדש לחשבון הבעלים.";
        conflicted = true;
        if (error.status === 401) onSessionLost();
      } else if (error.status === 409 || error.status === 404) {
        conflicted = true;
        message.textContent = "ההזמנה השתנתה או אינה זמינה להחלטה. סגרו ופתחו אותה מחדש מהרשימה המעודכנת.";
        onSaved();
      } else if (error.status === 422) {
        attempt = null;
        message.textContent = "פרטי ההחלטה אינם תקינים. בדקו את ההודעה ללקוח ונסו שוב.";
      } else {
        message.textContent = "לא התקבל אישור לשמירה. אפשר לנסות שוב את אותה החלטה; ניסיון חוזר לא ישמור אותה פעמיים.";
      }
    } finally {
      saving = false;
      if (isAlive()) controls();
    }
  }
  async function load() {
    try {
      const [items, event, address] = await Promise.all([
        client.from("order_items").select("name,quantity_milli,unit,line_total_minor").eq("order_id", row.id).order("dish_id"),
        client.from("events").select("event_type,event_date,adults,children,dietary_notes").eq("id", row.event_id).single(),
        row.delivery_address_id ? client.from("addresses").select("street,house_number,city,access_notes").eq("id", row.delivery_address_id).single() : Promise.resolve({ data: null }),
      ]);
      if (!isAlive()) return;
      if (items.error || event.error || address.error || (row.delivery_address_id && !address.data) || !items.data?.length || !event.data) throw new Error("read failed");
      const e = event.data;
      clear(details).append(
        h("p", {}, `${e.event_type}, ${e.event_date} · ${e.adults} מבוגרים, ${e.children} ילדים`),
        h("p", {}, `מועד אספקה: ${new Date(row.requested_at).toLocaleString("he-IL", { timeZone: "Asia/Jerusalem" })}`),
        h("p", {}, row.fulfillment_type === "delivery" ? `משלוח: ${address.data?.street ?? ""} ${address.data?.house_number ?? ""}, ${address.data?.city ?? ""}` : "איסוף עצמי מהעסק"),
        ...(address.data?.access_notes ? [h("p", {}, `הערות הגעה: ${address.data.access_notes}`)] : []),
        ...(e.dietary_notes ? [h("p", {}, `הערות תזונה: ${e.dietary_notes}`)] : []),
        h("ul", {}, items.data.map(item => h("li", {}, `${item.name} · ${item.quantity_milli / 1000} ${DISH_UNITS[item.unit] ?? ""} · ${money(item.line_total_minor)}`))),
        h("p", {}, `דמי משלוח: ${money(row.delivery_fee_minor)}`),
        h("strong", {}, `סה״כ: ${money(row.total_minor)}`),
      );
      loaded = true;
      controls();
    } catch {
      if (isAlive()) details.textContent = "לא ניתן לטעון את פרטי ההזמנה. סגרו ופתחו מחדש כדי לבדוק לפני קבלת החלטה.";
    }
  }
  document.body.append(dialog);
  registerDialog({ close });
  dialog.showModal();
  load();
}

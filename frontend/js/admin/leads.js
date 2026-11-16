// Lead CRM: submitted requests ranked by the chance they become a sale.
// The score is computed by the backend and is advisory. The caterer decides.
import { adminApi, patchJson, postJson } from "/js/admin/auth.js";
import { attempt, field, h, openDialog, select } from "/js/ui.js";

const STAGE = { new: "חדש", qualified: "מתאים", won: "נסגר", lost: "אבד" };
const FILTERS = [["", "כל הלידים"], ...Object.entries(STAGE)];
// Each band has a text label too, so the meaning never depends on colour alone.
const BAND = {
  high: ["סיכוי גבוה", "approved"],
  medium: ["סיכוי בינוני", "pending_approval"],
  low: ["סיכוי נמוך", "rejected"],
};

let filter = "";

const percent = (score) => `${Math.round(Number(score) * 100)}%`;
const dateText = (value) => new Date(`${value}T12:00`).toLocaleDateString("he-IL");
const stamp = (value) => new Date(value).toLocaleString("he-IL", { timeZone: "Asia/Jerusalem" });
const bandBadge = (lead) => h("span", { className: `badge dot ${BAND[lead.band][1]}` },
  `${BAND[lead.band][0]} · ${percent(lead.score)}`);

export async function renderLeads(view) {
  const leads = await adminApi(`/api/admin/leads${filter ? `?stage=${filter}` : ""}`);
  const stage = select(FILTERS, filter);
  stage.addEventListener("change", () => {
    filter = stage.value;
    attempt(() => renderLeads(view));
  });

  view.dataset.screen = "leads";
  view.replaceChildren(
    h("div", { className: "page-head" },
      h("div", {}, h("p", { className: "eyebrow" }, "ניהול לידים"), h("h1", {}, "לידים"))),
    h("p", { className: "muted" }, "הציון הוא הערכה בלבד, לפי נתוני הבקשה. ההחלטה תמיד שלכם."),
    h("div", { className: "card filter-bar" }, field("הצגת לידים", stage)),
    leads.length
      ? h("ul", { className: "order-cards" }, leads.map((lead) => h("li", { className: "order-card" },
        h("span", { className: "avatar", "aria-hidden": "true" }, lead.customer_name[0]),
        h("div", { className: "order-main" },
          h("div", { className: "order-name" },
            h("strong", {}, lead.customer_name),
            bandBadge(lead),
            h("span", { className: "muted" }, STAGE[lead.stage])),
          h("p", { className: "order-meta" },
            h("span", {}, h("span", { className: "icon icon-calendar_month", "aria-hidden": "true" }), dateText(lead.event_date)),
            h("span", {}, h("span", { className: "icon icon-group", "aria-hidden": "true" }), `${lead.guests} סועדים`))),
        h("div", { className: "actions" },
          h("button", {
            className: "secondary",
            "aria-label": `פתיחת הליד של ${lead.customer_name}`,
            onclick: () => attempt(() => renderDetail(view, lead.id)),
          }, "פתיחה")))))
      : h("div", { className: "card empty-state" },
        h("p", { className: "empty" }, "אין לידים להצגה."),
        h("p", { className: "muted" }, "בקשה להצעת מחיר שנשלחת מהאתר מופיעה כאן עם ציון.")),
  );
}

async function renderDetail(view, id) {
  const lead = await adminApi(`/api/admin/leads/${id}`);
  view.dataset.screen = "lead-detail";
  const stage = select(Object.entries(STAGE), lead.stage);
  stage.addEventListener("change", () => attempt(async () => {
    await patchJson(`/api/admin/leads/${id}/stage`, { stage: stage.value });
    await renderDetail(view, id);
  }, "השלב עודכן"));

  const sign = (points) => (points > 0 ? "+" : "−");
  view.replaceChildren(
    h("button", { className: "secondary", onclick: () => attempt(() => renderLeads(view)) },
      h("span", { className: "icon icon-arrow_back", "aria-hidden": "true" }), "חזרה לרשימה"),
    h("div", { className: "page-head" },
      h("div", {}, h("p", { className: "eyebrow" }, "פרטי ליד"), h("h1", {}, lead.customer_name)),
      bandBadge(lead)),
    h("section", { className: "card" },
      h("h2", {}, "פרטים"),
      h("p", {}, h("strong", {}, "טלפון: "), h("a", { href: `tel:${lead.phone.replace(/\s/g, "")}` }, h("bdi", {}, lead.phone))),
      h("p", {}, h("strong", {}, "תאריך האירוע: "), dateText(lead.event_date)),
      h("p", {}, h("strong", {}, "סועדים: "), String(lead.guests)),
      field("שלב", stage)),
    h("section", { className: "card" },
      h("h2", {}, "למה הציון הזה"),
      lead.reasons.length
        ? h("ul", { className: "rows" }, lead.reasons.map((reason) => h("li", {},
          h("span", {}, reason.label), h("strong", {}, `${sign(reason.points)}${Math.abs(reason.points)}`))))
        : h("p", { className: "muted" }, "אין מספיק נתונים. הציון הוא שיעור הבסיס."),
      lead.unknown.length
        ? h("p", { className: "muted" }, `לא ידוע, ולא נספר לרעה: ${lead.unknown.join(", ")}`)
        : null),
    h("section", { className: "card" },
      h("h2", {}, "היסטוריה והערות"),
      h("button", { onclick: () => addNote(view, id) }, h("span", { className: "icon icon-edit", "aria-hidden": "true" }), "הוספת הערה"),
      lead.events.length
        ? h("ul", { className: "rows" }, lead.events.map((event) => h("li", {},
          h("span", {}, event.kind === "note" ? event.note : `השלב שונה ל${STAGE[event.stage]}`),
          h("span", { className: "muted" }, stamp(event.created_at)))))
        : h("p", { className: "muted" }, "עדיין אין היסטוריה.")),
  );
  window.scrollTo(0, 0);
}

function addNote(view, id) {
  const note = h("textarea", { rows: 3, maxLength: 1000, required: true });
  openDialog("הערה חדשה", field("הערה", note), async () => {
    await postJson(`/api/admin/leads/${id}/notes`, { note: note.value });
    await renderDetail(view, id);
  });
}

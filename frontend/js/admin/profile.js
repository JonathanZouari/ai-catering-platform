// A6: business profile, branding, and kashrut settings.
import { adminApi, getConfig, patchJson, upload } from "/js/admin/auth.js";
import { attempt, field, h, select, textOrNull } from "/js/admin/ui.js";

const MIXING = [
  ["warn", "להציג אזהרה ולאפשר להמשיך"],
  ["block", "לחסום הזמנה שמערבת בשר וחלב"],
];
const DEFAULT_COLOR = "#7a4f2a";

export async function renderProfile(view) {
  const [profile, { storage_public_url: storageUrl }] = await Promise.all([
    adminApi("/api/admin/profile"),
    getConfig(),
  ]);
  const refresh = () => renderProfile(view);

  const link = `${location.origin}/c/${profile.slug}/`;
  const name = h("input", { required: true, maxLength: 120, value: profile.name });
  const phone = h("input", { type: "tel", dir: "ltr", maxLength: 30, value: profile.contact_phone ?? "" });
  const color = h("input", { type: "color", value: profile.brand_color ?? DEFAULT_COLOR });
  const kashrut = h("input", { maxLength: 200, value: profile.kashrut_status ?? "" });
  const mixing = select(MIXING, profile.kashrut_mixing_rule);

  const uploader = (label, accept, url, path) => {
    const input = h("input", {
      type: "file",
      accept,
      onchange: () => attempt(async () => {
        await upload(url, input.files[0]);
        await refresh();
      }, "הקובץ הועלה"),
    });
    return field(label, input, path ? "קיים קובץ. העלאה חדשה תחליף אותו." : "עדיין לא הועלה קובץ.");
  };

  view.replaceChildren(
    h("h1", {}, "פרופיל העסק"),
    h("section", { className: "card" },
      h("h2", {}, "הקישור ללקוחות"),
      h("p", {}, h("bdi", { dir: "ltr" }, link)),
      h("button", {
        className: "secondary",
        onclick: () => attempt(() => navigator.clipboard.writeText(link), "הקישור הועתק"),
      }, "העתקת הקישור")),
    h("form", {
      className: "card",
      onsubmit: async (event) => {
        event.preventDefault();
        await attempt(async () => {
          await patchJson("/api/admin/profile", {
            name: name.value.trim(),
            contact_phone: textOrNull(phone.value),
            brand_color: color.value,
            kashrut_status: textOrNull(kashrut.value),
            kashrut_mixing_rule: mixing.value,
          });
        }, "הפרטים נשמרו");
      },
    },
    h("h2", {}, "פרטי העסק"),
    field("שם העסק", name),
    field("טלפון ליצירת קשר", phone),
    field("צבע המותג", color),
    h("h2", {}, "כשרות"),
    field("סטטוס כשרות", kashrut, "מוצג ללקוחות, למשל שם הגוף המכשיר. ריק = לא צוין"),
    field("הזמנה שמערבת בשר וחלב", mixing),
    h("button", { type: "submit" }, "שמירה")),
    h("section", { className: "card" },
      h("h2", {}, "קבצים"),
      profile.logo_path && storageUrl
        ? h("img", { className: "preview", src: `${storageUrl}/${profile.logo_path}`, alt: "הלוגו של העסק" })
        : null,
      uploader("לוגו", "image/png,image/jpeg,image/webp", "/api/admin/profile/logo", profile.logo_path),
      uploader("תעודת כשרות", "image/png,image/jpeg,image/webp,application/pdf",
        "/api/admin/profile/kashrut-certificate", profile.kashrut_certificate_path)),
  );
}

import { h } from "../dom.js";

const STATUS = {
  draft: ["טיוטה", "pill-draft"],
  pending: ["ממתין לאישור", "pill-pending"],
  approved: ["אושרה", "pill-approved"],
  rejected: ["לא אושרה", "pill-rejected"],
};

// `label` overrides the default text (the colour still follows the status).
export function statusPill(status, label) {
  const [text, cls] = STATUS[status];
  return h("span", { class: `pill ${cls}` }, label ?? text);
}

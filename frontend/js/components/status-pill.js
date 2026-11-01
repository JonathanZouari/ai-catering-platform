import { h } from "../dom.js";

const STATUS = {
  draft: ["טיוטה", "pill-draft"],
  pending: ["ממתין לאישור", "pill-pending"],
  approved: ["אושרה", "pill-approved"],
  rejected: ["לא אושרה", "pill-rejected"],
};

export function statusPill(status) {
  const [text, cls] = STATUS[status];
  return h("span", { class: `pill ${cls}` }, text);
}

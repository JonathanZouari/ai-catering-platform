// Mobile: agent panel becomes a bottom sheet over a blurred catalog. On desktop the toggle is hidden by CSS.
// While open it behaves as a modal dialog: focus moves in, Tab stays inside, Escape closes, focus returns.
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), summary, [tabindex="0"]';

export function bindBottomSheet({ panel, openBtn, closeBtn, backdrop, onChange }) {
  let opener = null;
  const set = (open) => {
    document.body.classList.toggle("sheet-open", open);
    backdrop.hidden = !open;
    panel.toggleAttribute("data-open", open);
    openBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      opener = document.activeElement;
      panel.setAttribute("role", "dialog");
      panel.setAttribute("aria-modal", "true");
      panel.focus({ preventScroll: true });
    } else {
      panel.removeAttribute("role");
      panel.removeAttribute("aria-modal");
      // The opener (e.g. the hint pill) may hide itself while the sheet is open: fall back to the bar button.
      (opener && opener.offsetParent !== null ? opener : openBtn).focus();
    }
    onChange?.(open);
  };
  openBtn.addEventListener("click", () => set(true));
  closeBtn.addEventListener("click", () => set(false));
  backdrop.addEventListener("click", () => set(false));
  document.addEventListener("keydown", (e) => {
    if (!panel.hasAttribute("data-open")) return;
    if (e.key === "Escape") return set(false);
    if (e.key !== "Tab") return;
    const items = [...panel.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items.at(-1);
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  panel.tabIndex = -1;
  return { open: () => set(true), close: () => set(false) };
}

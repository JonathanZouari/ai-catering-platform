// Mobile: agent panel becomes a bottom sheet over a blurred catalog. On desktop the toggle is hidden by CSS.
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
      panel.focus({ preventScroll: true });
    } else {
      panel.removeAttribute("role");
      opener?.focus?.();
    }
    onChange?.(open);
  };
  openBtn.addEventListener("click", () => set(true));
  closeBtn.addEventListener("click", () => set(false));
  backdrop.addEventListener("click", () => set(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.hasAttribute("data-open")) set(false);
  });
  panel.tabIndex = -1;
  return { open: () => set(true), close: () => set(false) };
}

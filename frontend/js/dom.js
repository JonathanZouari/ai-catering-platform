// Tiny element builder shared by the customer and admin pages.
// Text always goes through textContent (via append), never innerHTML, so data cannot inject markup.
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value !== false && value != null) el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...children.flat().filter((c) => c != null && c !== false));
  return el;
}

// Isolates a left-to-right run (price, date, time, ID) inside Hebrew text.
export const ltr = (text) => h("bdi", { dir: "ltr" }, text);

export const $ = (id) => document.getElementById(id);

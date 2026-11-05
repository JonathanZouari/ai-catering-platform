// Small DOM builders. Everything goes through textContent and setAttribute, never innerHTML,
// so database values cannot inject markup.

const PROPERTIES = new Set(["value", "checked", "disabled", "selected", "open"]);
const SVG_NS = "http://www.w3.org/2000/svg";

function build(element, props, children) {
  for (const [key, value] of Object.entries(props ?? {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") element.addEventListener(key.slice(2), value);
    else if (PROPERTIES.has(key)) element[key] = value;
    else element.setAttribute(key, value === true ? "" : String(value));
  }
  element.append(...children.flat(Infinity).filter((child) => child !== null && child !== undefined && child !== false));
  return element;
}

export const h = (tag, props, ...children) => build(document.createElement(tag), props, children);
export const svg = (tag, props, ...children) => build(document.createElementNS(SVG_NS, tag), props, children);

// A machine identifier, always in its own left-to-right block and never inside a Hebrew sentence.
export const ident = (text) => h("code", { class: "ident", dir: "ltr" }, text);

export function errorBlock({ message, detail }, { onRetry } = {}) {
  return h(
    "div",
    { class: "notice notice-danger", role: "alert" },
    h("p", { class: "notice-title" }, message),
    detail && h("p", {}, h("code", { class: "ident", dir: "ltr" }, detail)),
    onRetry && h("button", { class: "btn btn-secondary", type: "button", onclick: onRetry }, "ניסיון נוסף"),
  );
}

export function clear(element) {
  element.replaceChildren();
  return element;
}

let toastTimer;
export function showToast(text) {
  const region = document.getElementById("toast");
  region.textContent = text;
  region.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    region.hidden = true;
    region.textContent = "";
  }, 5000);
}

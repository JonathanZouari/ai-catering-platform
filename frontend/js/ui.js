// Small DOM helpers. Text goes through textContent, so caterer data can't inject HTML.
export function h(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name.startsWith("on")) element.addEventListener(name.slice(2), value);
    else if (name in element) element[name] = value;
    else if (value !== undefined) element.setAttribute(name, value);
  }
  element.append(...children.flat().filter((child) => child !== null && child !== undefined));
  return element;
}

let fieldCount = 0;

export function field(label, control, hint) {
  control.id ||= `field-${++fieldCount}`;
  return h("div", { className: "field" },
    h("label", { htmlFor: control.id }, label),
    control,
    hint ? h("small", {}, hint) : null);
}

export function select(options, value) {
  const control = h("select", {},
    options.map(([optionValue, label]) => h("option", { value: optionValue }, label)));
  control.value = value ?? options[0][0];
  return control;
}

export function notify(message, isError = false) {
  const box = document.getElementById("notice");
  box.textContent = message;
  box.className = isError ? "notice error" : "notice";
  box.hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => { box.hidden = true; }, 6000);
}

// Runs an action and shows the backend's Hebrew error instead of failing silently.
export async function attempt(action, successMessage) {
  try {
    const result = await action();
    if (successMessage) notify(successMessage);
    return result ?? true;
  } catch (error) {
    notify(error.message, true);
    return null;
  }
}

export function openDialog(title, content, onSubmit, submitLabel = "שמירה") {
  const form = h("form", { method: "dialog" },
    h("h2", {}, title),
    content,
    h("div", { className: "actions" },
      h("button", { type: "button", className: "secondary", onclick: () => dialog.close() }, "ביטול"),
      h("button", { type: "submit" }, submitLabel)));
  const dialog = h("dialog", {}, form);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (await attempt(onSubmit)) dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

export function confirmDelete(name, onConfirm) {
  openDialog("מחיקה", h("p", {}, `למחוק את "${name}"?`), onConfirm, "מחיקה");
}

export const numberOrNull = (value) => (value === "" ? null : Number(value));
export const textOrNull = (value) => value.trim() || null;

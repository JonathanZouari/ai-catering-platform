// Create and edit dialogs for the editable tables. Success is reported only after the
// database returns the saved row. There is no delete anywhere in this interface.
import { clear, errorBlock, h, ident, showToast } from "./dom.js";
import { replaceDishImage } from "./dish-images.js";
import {
  DIETARY_FIELDS,
  DISH_BUCKET,
  DISH_FIELDS,
  SIGNED_URL_SECONDS,
  allergenUpserts,
  buildPatch,
  describeError,
  dietaryToFields,
  dishToFields,
  escapeLike,
  sniffImageType,
  toInputValue,
  validateColumns,
  validateDietary,
  validateDishForm,
  validateImageFile,
  validateTableRules,
} from "./helpers.js";
import { ALLERGEN_STATUSES, formColumns, getTable, labelSelect, primaryKey, selectList } from "./schema.js";

const PICKER_LIMIT = 50;

/* ---------- foreign key picker ---------- */

function foreignKeyPicker({ client, column, value, inputId, describedBy, isAlive }) {
  const target = getTable(column.fk.table);
  const select = h("select", {
    class: "input",
    id: inputId,
    "aria-describedby": describedBy,
    onchange: () => {
      const option = select.selectedOptions[0];
      selected = select.value ? { id: select.value, label: option.dataset.label ?? null } : null;
    },
  });
  const status = h("p", { class: "hint", "aria-live": "polite" });
  let selected = value === "" ? null : { id: value, label: null };
  let requestId = 0;
  let timer;

  const optionText = (row) => (row.label ? `${row.label} (רשומה ${row.id})` : `רשומה ${row.id}`);

  function fill(rows) {
    clear(select);
    select.append(h("option", { value: "" }, column.nullable ? "ללא קישור" : "יש לבחור"));
    const known = new Set();
    for (const row of rows) {
      known.add(String(row.id));
      select.append(h("option", { value: String(row.id), "data-label": row.label }, optionText(row)));
    }
    // The saved choice stays available even when it falls outside the search results.
    if (selected && !known.has(String(selected.id))) {
      select.append(h("option", { value: String(selected.id), "data-label": selected.label }, optionText(selected)));
    }
    select.value = selected ? String(selected.id) : "";
  }

  async function search(term) {
    const mine = ++requestId;
    status.textContent = "טוען רשימה…";
    let query = client.from(target.name).select(labelSelect(target)).order(target.labelColumn).limit(PICKER_LIMIT);
    if (term) query = query.ilike(target.labelColumn, `%${escapeLike(term)}%`);
    const { data, error } = await query;
    if (mine !== requestId || !isAlive()) return;
    if (error) {
      status.textContent = `${describeError(error).message} הרשימה לא נטענה.`;
      return;
    }
    fill(data);
    status.textContent = data.length === 0
      ? "לא נמצאו תוצאות."
      : data.length === PICKER_LIMIT
        ? `מוצגות ${PICKER_LIMIT} התוצאות הראשונות. אפשר לצמצם בעזרת חיפוש.`
        : `נמצאו ${data.length} תוצאות.`;
  }

  async function resolveSelected() {
    if (!selected) return;
    const { data } = await client.from(target.name).select(labelSelect(target)).eq("id", selected.id).maybeSingle();
    if (!data || !isAlive() || String(selected?.id) !== String(data.id)) return;
    selected = data;
    const option = select.selectedOptions[0];
    option.textContent = optionText(data);
    option.dataset.label = data.label;
  }

  const searchInput = h("input", {
    class: "input",
    type: "search",
    placeholder: `חיפוש ב${target.label}`,
    "aria-label": `חיפוש ב${target.label}`,
    oninput: (event) => {
      clearTimeout(timer);
      timer = setTimeout(() => search(event.target.value.trim()), 300);
    },
  });

  fill([]);
  search("").then(resolveSelected);

  return {
    element: h(
      "div",
      { class: "fk-picker" },
      h("p", { class: "hint" }, `קישור לטבלה ${target.label}. יש לחפש ולבחור רשומה מהרשימה.`),
      searchInput,
      select,
      status,
    ),
    control: select,
  };
}

/* ---------- field rendering ---------- */

function fieldControl(column, value, id, describedBy) {
  const common = { id, class: "input", "aria-describedby": describedBy };
  switch (column.type) {
    case "bool":
      return h("input", { id, type: "checkbox", class: "checkbox", checked: value === true, "aria-describedby": describedBy });
    case "enum":
      return h(
        "select",
        common,
        !column.noEmptyOption && h("option", { value: "" }, column.emptyLabel ?? "יש לבחור"),
        Object.entries(column.options).map(([key, label]) => h("option", { value: key, selected: key === value }, label)),
      );
    case "longtext":
      return h("textarea", { ...common, value, rows: 3 });
    case "email":
      return h("input", { ...common, type: "email", dir: "ltr", value, autocomplete: "off" });
    case "phone":
      return h("input", { ...common, type: "tel", dir: "ltr", value, autocomplete: "off" });
    case "date":
      return h("input", { ...common, type: "date", value });
    case "int":
      return h("input", { ...common, inputmode: "numeric", dir: "ltr", value });
    case "money":
    case "milli":
      return h("input", { ...common, inputmode: "decimal", dir: "ltr", value });
    default:
      return h("input", { ...common, type: "text", dir: column.identifier ? "ltr" : "auto", value });
  }
}

function renderField({ client, column, value, isAlive, locked }) {
  const inputId = `field-${column.name}`;
  const errorId = `${inputId}-error`;
  const hintId = column.hint ? `${inputId}-hint` : null;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ");
  const error = h("p", { class: "error", id: errorId, hidden: true });

  let body;
  let control;
  if (column.type === "fk") {
    const picker = foreignKeyPicker({ client, column, value, inputId, describedBy, isAlive });
    body = picker.element;
    control = picker.control;
  } else {
    control = fieldControl(column, value, inputId, describedBy);
    body = control;
  }
  if (locked) control.disabled = true;

  const suffix = column.type === "money" ? "בשקלים" : null;
  const required = !column.nullable && column.type !== "bool";
  const wrapper = h(
    "div",
    { class: `field${column.type === "bool" ? " field-check" : ""}${column.type === "longtext" ? " field-wide" : ""}` },
    column.type === "bool" && body,
    h("label", { for: inputId }, column.label, suffix && ` (${suffix})`, required && h("span", { class: "required" }, " (חובה)")),
    column.type !== "bool" && body,
    column.hint && h("p", { class: "hint", id: hintId }, column.hint),
    error,
  );

  return {
    wrapper,
    control,
    read: () => (column.type === "bool" ? control.checked : control.value),
    setError(message) {
      wrapper.classList.toggle("invalid", Boolean(message));
      error.textContent = message ?? "";
      error.hidden = !message;
      if (message) control.setAttribute("aria-invalid", "true");
      else control.removeAttribute("aria-invalid");
    },
  };
}

/* ---------- dish dietary and allergen fields ---------- */

// Only the owner can read or write these tables. Anything that cannot be loaded stays out of the
// form and out of the save, so a failed read can never be saved over real data as unknown.
function dishSafetySection({ client, row, isAlive }) {
  const body = h("div", { "aria-live": "polite" }, h("p", { class: "muted" }, "טוען מידע תזונתי ואלרגנים…"));
  let saved = null;
  let dietaryFields = null;
  let allergenFields = null;

  const readDietary = () => Object.fromEntries([...dietaryFields].map(([name, field]) => [name, field.read()]));
  const readAllergens = () => Object.fromEntries([...allergenFields].map(([allergenId, field]) => [allergenId, field.read()]));
  const snapshot = () => (saved ? JSON.stringify([readDietary(), readAllergens()]) : "");
  let initial = "";

  async function load() {
    const [allergens, dietary, statuses] = await Promise.all([
      client.from("allergens").select("id,name").order("id"),
      row ? client.from("dish_dietary").select("kashrut_class,is_vegetarian,is_vegan").eq("dish_id", row.id).maybeSingle() : { data: null },
      row ? client.from("dish_allergens").select("allergen_id,status").eq("dish_id", row.id) : { data: [] },
    ]);
    if (!isAlive()) return;
    const error = allergens.error ?? dietary.error ?? statuses.error;
    if (error || (allergens.data ?? []).length === 0) {
      clear(body).append(h("p", { class: "notice" }, "מידע תזונתי ואלרגנים נערך בידי הבעלים בלבד. המידע לא נטען, והשמירה לא תשנה אותו."));
      return;
    }
    saved = {
      dietary: dietary.data,
      statuses: Object.fromEntries((statuses.data ?? []).map((item) => [String(item.allergen_id), item.status])),
    };
    const fields = dietaryToFields(dietary.data);
    dietaryFields = new Map(DIETARY_FIELDS.map((column) => [column.name, renderField({ client, column, value: fields[column.name], isAlive })]));
    allergenFields = new Map(allergens.data.map((allergen) => {
      const column = { name: `allergen-${allergen.id}`, label: allergen.name, type: "enum", options: ALLERGEN_STATUSES, noEmptyOption: true };
      return [String(allergen.id), renderField({ client, column, value: saved.statuses[String(allergen.id)] ?? "unknown", isAlive })];
    }));
    clear(body).append(
      h("p", { class: "hint" }, "״לא ידוע״ לעולם אינו מוצג ללקוח כבטוח."),
      h("div", { class: "form-grid" }, [...dietaryFields.values(), ...allergenFields.values()].map((field) => field.wrapper)),
    );
    initial = snapshot();
  }

  load().catch(() => {
    if (isAlive()) clear(body).append(h("p", { class: "notice" }, "לא ניתן לטעון מידע תזונתי ואלרגנים. השמירה לא תשנה אותו."));
  });

  return {
    wrapper: h("section", { class: "field field-wide" }, h("h3", {}, "מידע תזונתי ואלרגנים"), body),
    isDirty: () => snapshot() !== initial,
    validate() {
      if (!saved) return true;
      const { errors } = validateDietary(readDietary());
      for (const [name, field] of dietaryFields) field.setError(errors[name]);
      return Object.keys(errors).length === 0;
    },
    // Each table is marked saved as it succeeds, so a retry after a failure sends only what is left.
    async save(dishId) {
      if (!saved) return { changed: false };
      let changed = false;
      const { values } = validateDietary(readDietary());
      if (Object.keys(buildPatch(saved.dietary ?? {}, values)).length > 0) {
        const written = await client.from("dish_dietary").upsert({ dish_id: dishId, ...values }, { onConflict: "dish_id" });
        if (written.error) return { changed, error: written.error };
        saved.dietary = values;
        changed = true;
      }
      const chosen = readAllergens();
      const rows = allergenUpserts(dishId, saved.statuses, chosen);
      if (rows.length > 0) {
        const written = await client.from("dish_allergens").upsert(rows, { onConflict: "dish_id,allergen_id" });
        if (written.error) return { changed, error: written.error };
        saved.statuses = chosen;
        changed = true;
      }
      return { changed };
    },
  };
}

/* ---------- dish image field ---------- */

function dishImageField({ client, row, isAlive }) {
  const preview = h("div", { class: "image-preview" });
  const message = h("div", { "aria-live": "polite" });
  let selection = null;
  let objectUrl = null;

  const input = h("input", {
    id: "field-image",
    class: "input",
    type: "file",
    accept: ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp",
    onchange: onSelect,
  });
  const clearButton = h("button", { class: "btn btn-ghost", type: "button", hidden: true, onclick: () => { reset(); showCurrent(); } }, "ביטול הבחירה");

  function releasePreview() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }

  function reset() {
    releasePreview();
    selection = null;
    input.value = "";
    clearButton.hidden = true;
    clear(message);
  }

  async function showCurrent() {
    const currentPath = row?.image_path;
    clear(preview);
    if (!currentPath) {
      preview.append(h("p", { class: "muted" }, "אין תמונה שמורה."));
      return;
    }
    preview.append(h("p", { class: "muted" }, "טוען את התמונה הנוכחית…"));
    const { data, error } = await client.storage.from(DISH_BUCKET).createSignedUrl(currentPath, SIGNED_URL_SECONDS);
    if (!isAlive() || selection) return;
    clear(preview);
    if (error) {
      preview.append(errorBlock({ message: "לא ניתן להציג את התמונה הנוכחית. הקובץ לא נמחק.", detail: describeError(error).detail }));
      return;
    }
    preview.append(h("img", { src: data.signedUrl, alt: "התמונה הנוכחית של המנה", loading: "lazy" }), h("p", { class: "hint" }, "התמונה הנוכחית"));
  }

  async function onSelect() {
    const file = input.files?.[0];
    if (!file) return;
    releasePreview();
    selection = null;
    clear(message);
    const info = validateImageFile(file);
    const declared = info.error ? null : sniffImageType(new Uint8Array(await file.slice(0, 12).arrayBuffer()));
    if (info.error || declared !== info.contentType) {
      input.value = "";
      message.append(errorBlock({ message: info.error ?? "תוכן הקובץ אינו תואם את סוג התמונה שלו." }));
      showCurrent();
      return;
    }
    selection = { file, info };
    objectUrl = URL.createObjectURL(file);
    clearButton.hidden = false;
    clear(preview).append(
      h("img", { src: objectUrl, alt: "תצוגה מקדימה של התמונה שנבחרה" }),
      h("p", { class: "hint" }, "תצוגה מקדימה. הקובץ יועלה רק בלחיצה על שמירה."),
    );
  }

  showCurrent();

  return {
    wrapper: h(
      "div",
      { class: "field field-wide" },
      h("label", { for: "field-image" }, "תמונת המנה"),
      input,
      h("p", { class: "hint" }, "עד 5 מגה־בייט, בתבניות:"),
      ident("jpg, png, webp"),
      clearButton,
      message,
      preview,
    ),
    getSelection: () => selection,
    dispose: releasePreview,
  };
}

/* ---------- dialog ---------- */

// isSessionAlive turns false on signout, so a late response can never touch a closed session.
export function openRowForm({ client, table, row, isSessionAlive, onSaved, registerDialog }) {
  const isDish = table.name === "dishes";
  const fields = isDish ? DISH_FIELDS : formColumns(table);
  const initial = isDish
    ? dishToFields(row)
    : Object.fromEntries(fields.map((column) => [column.name, toInputValue(column, row?.[column.name])]));

  let original = row ?? null;
  let open = true;
  let saving = false;
  let warnedDirty = false;
  const isAlive = () => open && isSessionAlive();

  const rendered = new Map();
  for (const column of fields) {
    rendered.set(column.name, renderField({
      client,
      column,
      value: initial[column.name],
      isAlive,
      locked: isDish && column.name === "legacy_code" && Boolean(row),
    }));
  }
  const safety = isDish ? dishSafetySection({ client, row, isAlive }) : null;
  const image = isDish ? dishImageField({ client, row, isAlive }) : null;

  const formMessage = h("div", { class: "form-message" });
  const saveButton = h("button", { class: "btn btn-primary", type: "submit" }, "שמירה");
  const cancelButton = h("button", { class: "btn btn-secondary", type: "button", onclick: () => requestClose() }, "ביטול");
  const titleId = "row-form-title";
  const form = h(
    "form",
    { novalidate: true, onsubmit: onSubmit },
    h("div", { class: "form-grid" }, [...rendered.values()].map((field) => field.wrapper), safety?.wrapper, image?.wrapper),
    formMessage,
    h("div", { class: "form-actions" }, saveButton, cancelButton),
  );
  const heading = h("h2", { id: titleId }, `${row ? "עריכת רשומה" : "רשומה חדשה"}: ${table.label}`);
  const dialog = h(
    "dialog",
    {
      class: "row-dialog",
      "aria-labelledby": titleId,
      oncancel: (event) => {
        event.preventDefault();
        requestClose();
      },
    },
    h("header", { class: "dialog-head" }, heading, ident(table.name), row && h("p", { class: "muted" }, `רשומה ${row[primaryKey(table)[0]]}`)),
    form,
  );

  const readRaw = () => Object.fromEntries([...rendered].map(([name, field]) => [name, field.read()]));
  const initialRaw = JSON.stringify(readRaw());

  function isDirty() {
    return JSON.stringify(readRaw()) !== initialRaw || Boolean(image?.getSelection()) || Boolean(safety?.isDirty());
  }

  function close() {
    open = false;
    image?.dispose();
    dialog.close();
    dialog.remove();
    registerDialog(null);
  }

  function requestClose() {
    if (saving) return;
    if (isDirty() && !warnedDirty) {
      warnedDirty = true;
      clear(formMessage).append(h("div", { class: "notice notice-warning", role: "alert" }, "יש שינויים שלא נשמרו. לחיצה נוספת על ביטול תסגור בלי לשמור."));
      return;
    }
    close();
  }

  function showFieldErrors(errors) {
    let firstInvalid = null;
    for (const [name, field] of rendered) {
      field.setError(errors[name]);
      if (errors[name] && !firstInvalid) firstInvalid = field.control;
    }
    firstInvalid?.focus();
    return firstInvalid !== null;
  }

  function setSaving(value) {
    saving = value;
    saveButton.disabled = value;
    cancelButton.disabled = value;
    saveButton.textContent = value ? "שומר…" : "שמירה";
  }

  async function writeRow(values) {
    const select = selectList(table);
    if (!original) return client.from(table.name).insert(values).select(select).single();
    const patch = buildPatch(original, values);
    if (Object.keys(patch).length === 0) return { data: original, unchanged: true };
    const key = primaryKey(table)[0];
    let query = client.from(table.name).update(patch).eq(key, original[key]);
    // Refuses to overwrite a change another staff member saved after this form opened.
    if (original.updated_at) query = query.eq("updated_at", original.updated_at);
    return query.select(select).single();
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (saving) return;
    warnedDirty = false;
    clear(formMessage);

    let values;
    if (isDish) {
      const result = validateDishForm(readRaw(), original);
      const invalid = showFieldErrors(result.errors);
      if (!safety.validate() || invalid) return;
      values = result.row;
    } else {
      const result = validateColumns(fields, readRaw());
      validateTableRules(table.name, result.values, result.errors);
      if (showFieldErrors(result.errors)) return;
      values = result.values;
    }

    setSaving(true);
    try {
      const written = await writeRow(values);
      if (!isAlive()) return;
      if (written.error) {
        formMessage.append(errorBlock(describeError(written.error)));
        return;
      }
      const wasNew = !original;
      original = written.data;
      // From here the row exists, so a retry after a later failure must update it, not insert again.
      if (wasNew && isDish) rendered.get("legacy_code").control.disabled = true;

      const safetySaved = safety ? await safety.save(original.id) : { changed: false };
      if (!isAlive()) return;
      if (safetySaved.error) {
        onSaved();
        const description = describeError(safetySaved.error);
        const saved = written.unchanged ? "" : "פרטי המנה נשמרו. ";
        formMessage.append(errorBlock({
          message: `${saved}המידע התזונתי או מידע האלרגנים לא נשמר במלואו. ${description.message}`,
          detail: description.detail,
        }));
        return;
      }

      const selection = image?.getSelection();
      if (selection) {
        const result = await replaceDishImage({
          client,
          dishId: original.id,
          dishCode: original.legacy_code,
          oldPath: original.image_path,
          file: selection.file,
          info: selection.info,
          uuid: crypto.randomUUID(),
        });
        if (!isAlive()) return;
        if (!result.ok) {
          onSaved();
          const description = describeError(result.error);
          const saved = written.unchanged && !safetySaved.changed ? "" : "פרטי המנה נשמרו. ";
          const outcome = result.stage === "upload"
            ? "התמונה לא הוחלפה, והתמונה הקודמת נשארה במקומה."
            : "לא התקבל אישור לקישור התמונה, וייתכן שהיא כבר נשמרה. הקובץ שהועלה לא נמחק. יש לטעון מחדש את הרשימה ולבדוק את המנה לפני ניסיון נוסף.";
          formMessage.append(errorBlock({
            message: `${saved}${outcome} ${description.message}`,
            detail: description.detail,
          }));
          return;
        }
        close();
        onSaved();
        showToast("המנה והתמונה נשמרו.");
        return;
      }

      if (written.unchanged && !safetySaved.changed) {
        formMessage.append(h("div", { class: "notice", role: "status" }, "לא בוצעו שינויים, לכן לא נשלח דבר לענן."));
        return;
      }
      close();
      onSaved();
      showToast("הרשומה נשמרה.");
    } catch (error) {
      if (isAlive()) formMessage.append(errorBlock(describeError(error)));
    } finally {
      if (open) setSaving(false);
    }
  }

  document.body.append(dialog);
  registerDialog({ close });
  dialog.showModal();
}

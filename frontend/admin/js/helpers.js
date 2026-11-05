// Pure helpers with no DOM or network access, covered by tests/helpers.test.mjs.
import { DISH_KASHRUT, DISH_UNITS } from "./schema.js";

export const STAFF_ROLES = ["catering_owner"];
export const ROLE_LABELS = { catering_owner: "בעלים", catering_manager: "מנהל" };
export const PAGE_SIZES = [25, 50, 100];

/* ---------- authorization ---------- */

// Only app_metadata counts: user_metadata is editable by the user and must never grant access.
export function staffRoleOf(user) {
  const role = user?.app_metadata?.role;
  return STAFF_ROLES.includes(role) ? role : null;
}

export function decodeJwtPayload(token) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = part.padEnd(part.length + ((4 - (part.length % 4)) % 4), "=");
    const bytes = Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

// Row security reads the role from the token, which can lag behind the server's user record.
// This only decides whether a token refresh is needed, never whether access is granted.
export function tokenHasStaffRole(accessToken) {
  return staffRoleOf(decodeJwtPayload(accessToken ?? "")) !== null;
}

export function parseCloudConfig(body) {
  const url = typeof body?.url === "string" ? body.url : "";
  const key = typeof body?.publishableKey === "string" ? body.publishableKey : "";
  if (body?.configured !== true || !url.startsWith("https://") || !key.startsWith("sb_publishable_")) return { configured: false };
  return { configured: true, url, publishableKey: key };
}

/* ---------- pagination and stale responses ---------- */

export function pageRange(page, pageSize) {
  const from = page * pageSize;
  return { from, to: from + pageSize - 1 };
}

export function pageInfo(count, page, pageSize) {
  const total = Number.isInteger(count) ? count : 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : page * pageSize + 1;
  const last = Math.min(total, (page + 1) * pageSize);
  return { total, totalPages, first, last, hasPrev: page > 0, hasNext: page + 1 < totalPages };
}

export function createRequestGuard() {
  let current = 0;
  return {
    next: () => ++current,
    isCurrent: (token) => token === current,
    invalidate: () => void ++current,
  };
}

/* ---------- value parsing ---------- */

// Scales a decimal string to an integer without binary floating point, so 19.99 is exactly 1999.
function parseScaled(text, decimals) {
  const match = /^(\d+)(?:\.(\d*))?$/.exec(text);
  if (!match) return null;
  const fraction = match[2] ?? "";
  if (fraction.length > decimals) return null;
  const scaled = Number(match[1] + fraction.padEnd(decimals, "0"));
  return Number.isSafeInteger(scaled) ? scaled : null;
}

function scaledToText(value, decimals) {
  if (value === null || value === undefined) return "";
  const digits = String(value).padStart(decimals + 1, "0");
  const whole = digits.slice(0, -decimals);
  const fraction = digits.slice(-decimals).replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : whole;
}

export const parseMoneyToMinor = (text) => parseScaled(text.trim(), 2);
export const minorToInput = (minor) => scaledToText(minor, 2);
export const parseMilli = (text) => parseScaled(text.trim(), 3);
export const milliToInput = (milli) => scaledToText(milli, 3);

function isRealDate(text) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return false;
  const date = new Date(`${text}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === text;
}

// Turns a stored value into what the matching form control displays.
export function toInputValue(column, value) {
  if (column.type === "bool") return value === undefined || value === null ? column.defaultValue === true : value;
  if (value === null || value === undefined) return "";
  if (column.type === "money") return minorToInput(value);
  if (column.type === "milli") return milliToInput(value);
  return String(value);
}

// Validates one column against the type and constraints in the migration.
// Returns { value } on success or { error } with a Hebrew message.
export function validateColumn(column, raw) {
  if (column.type === "bool") return { value: raw === true };
  const text = typeof raw === "string" ? raw.trim() : "";
  if (text === "") {
    return column.nullable ? { value: null } : { error: "שדה חובה." };
  }
  switch (column.type) {
    case "email":
      return /^[^\s@]+@[^\s@]+$/.test(text) ? { value: text } : { error: "כתובת דוא״ל לא תקינה." };
    case "phone":
      return /^\+?[\d\s()-]{6,}$/.test(text) ? { value: text } : { error: "מספר טלפון לא תקין." };
    case "date":
      return isRealDate(text) ? { value: text } : { error: "תאריך לא תקין." };
    case "enum":
      return Object.hasOwn(column.options, text) ? { value: text } : { error: "יש לבחור ערך מהרשימה." };
    case "int":
    case "fk": {
      if (!/^\d+$/.test(text)) return { error: "יש להזין מספר שלם, אפס או גדול ממנו." };
      const value = Number(text);
      return Number.isSafeInteger(value) ? { value } : { error: "המספר גדול מדי." };
    }
    case "money": {
      const value = parseMoneyToMinor(text);
      return value === null ? { error: "יש להזין סכום בשקלים, עד שתי ספרות אחרי הנקודה." } : { value };
    }
    case "milli": {
      const value = parseMilli(text);
      if (value === null) return { error: "יש להזין מספר, עד שלוש ספרות אחרי הנקודה." };
      return value > 0 ? { value } : { error: "יש להזין מספר גדול מאפס." };
    }
    default:
      return { value: text };
  }
}

export function validateColumns(columns, rawValues) {
  const values = {};
  const errors = {};
  for (const column of columns) {
    const result = validateColumn(column, rawValues[column.name]);
    if (result.error) errors[column.name] = result.error;
    else values[column.name] = result.value;
  }
  return { values, errors };
}

// Table rules that span columns, mirroring the migration's check constraints.
export function validateTableRules(tableName, values, errors) {
  if (tableName === "customers" && !values.email && !values.phone && !errors.email && !errors.phone) {
    errors.phone = "ללקוח חייב להיות דוא״ל או טלפון.";
  }
  return errors;
}

export function buildPatch(original, values) {
  const patch = {};
  for (const [key, value] of Object.entries(values)) {
    if (JSON.stringify(original?.[key] ?? null) !== JSON.stringify(value)) patch[key] = value;
  }
  return patch;
}

export function escapeLike(text) {
  return text.replace(/[\\%_]/g, "\\$&");
}

/* ---------- dishes ---------- */

const YES_NO_UNKNOWN = { yes: "כן", no: "לא" };

export const DISH_FIELDS = [
  { name: "legacy_code", label: "קוד מנה", type: "text", identifier: true, hint: "אותיות לועזיות, ספרות, מקף וקו תחתון. לא ניתן לשינוי לאחר היצירה." },
  { name: "name", label: "שם המנה", type: "text" },
  { name: "description", label: "תיאור", type: "longtext", nullable: true },
  { name: "category_id", label: "קטגוריה", type: "fk", fk: { table: "dish_categories", column: "id" } },
  { name: "pricing_unit", label: "יחידת מכירה", type: "enum", options: DISH_UNITS },
  { name: "price_minor", label: "מחיר ליחידה", type: "money" },
  { name: "step_milli", label: "צעד כמות", type: "milli", hint: "לדוגמה: 0.5 לחצי קילו, 1 ליחידה אחת." },
  { name: "per_guest", label: "כמות לכל אורח", type: "text", nullable: true, hint: "לא חובה. מספר גדול מאפס." },
  { name: "is_available", label: "זמינה להזמנה", type: "bool" },
];

// An empty choice here means "not provided", which is stored as NULL and shown as unknown.
export const DIETARY_FIELDS = [
  { name: "kashrut_class", label: "כשרות", type: "enum", nullable: true, options: DISH_KASHRUT, emptyLabel: "לא ידוע" },
  { name: "is_vegetarian", label: "צמחונית", type: "enum", nullable: true, options: YES_NO_UNKNOWN, emptyLabel: "לא ידוע" },
  { name: "is_vegan", label: "טבעונית", type: "enum", nullable: true, options: YES_NO_UNKNOWN, emptyLabel: "לא ידוע" },
];

export function isSafeDishCode(code) {
  return typeof code === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(code);
}

export function dishToFields(row) {
  return {
    legacy_code: row?.legacy_code ?? "",
    name: row?.name ?? "",
    description: row?.description ?? "",
    category_id: row ? String(row.category_id) : "",
    pricing_unit: row?.pricing_unit ?? "",
    price_minor: row ? minorToInput(row.price_minor) : "",
    step_milli: row ? milliToInput(row.step_milli) : "1",
    per_guest: row?.per_guest === undefined || row?.per_guest === null ? "" : String(row.per_guest),
    is_available: row ? row.is_available : true,
  };
}

// Validates the dish form and returns the dishes columns to write. The code is set only on creation.
export function validateDishForm(raw, original) {
  const fields = original ? DISH_FIELDS.filter((field) => field.name !== "legacy_code") : DISH_FIELDS;
  const { values, errors } = validateColumns(fields, raw);

  if (!original && values.legacy_code !== undefined && !isSafeDishCode(values.legacy_code)) {
    errors.legacy_code = "מותרות אותיות לועזיות, ספרות, מקף וקו תחתון בלבד.";
  }
  if (values.per_guest) {
    values.per_guest = Number(values.per_guest);
    if (!Number.isFinite(values.per_guest) || values.per_guest <= 0) errors.per_guest = "יש להזין מספר גדול מאפס.";
  }
  if (Object.keys(errors).length > 0) return { errors };
  return { errors: {}, row: values };
}

const toYesNo = (value) => (value === true ? "yes" : value === false ? "no" : "");
const fromYesNo = (value) => (value === "yes" ? true : value === "no" ? false : null);

export function dietaryToFields(dietary) {
  return {
    kashrut_class: dietary?.kashrut_class ?? "",
    is_vegetarian: toYesNo(dietary?.is_vegetarian),
    is_vegan: toYesNo(dietary?.is_vegan),
  };
}

// Unknown stays NULL: a blank choice must never be saved as "no".
export function validateDietary(raw) {
  const { values, errors } = validateColumns(DIETARY_FIELDS, raw);
  if (Object.keys(errors).length > 0) return { errors };
  if (values.is_vegan === "yes" && values.is_vegetarian === "no") {
    return { errors: { is_vegetarian: "מנה טבעונית היא גם צמחונית." } };
  }
  return {
    errors: {},
    values: {
      kashrut_class: values.kashrut_class,
      is_vegetarian: fromYesNo(values.is_vegetarian),
      is_vegan: fromYesNo(values.is_vegan),
    },
  };
}

// The rows to upsert after an edit. A missing row already means unknown, so choosing unknown for an
// allergen with no row writes nothing, and only a changed status is sent.
export function allergenUpserts(dishId, savedStatuses, chosenStatuses) {
  const rows = [];
  for (const [allergenId, status] of Object.entries(chosenStatuses)) {
    if ((savedStatuses[allergenId] ?? "unknown") !== status) {
      rows.push({ dish_id: dishId, allergen_id: Number(allergenId), status });
    }
  }
  return rows;
}

/* ---------- dish images ---------- */

export const DISH_BUCKET = "dish-images";
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const SIGNED_URL_SECONDS = 3600;

const IMAGE_TYPES = {
  "image/jpeg": { extension: "jpg", accepted: ["jpg", "jpeg"] },
  "image/png": { extension: "png", accepted: ["png"] },
  "image/webp": { extension: "webp", accepted: ["webp"] },
};

export function validateImageFile({ name, type, size }) {
  const info = IMAGE_TYPES[type];
  const extension = String(name ?? "").split(".").pop().toLowerCase();
  if (!info || !info.accepted.includes(extension)) return { error: "אפשר להעלות רק תמונה בתבנית שמופיעה ברשימה שמתחת לשדה." };
  if (size <= 0) return { error: "הקובץ ריק." };
  if (size > MAX_IMAGE_BYTES) return { error: "הקובץ גדול מדי. הגודל המרבי הוא 5 מגה־בייט." };
  return { extension: info.extension, contentType: type };
}

// Compares the file's first bytes with its declared type, so a renamed file is rejected.
export function sniffImageType(bytes) {
  const matches = (signature, offset = 0) => signature.every((byte, index) => bytes[offset + index] === byte);
  if (matches([0xff, 0xd8, 0xff])) return "image/jpeg";
  if (matches([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) return "image/png";
  if (matches([0x52, 0x49, 0x46, 0x46]) && matches([0x57, 0x45, 0x42, 0x50], 8)) return "image/webp";
  return null;
}

// The folder is the dish code, not its numeric key: existing objects and the storage policies use it.
export function buildDishImagePath(dishCode, extension, uuid) {
  if (!isSafeDishCode(dishCode)) throw new Error("unsafe dish code");
  return `dishes/${dishCode}/${uuid}.${extension}`;
}

/* ---------- display ---------- */

const timeFormat = new Intl.DateTimeFormat("he-IL", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Jerusalem" });

export function formatMoney(minor, currency = "ILS") {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency }).format(minor / 100);
  } catch {
    return `${minor / 100} ${currency}`;
  }
}

export function formatDate(text) {
  const [year, month, day] = String(text).split("-");
  return day ? `${day}/${month}/${year}` : String(text);
}

export function formatCell(column, value, row) {
  if (value === null || value === undefined) return "—";
  switch (column.type) {
    case "money": return formatMoney(value, row?.currency ?? "ILS");
    case "milli": return milliToInput(value);
    case "bool": return value ? "כן" : "לא";
    case "date": return formatDate(value);
    case "timestamp": {
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? String(value) : timeFormat.format(date);
    }
    case "enum": return column.options[value] ?? String(value);
    case "jsonb": return JSON.stringify(value);
    default:
      return column.masked ? `${String(value).slice(0, 10)}…` : String(value);
  }
}

// Indented document text for display. A text column holds JSON as a string and is parsed first.
export function jsonCellText(column, value) {
  if (column.type !== "jsontext") return JSON.stringify(value, null, 2);
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return String(value);
  }
}

// True for machine values that must render left to right on their own line.
export function isLtrCell(column) {
  return column.type === "jsonb" || column.type === "jsontext" || column.masked === true || column.name === "image_path" || column.name === "currency";
}

/* ---------- errors ---------- */

const KNOWN_ERRORS = {
  23505: "כבר קיימת רשומה עם אותו ערך ייחודי.",
  23503: "הפעולה נחסמה כי היא סותרת קשר לרשומה אחרת.",
  23514: "הערכים אינם עומדים בכללי המסד.",
  23502: "חסר ערך בשדה חובה.",
  42501: "אין לחשבון הרשאה לפעולה הזו.",
  "42P01": "הטבלה עדיין לא קיימת במסד הענן.",
  42703: "מבנה הטבלה במסד אינו תואם את המסך. ייתכן שחסר עדכון מבנה.",
  PGRST116: "לא עודכנה אף רשומה. ייתכן שהרשומה השתנתה בינתיים, נמחקה או שאין הרשאה.",
  PGRST204: "מבנה הטבלה במסד אינו תואם את המסך. ייתכן שחסר עדכון מבנה.",
  PGRST205: "הטבלה אינה זמינה בממשק הענן.",
  PGRST301: "תוקף ההתחברות פג. יש להתחבר מחדש.",
  PGRST303: "תוקף ההתחברות פג. יש להתחבר מחדש.",
  invalid_credentials: "הדוא״ל או הסיסמה שגויים.",
  email_not_confirmed: "כתובת הדוא״ל של החשבון טרם אומתה.",
  over_request_rate_limit: "בוצעו יותר מדי ניסיונות. יש להמתין ולנסות שוב.",
  user_banned: "החשבון חסום.",
};

// Returns a Hebrew explanation plus the untranslated detail, which is shown on its own LTR line.
export function describeError(error) {
  const detail = [error?.code, error?.message].filter(Boolean).join(": ");
  const known = KNOWN_ERRORS[error?.code];
  if (known) return { message: known, detail };

  const status = Number(error?.statusCode ?? error?.status);
  const text = String(error?.message ?? "");
  if (/failed to fetch|networkerror|load failed|fetch failed/i.test(text) || error?.name === "AuthRetryableFetchError") {
    return { message: "אין תקשורת עם הענן. הפעולה לא הושלמה.", detail };
  }
  if (status === 401 || status === 403) return { message: "אין הרשאה לפעולה הזו.", detail };
  if (status === 404) return { message: "המשאב המבוקש לא נמצא בענן.", detail };
  if (status === 409) return { message: "כבר קיים קובץ באותו נתיב.", detail };
  if (status === 413) return { message: "הקובץ גדול מהמותר בענן.", detail };
  if (status === 429) return { message: "בוצעו יותר מדי בקשות. יש להמתין ולנסות שוב.", detail };
  return { message: "הפעולה נכשלה.", detail };
}

export function isSessionInvalidError(error) {
  const status = Number(error?.status);
  return error?.name === "AuthSessionMissingError" || status === 401 || status === 403;
}

/* ---------- diagram geometry ---------- */

// Curved path between two boxes, leaving and entering through the facing edges.
export function edgePath(from, to) {
  if (from === to) {
    const x = from.x + from.width;
    const y = from.y + from.height / 2;
    return `M ${x} ${y - 12} C ${x + 42} ${y - 34}, ${x + 42} ${y + 34}, ${x} ${y + 12}`;
  }
  const fromCenter = { x: from.x + from.width / 2, y: from.y + from.height / 2 };
  const toCenter = { x: to.x + to.width / 2, y: to.y + to.height / 2 };
  const dx = toCenter.x - fromCenter.x;
  const dy = toCenter.y - fromCenter.y;
  if (Math.abs(dx) >= Math.abs(dy) * 1.2) {
    const direction = Math.sign(dx);
    const startX = fromCenter.x + (direction * from.width) / 2;
    const endX = toCenter.x - (direction * to.width) / 2;
    const bend = Math.max(36, Math.abs(endX - startX) / 2) * direction;
    return `M ${startX} ${fromCenter.y} C ${startX + bend} ${fromCenter.y}, ${endX - bend} ${toCenter.y}, ${endX} ${toCenter.y}`;
  }
  const direction = Math.sign(dy) || 1;
  const startY = fromCenter.y + (direction * from.height) / 2;
  const endY = toCenter.y - (direction * to.height) / 2;
  const bend = Math.max(24, Math.abs(endY - startY) / 2) * direction;
  return `M ${fromCenter.x} ${startY} C ${fromCenter.x} ${startY + bend}, ${toCenter.x} ${endY - bend}, ${toCenter.x} ${endY}`;
}

// Static description of the MVP application tables: the core baseline migration plus the catalog
// normalization migration. Structure and Hebrew labels only, never records.
// supabase/tests/mvp-postgres.mjs compares every column and FK to the migrated database.
import { FOUNDATION_GROUPS, FOUNDATION_TABLES, FOUNDATION_RELATIONS } from './schema-additions.js';

const id = { name: "id", label: "מספר רשומה", type: "id", pk: true };
const createdAt = { name: "created_at", label: "נוצר בתאריך", type: "timestamp", generated: true };
const updatedAt = { name: "updated_at", label: "עודכן בתאריך", type: "timestamp", generated: true };

const fk = (table, column = "id") => ({ table, column });

const nullable = true;
// Added to a baseline table by a later migration; the schema test checks that migration instead.
const addedByLaterMigration = true;
// NULL is a fact here: nobody provided the value, so it must never look like "no" or be left blank.
const UNKNOWN = "לא ידוע";

export const DISH_UNITS = { tray: "מגש", kg: "ק״ג", item: "יחידה", guest: "לאורח" };
export const DISH_KASHRUT = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };
export const ALLERGEN_STATUSES = { unknown: UNKNOWN, contains: "מכיל", free: "לא מכיל" };

export const GROUPS = [
  ...FOUNDATION_GROUPS,
  { id: "people", label: "לקוחות וכתובות" },
  { id: "orders", label: "אירועים והזמנות" },
  { id: "menu", label: "תפריט ואזורי משלוח" },
];

export const TABLES = [
  {
    name: "customers",
    label: "לקוחות",
    description: "פרטי הקשר של מי שמזמין. כל לקוח חייב דוא״ל או טלפון.",
    group: "people",
    editable: true,
    labelColumn: "full_name",
    columns: [
      id,
      { name: "full_name", label: "שם מלא", type: "text" },
      { name: "email", label: "דוא״ל", type: "email", nullable, unique: true },
      { name: "phone", label: "טלפון", type: "phone", nullable },
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "addresses",
    label: "כתובות",
    description: "כתובות למשלוח. כתובת יכולה להיות משויכת ללקוח.",
    group: "people",
    editable: true,
    labelColumn: "street",
    columns: [
      id,
      { name: "customer_id", label: "לקוח", type: "fk", nullable, fk: fk("customers") },
      { name: "label", label: "כינוי לכתובת", type: "text", nullable },
      { name: "street", label: "רחוב", type: "text" },
      { name: "house_number", label: "מספר בית", type: "text", nullable },
      { name: "apartment", label: "דירה", type: "text", nullable },
      { name: "floor", label: "קומה", type: "text", nullable },
      { name: "city", label: "עיר", type: "text" },
      { name: "postal_code", label: "מיקוד", type: "text", nullable },
      { name: "access_notes", label: "הערות הגעה", type: "longtext", nullable },
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "events",
    label: "אירועים",
    description: "האירוע שעבורו מוזמן האוכל, כולל מספר הסועדים והעדפות תזונה.",
    group: "orders",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    labelColumn: "event_type",
    columns: [
      id,
      { name: "customer_id", label: "לקוח", type: "fk", fk: fk("customers") },
      { name: "event_type", label: "סוג אירוע", type: "text" },
      { name: "event_date", label: "תאריך האירוע", type: "date" },
      { name: "adults", label: "מבוגרים", type: "int", defaultValue: 0 },
      { name: "children", label: "ילדים", type: "int", defaultValue: 0 },
      { name: "vegetarian_guests", label: "סועדים צמחונים", type: "int", defaultValue: 0 },
      { name: "vegan_guests", label: "סועדים טבעונים", type: "int", defaultValue: 0 },
      { name: "restricted_guests", label: "סועדים עם הגבלות", type: "int", defaultValue: 0 },
      { name: "dietary_notes", label: "הערות תזונה", type: "longtext", nullable },
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "orders",
    label: "הזמנות",
    description: "הזמנה אחת לכל אירוע, עם סטטוס, סכומים ואופן אספקה.",
    group: "orders",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    columns: [
      id,
      { name: "customer_id", label: "לקוח", type: "fk", fk: fk("customers") },
      { name: "event_id", label: "אירוע", type: "fk", unique: true, fk: fk("events") },
      {
        name: "status",
        label: "סטטוס",
        type: "enum",
        defaultValue: "draft",
        options: { draft: "טיוטה", pending_approval: "ממתינה לאישור", approved: "אושרה", rejected: "נדחתה" },
      },
      { name: "version", label: "גרסה", type: "int", defaultValue: 1 },
      {
        name: "fulfillment_type",
        label: "אופן אספקה",
        type: "enum",
        options: { pickup: "איסוף עצמי", delivery: "משלוח" },
      },
      { name: "requested_at", label: "מועד מבוקש", type: "timestamp" },
      { name: "delivery_address_id", label: "כתובת למשלוח", type: "fk", nullable, fk: fk("addresses") },
      { name: "currency", label: "מטבע", type: "text", defaultValue: "ILS" },
      { name: "subtotal_minor", label: "סכום ביניים", type: "money", nullable },
      { name: "delivery_fee_minor", label: "דמי משלוח", type: "money", nullable },
      { name: "total_minor", label: "סכום כולל", type: "money", nullable },
      { name: "submitted_at", label: "הוגשה בתאריך", type: "timestamp", nullable },
      { name: "decided_at", label: "הוחלט בתאריך", type: "timestamp", nullable },
      { name: "decision_note", label: "הערת החלטה", type: "longtext", nullable },
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "dishes",
    label: "מנות",
    description: "תפריט העסק: קטגוריה, מחיר, צעד כמות, זמינות ותמונה.",
    group: "menu",
    editable: true,
    labelColumn: "name",
    columns: [
      { ...id, addedByLaterMigration },
      { name: "legacy_code", label: "קוד מנה", type: "text", unique: true, addedByLaterMigration },
      { name: "name", label: "שם המנה", type: "text", addedByLaterMigration },
      { name: "description", label: "תיאור", type: "longtext", nullable, addedByLaterMigration },
      { name: "category_id", label: "קטגוריה", type: "fk", fk: fk("dish_categories"), addedByLaterMigration },
      { name: "pricing_unit", label: "יחידת מכירה", type: "enum", options: DISH_UNITS, addedByLaterMigration },
      { name: "per_guest", label: "כמות לכל אורח", type: "text", nullable, addedByLaterMigration },
      { name: "price_minor", label: "מחיר", type: "money" },
      { name: "step_milli", label: "צעד כמות", type: "milli" },
      { name: "is_available", label: "זמינה להזמנה", type: "bool", defaultValue: true, addedByLaterMigration },
      { name: "image_path", label: "נתיב תמונה", type: "text", nullable, addedByLaterMigration },
    ],
  },
  {
    name: "dish_categories",
    label: "קטגוריות מנות",
    description: "הקטגוריות שמהן בנוי התפריט.",
    group: "menu",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    labelColumn: "name",
    columns: [
      id,
      { name: "legacy_code", label: "קוד קטגוריה", type: "text", unique: true },
      { name: "name", label: "שם הקטגוריה", type: "text", unique: true },
      { name: "sort_order", label: "סדר תצוגה", type: "int", defaultValue: 0 },
      { name: "is_active", label: "פעילה", type: "bool", defaultValue: true },
    ],
  },
  {
    name: "dish_dietary",
    label: "מידע תזונתי",
    description: "כשרות וצמחונות לכל מנה. ערך חסר פירושו שהמידע אינו ידוע, ולא תשובה שלילית.",
    group: "menu",
    readOnlyReason: "נערך בטופס המנה, בידי הבעלים בלבד.",
    columns: [
      { name: "dish_id", label: "מנה", type: "fk", pk: true, fk: fk("dishes") },
      { name: "kashrut_class", label: "כשרות", type: "enum", nullable, options: DISH_KASHRUT, nullLabel: UNKNOWN },
      { name: "is_vegetarian", label: "צמחונית", type: "bool", nullable, nullLabel: UNKNOWN },
      { name: "is_vegan", label: "טבעונית", type: "bool", nullable, nullLabel: UNKNOWN },
      { name: "verified_at", label: "אומת בתאריך", type: "timestamp", nullable },
    ],
  },
  {
    name: "allergens",
    label: "אלרגנים",
    description: "רשימת האלרגנים של העסק. אלרגן חדש הוא בגדר לא ידוע בכל מנה עד שיוזן עבורה.",
    group: "menu",
    editable: true,
    labelColumn: "name",
    columns: [
      id,
      { name: "name", label: "שם האלרגן", type: "text", unique: true },
    ],
  },
  {
    name: "dish_allergens",
    label: "אלרגנים במנות",
    description: "מה ידוע על כל אלרגן בכל מנה. שורה חסרה פירושה שהמידע אינו ידוע, ולא שהמנה נקייה.",
    group: "menu",
    readOnlyReason: "נערך בטופס המנה, בידי הבעלים בלבד.",
    columns: [
      { name: "dish_id", label: "מנה", type: "fk", pk: true, fk: fk("dishes") },
      { name: "allergen_id", label: "אלרגן", type: "fk", pk: true, fk: fk("allergens") },
      { name: "status", label: "מצב", type: "enum", options: ALLERGEN_STATUSES },
    ],
  },
  {
    name: "delivery_zones",
    label: "אזורי משלוח",
    description: "דמי המשלוח לפי עיר. אין לטבלה קשר ישיר לטבלאות אחרות.",
    group: "menu",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    columns: [
      { ...id, addedByLaterMigration },
      { name: "city", label: "עיר", type: "text", unique: true },
      { name: "fee_minor", label: "דמי משלוח", type: "money" },
    ],
  },
  {
    name: "order_items",
    label: "פריטי הזמנה",
    description: "המנות שנכללו בהזמנה בעת הגשתה, כולל שם ומחיר באותו רגע.",
    group: "orders",
    readOnlyReason: "נוצר בעת הגשת ההזמנה ואינו נערך כאן.",
    columns: [
      { name: "order_id", label: "הזמנה", type: "fk", pk: true, fk: fk("orders") },
      { name: "dish_id", label: "מנה", type: "fk", pk: true, fk: fk("dishes") },
      { name: "name", label: "שם המנה בעת ההזמנה", type: "text" },
      { name: "unit", label: "יחידה", type: "text" },
      { name: "quantity_milli", label: "כמות", type: "milli" },
      { name: "unit_price_minor", label: "מחיר ליחידה", type: "money" },
      { name: "line_total_minor", label: "סכום השורה", type: "money" },
    ],
  },
  {
    name: "order_submissions",
    label: "הגשות הזמנה",
    description: "קבלת ההגשה המקורית, כדי למנוע הגשה כפולה. נגישה לשרת בלבד.",
    group: "orders",
    // Holds credential hashes and customer payloads: described here, but never read by the browser.
    hiddenFromData: true,
    readOnlyReason: "נוצר בעת הגשת ההזמנה ואינו נערך כאן.",
    columns: [
      { name: "order_id", label: "הזמנה", type: "fk", pk: true, fk: fk("orders") },
      { name: "token_hash", label: "תקציר אסימון", type: "text", unique: true, masked: true },
      { name: "payload", label: "תוכן ההגשה", type: "jsontext" },
    ],
  },
];

TABLES.push(...FOUNDATION_TABLES);
TABLES.find(table => table.name === 'orders').columns.push({
  name: 'time_slot_id', label: 'חלון זמן', type: 'fk', nullable: true,
  fk: fk('time_slots'), addedByLaterMigration: true,
});

// Every foreign key in the migrations. Composite keys list all their columns, because the
// extra column is what keeps an order and its address or event on the same customer.
export const RELATIONS = [
  ...FOUNDATION_RELATIONS,
  { from: "addresses", columns: ["customer_id"], to: "customers", toColumns: ["id"], optional: true },
  { from: "events", columns: ["customer_id"], to: "customers", toColumns: ["id"] },
  { from: "orders", columns: ["customer_id"], to: "customers", toColumns: ["id"] },
  { from: "orders", columns: ["event_id", "customer_id"], to: "events", toColumns: ["id", "customer_id"] },
  { from: "orders", columns: ["delivery_address_id", "customer_id"], to: "addresses", toColumns: ["id", "customer_id"], optional: true },
  { from: "order_items", columns: ["order_id"], to: "orders", toColumns: ["id"] },
  { from: "order_items", columns: ["dish_id"], to: "dishes", toColumns: ["id"] },
  { from: "order_submissions", columns: ["order_id"], to: "orders", toColumns: ["id"] },
  { from: "dishes", columns: ["category_id"], to: "dish_categories", toColumns: ["id"], addedByLaterMigration },
  { from: "dish_dietary", columns: ["dish_id"], to: "dishes", toColumns: ["id"] },
  { from: "dish_allergens", columns: ["dish_id"], to: "dishes", toColumns: ["id"] },
  { from: "dish_allergens", columns: ["allergen_id"], to: "allergens", toColumns: ["id"] },
];

export function getTable(name) {
  return TABLES.find((table) => table.name === name) ?? null;
}

export function primaryKey(table) {
  return table.columns.filter((column) => column.pk).map((column) => column.name);
}

export function selectList(table) {
  return table.columns.map((column) => column.name).join(",");
}

// PostgREST select for an id-and-label lookup, or null when the table has no readable label.
export function labelSelect(table) {
  return table.labelColumn ? `id,label:${table.labelColumn}` : null;
}

export function relationsOf(tableName) {
  return {
    outgoing: RELATIONS.filter((relation) => relation.from === tableName),
    incoming: RELATIONS.filter((relation) => relation.to === tableName),
  };
}

// Columns a staff member fills in. Identity keys and trigger-managed timestamps are excluded.
export function formColumns(table) {
  return table.columns.filter((column) => !column.generated && column.type !== "id");
}

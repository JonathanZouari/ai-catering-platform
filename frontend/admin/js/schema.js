// Static description of the 16 application tables in
// supabase/migrations/*foundation.sql. Structure and Hebrew labels only, never records.
// tests/schema.test.mjs compares this file with the migration, so drift fails the tests.

const id = { name: "id", label: "מספר רשומה", type: "id", pk: true };
const createdAt = { name: "created_at", label: "נוצר בתאריך", type: "timestamp", generated: true };
const updatedAt = { name: "updated_at", label: "עודכן בתאריך", type: "timestamp", generated: true };
const isActive = { name: "is_active", label: "פעיל", type: "bool", defaultValue: true };

const fk = (table, column = "id") => ({ table, column });

const EMPLOYEE_ROLES = {
  owner: "בעלים",
  manager: "מנהל",
  chef: "שף",
  cook: "טבח",
  kitchen_assistant: "עוזר מטבח",
  driver: "נהג",
  server: "מלצר",
  other: "אחר",
};

const nullable = true;

export const GROUPS = [
  { id: "people", label: "לקוחות וכתובות" },
  { id: "orders", label: "אירועים והזמנות" },
  { id: "operations", label: "משלוחים ותשלומים" },
  { id: "menu", label: "תפריט ואזורי משלוח" },
  { id: "staff", label: "צוות" },
  { id: "equipment", label: "ציוד" },
  { id: "stock", label: "מלאי חומרי גלם" },
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
    name: "deliveries",
    label: "משלוחים",
    description: "הובלת אוכל או איסוף ציוד. עותק הכתובת נשמר ואינו משתנה.",
    group: "operations",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    columns: [
      id,
      { name: "address_snapshot", label: "עותק הכתובת", type: "jsonb" },
      { name: "order_id", label: "הזמנה", type: "fk", fk: fk("orders") },
      {
        name: "purpose",
        label: "מטרה",
        type: "enum",
        defaultValue: "food_drop_off",
        options: { food_drop_off: "הבאת אוכל", equipment_collection: "איסוף ציוד" },
      },
      { name: "address_id", label: "כתובת", type: "fk", fk: fk("addresses") },
      { name: "driver_employee_id", label: "נהג", type: "fk", nullable, fk: fk("employees") },
      {
        name: "status",
        label: "סטטוס",
        type: "enum",
        defaultValue: "scheduled",
        options: {
          scheduled: "מתוכנן",
          out_for_delivery: "בדרך",
          delivered: "נמסר",
          failed: "נכשל",
          cancelled: "בוטל",
        },
      },
      { name: "window_start", label: "תחילת חלון זמן", type: "timestamp" },
      { name: "window_end", label: "סוף חלון זמן", type: "timestamp" },
      { name: "dispatched_at", label: "יצא בתאריך", type: "timestamp", nullable },
      { name: "completed_at", label: "הסתיים בתאריך", type: "timestamp", nullable },
      { name: "notes", label: "הערות", type: "longtext", nullable },
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "payments",
    label: "תשלומים",
    description: "קבלות והחזרים. רשומה קיימת אינה משתנה: תיקון נעשה בהחזר חדש.",
    group: "operations",
    appendOnly: true,
    readOnlyReason: "יומן הוספה בלבד. אי אפשר לערוך או למחוק רשומה קיימת.",
    columns: [
      id,
      { name: "kind", label: "סוג", type: "enum", options: { receipt: "קבלה", refund: "החזר" } },
      { name: "order_id", label: "הזמנה", type: "fk", fk: fk("orders") },
      { name: "currency", label: "מטבע", type: "text" },
      { name: "amount_minor", label: "סכום", type: "money" },
      {
        name: "method",
        label: "אמצעי תשלום",
        type: "enum",
        options: {
          cash: "מזומן",
          credit_card: "כרטיס אשראי",
          bank_transfer: "העברה בנקאית",
          bit: "ביט",
          check: "המחאה",
          other: "אחר",
        },
      },
      { name: "document_number", label: "מספר מסמך", type: "text", nullable, unique: true },
      { name: "refund_of_payment_id", label: "החזר עבור תשלום", type: "fk", nullable, fk: fk("payments") },
      { name: "reason", label: "סיבה", type: "longtext", nullable },
      { name: "recorded_by_employee_id", label: "נרשם בידי", type: "fk", nullable, fk: fk("employees") },
      { name: "occurred_at", label: "מועד התשלום", type: "timestamp" },
      createdAt,
    ],
  },
  {
    name: "equipment_items",
    label: "פריטי ציוד",
    description: "קטלוג שולחנות וכלי הגשה. הכמות נגזרת מיומן התנועות.",
    group: "equipment",
    editable: true,
    labelColumn: "name",
    columns: [
      id,
      { name: "name", label: "שם הפריט", type: "text", unique: true },
      {
        name: "category",
        label: "קטגוריה",
        type: "enum",
        options: { table: "שולחן", serving_utensil: "כלי הגשה" },
      },
      { name: "description", label: "תיאור", type: "longtext", nullable },
      { name: "replacement_cost_minor", label: "עלות החלפה", type: "money", nullable },
      isActive,
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "equipment_movements",
    label: "תנועות ציוד",
    description: "יומן כניסה ויציאה של ציוד. רשומה קיימת אינה משתנה.",
    group: "equipment",
    appendOnly: true,
    readOnlyReason: "יומן הוספה בלבד. אי אפשר לערוך או למחוק רשומה קיימת.",
    columns: [
      id,
      { name: "equipment_item_id", label: "פריט ציוד", type: "fk", fk: fk("equipment_items") },
      {
        name: "movement_type",
        label: "סוג תנועה",
        type: "enum",
        options: {
          purchase: "רכישה",
          dispatch: "יציאה לאירוע",
          return: "חזרה מאירוע",
          lost_at_event: "אבד באירוע",
          write_off: "גריעה",
          adjustment_in: "תיקון מלאי להוספה",
          adjustment_out: "תיקון מלאי להפחתה",
        },
      },
      { name: "quantity", label: "כמות", type: "int" },
      { name: "order_id", label: "הזמנה", type: "fk", nullable, fk: fk("orders") },
      { name: "delivery_id", label: "משלוח", type: "fk", nullable, fk: fk("deliveries") },
      { name: "employee_id", label: "עובד", type: "fk", nullable, fk: fk("employees") },
      { name: "occurred_at", label: "מועד התנועה", type: "timestamp", defaultValue: "now" },
      { name: "notes", label: "הערות", type: "longtext", nullable },
      createdAt,
    ],
  },
  {
    name: "ingredients",
    label: "חומרי גלם",
    description: "קטלוג חומרי הגלם ויחידת המידה הבסיסית של כל אחד.",
    group: "stock",
    editable: true,
    labelColumn: "name",
    columns: [
      id,
      { name: "name", label: "שם חומר הגלם", type: "text", unique: true },
      {
        name: "base_unit",
        label: "יחידת מידה",
        type: "enum",
        options: { g: "גרם", ml: "מיליליטר", unit: "יחידה" },
        hint: "לא ניתן לשנות יחידה אחרי שנרשמו תנועות מלאי.",
      },
      { name: "reorder_level", label: "סף הזמנה מחדש", type: "int", nullable, hint: "מספר שלם ביחידת המידה שנבחרה." },
      isActive,
      createdAt,
      updatedAt,
    ],
  },
  {
    name: "ingredient_batches",
    label: "אצוות חומרי גלם",
    description: "כל קבלה של חומר גלם, עם ספק, עלות ותוקף.",
    group: "stock",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    labelColumn: "lot_code",
    columns: [
      id,
      { name: "ingredient_id", label: "חומר גלם", type: "fk", fk: fk("ingredients") },
      { name: "lot_code", label: "קוד אצווה", type: "text", nullable },
      { name: "supplier_name", label: "שם הספק", type: "text", nullable },
      { name: "received_on", label: "התקבל בתאריך", type: "date" },
      { name: "expires_on", label: "תוקף עד", type: "date", nullable },
      { name: "total_cost_minor", label: "עלות כוללת", type: "money", nullable },
      { name: "currency", label: "מטבע", type: "text", defaultValue: "ILS" },
      createdAt,
    ],
  },
  {
    name: "ingredient_movements",
    label: "תנועות מלאי",
    description: "יומן קבלה, צריכה ופחת של אצוות. רשומה קיימת אינה משתנה.",
    group: "stock",
    appendOnly: true,
    readOnlyReason: "יומן הוספה בלבד. אי אפשר לערוך או למחוק רשומה קיימת.",
    columns: [
      id,
      { name: "batch_id", label: "אצווה", type: "fk", fk: fk("ingredient_batches") },
      {
        name: "movement_type",
        label: "סוג תנועה",
        type: "enum",
        options: {
          receipt: "קבלה",
          consumption: "צריכה",
          waste: "פחת",
          expired_disposal: "השמדה בגלל תוקף",
          return_to_supplier: "החזרה לספק",
          adjustment_in: "תיקון מלאי להוספה",
          adjustment_out: "תיקון מלאי להפחתה",
        },
      },
      { name: "quantity", label: "כמות", type: "int" },
      { name: "order_id", label: "הזמנה", type: "fk", nullable, fk: fk("orders") },
      { name: "employee_id", label: "עובד", type: "fk", nullable, fk: fk("employees") },
      { name: "occurred_at", label: "מועד התנועה", type: "timestamp", defaultValue: "now" },
      { name: "notes", label: "הערות", type: "longtext", nullable },
      createdAt,
    ],
  },
  {
    name: "dishes",
    label: "מנות",
    description: "תפריט העסק: מחיר, צעד כמות, פרטי המנה ותמונה.",
    group: "menu",
    editable: true,
    labelColumn: "metadata->>name",
    columns: [
      { name: "id", label: "מזהה מנה", type: "text", pk: true },
      { name: "metadata", label: "פרטי המנה", type: "jsonb" },
      { name: "price_minor", label: "מחיר", type: "money" },
      { name: "step_milli", label: "צעד כמות", type: "milli" },
      { name: "image_path", label: "נתיב תמונה", type: "text", nullable, addedByLaterMigration: true },
    ],
  },
  {
    name: "delivery_zones",
    label: "אזורי משלוח",
    description: "דמי המשלוח לפי עיר. אין לטבלה קשר ישיר לטבלאות אחרות.",
    group: "menu",
    readOnlyReason: "קריאה בלבד בשלב זה.",
    columns: [
      { name: "city", label: "עיר", type: "text", pk: true },
      { name: "fee_minor", label: "דמי משלוח", type: "money" },
    ],
  },
  {
    name: "employees",
    label: "עובדים",
    description: "אנשי הצוות ותפקידם בעסק. אין קשר בין הטבלה לחשבון ההתחברות.",
    group: "staff",
    editable: true,
    labelColumn: "full_name",
    columns: [
      id,
      { name: "full_name", label: "שם מלא", type: "text" },
      { name: "role", label: "תפקיד", type: "enum", options: EMPLOYEE_ROLES },
      { name: "email", label: "דוא״ל", type: "email", nullable, unique: true },
      { name: "phone", label: "טלפון", type: "phone", nullable },
      { name: "hired_on", label: "תאריך קליטה", type: "date", nullable },
      isActive,
      createdAt,
      updatedAt,
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
    description: "קבלת ההגשה המקורית, כדי למנוע הגשה כפולה.",
    group: "orders",
    readOnlyReason: "נוצר בעת הגשת ההזמנה ואינו נערך כאן.",
    columns: [
      { name: "token_hash", label: "תקציר אסימון", type: "text", pk: true, masked: true },
      { name: "order_id", label: "הזמנה", type: "fk", unique: true, fk: fk("orders") },
      { name: "payload", label: "תוכן ההגשה", type: "jsontext" },
    ],
  },
];

// Every foreign key in the migration. Composite keys list all their columns, because the
// extra column is what keeps an order and its address or event on the same customer.
export const RELATIONS = [
  { from: "addresses", columns: ["customer_id"], to: "customers", toColumns: ["id"], optional: true },
  { from: "events", columns: ["customer_id"], to: "customers", toColumns: ["id"] },
  { from: "orders", columns: ["customer_id"], to: "customers", toColumns: ["id"] },
  { from: "orders", columns: ["event_id", "customer_id"], to: "events", toColumns: ["id", "customer_id"] },
  { from: "orders", columns: ["delivery_address_id", "customer_id"], to: "addresses", toColumns: ["id", "customer_id"], optional: true },
  { from: "deliveries", columns: ["order_id"], to: "orders", toColumns: ["id"] },
  { from: "deliveries", columns: ["address_id"], to: "addresses", toColumns: ["id"] },
  { from: "deliveries", columns: ["driver_employee_id"], to: "employees", toColumns: ["id"], optional: true },
  { from: "payments", columns: ["order_id", "currency"], to: "orders", toColumns: ["id", "currency"] },
  { from: "payments", columns: ["refund_of_payment_id", "order_id", "currency"], to: "payments", toColumns: ["id", "order_id", "currency"], optional: true },
  { from: "payments", columns: ["recorded_by_employee_id"], to: "employees", toColumns: ["id"], optional: true },
  { from: "equipment_movements", columns: ["equipment_item_id"], to: "equipment_items", toColumns: ["id"] },
  { from: "equipment_movements", columns: ["order_id"], to: "orders", toColumns: ["id"], optional: true },
  { from: "equipment_movements", columns: ["delivery_id", "order_id"], to: "deliveries", toColumns: ["id", "order_id"], optional: true },
  { from: "equipment_movements", columns: ["employee_id"], to: "employees", toColumns: ["id"], optional: true },
  { from: "ingredient_batches", columns: ["ingredient_id"], to: "ingredients", toColumns: ["id"] },
  { from: "ingredient_movements", columns: ["batch_id"], to: "ingredient_batches", toColumns: ["id"] },
  { from: "ingredient_movements", columns: ["order_id"], to: "orders", toColumns: ["id"], optional: true },
  { from: "ingredient_movements", columns: ["employee_id"], to: "employees", toColumns: ["id"], optional: true },
  { from: "order_items", columns: ["order_id"], to: "orders", toColumns: ["id"] },
  { from: "order_items", columns: ["dish_id"], to: "dishes", toColumns: ["id"] },
  { from: "order_submissions", columns: ["order_id"], to: "orders", toColumns: ["id"] },
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

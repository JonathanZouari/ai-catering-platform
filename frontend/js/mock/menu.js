// MOCK DATA — placeholder until the API exists (docs/UX_UI_SPEC.md). Not real dishes or prices.
// Quantities, prices and dietary data below are invented for the demo only (OPEN #3, #8, #14, #17).

export const UNITS = {
  tray: { one: "מגש", many: "מגשים", per: "למגש" },
  kg: { one: "ק״ג", many: "ק״ג", per: "לק״ג" },
  item: { one: "יחידה", many: "יחידות", per: "ליחידה" },
};

export const CATEGORIES = [
  { id: "salads", name: "סלטים ומטבלים" },
  { id: "mains", name: "עיקריות" },
  { id: "sides", name: "תוספות" },
  { id: "desserts", name: "קינוחים" },
];

// kind: meat | dairy | pareve. allergens: null = unknown (never shown as safe).
export const DISHES = [
  { id: "hummus", cat: "salads", name: "חומוס ביתי", price: 120, unit: "tray", kind: "pareve", vegetarian: true, vegan: true, allergens: ["שומשום"] },
  { id: "eggplant", cat: "salads", name: "סלט חצילים קלוי", price: 58, unit: "tray", kind: "pareve", vegetarian: true, vegan: true, allergens: null },
  { id: "chopped", cat: "salads", name: "סלט ירקות קצוץ", price: 96, unit: "tray", kind: "pareve", vegetarian: true, vegan: true, allergens: [] },
  { id: "quinoa", cat: "salads", name: "סלט קינואה וירקות קלויים", price: 140, unit: "tray", kind: "pareve", vegetarian: true, vegan: true, allergens: [] },
  { id: "schnitzel", cat: "mains", name: "שניצל קריספי", price: 260, unit: "tray", kind: "meat", vegetarian: false, vegan: false, allergens: ["גלוטן", "ביצים"] },
  { id: "salmon", cat: "mains", name: "סלמון בתנור", price: 190, unit: "kg", kind: "pareve", vegetarian: false, vegan: false, allergens: ["דגים"] },
  { id: "meatballs", cat: "mains", name: "קציצות בעשבי תיבול", price: 240, unit: "tray", kind: "meat", vegetarian: false, vegan: false, allergens: null },
  { id: "pasta", cat: "mains", name: "פסטה ברוטב שמנת", price: 210, unit: "tray", kind: "dairy", vegetarian: true, vegan: false, allergens: ["גלוטן", "חלב"] },
  { id: "rice", cat: "sides", name: "אורז עם שקדים", price: 180, unit: "tray", kind: "pareve", vegetarian: true, vegan: true, allergens: ["שקדים"] },
  { id: "potatoes", cat: "sides", name: "תפוחי אדמה בתנור", price: 150, unit: "tray", kind: "pareve", vegetarian: true, vegan: true, allergens: [] },
  { id: "tart", cat: "desserts", name: "מיני טארט לימון", price: 9, unit: "item", step: 10, kind: "dairy", vegetarian: true, vegan: false, allergens: ["גלוטן", "חלב", "ביצים"] },
  { id: "chocolate", cat: "desserts", name: "עוגת שוקולד פרווה", price: 220, unit: "tray", kind: "pareve", vegetarian: true, vegan: false, allergens: null },
];

export const KIND_LABEL = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };

export const EVENT = { dateLabel: "יום חמישי, 19 בנובמבר", time: "19:00", guests: 80, adults: 68, children: 12, vegetarians: 12, vegans: 4, mode: "משלוח" };

// Starting order; sums to ₪5,592 so the demo matches the brief's example.
export const INITIAL_ORDER = { hummus: 6, schnitzel: 8, rice: 6, salmon: 8, chopped: 2 };

export const dishById = (id) => DISHES.find((d) => d.id === id);

// Stand-in for the backend pricing engine (ADR 0003): deterministic, never done by the LLM.
export const orderTotal = (order) =>
  Object.entries(order).reduce((sum, [id, qty]) => sum + dishById(id).price * qty, 0);

// Scripted "agent" proposals; a real agent would only propose existing dishes via the API.
export const SCRIPTED_PROPOSALS = [
  {
    message: "שמתי לב שיש בהזמנה רק שני סלטים, ובין האורחים 12 צמחונים ו-4 טבעונים. מציע להוסיף מהתפריט סלט חצילים קלוי, שמתאים גם לטבעונים. אני לא משנה כלום עד שתאשרו.",
    changes: [{ dishId: "eggplant", to: 5 }],
  },
  {
    message: "אפשר גם להגדיל את החומוס: כרגע הוא המטבל היחיד בהזמנה, והוא מתאים לצמחונים ולטבעונים.",
    changes: [{ dishId: "hummus", to: 9 }],
  },
];
export const DEMO_REPLY = "זו הדגמה: התשובות כאן מתוסרטות. בגרסה המחוברת אענה רק על מנות מהתפריט של העסק, ולא אשנה את ההזמנה בלי אישור שלך.";

// SAMPLE DATA for the UI prototype only. Replaced by the catalog and order APIs in Phase 2–3
// (API_CONTRACTS.md). Prices and quantities here are display values; the backend stays
// authoritative for every calculation (PRD §8, ADR 0003).

export const categories = [
  { id: "salads", name: "סלטים" },
  { id: "starters", name: "מנות פתיחה" },
  { id: "mains", name: "עיקריות" },
  { id: "sides", name: "תוספות" },
  { id: "bakes", name: "מאפים" },
  { id: "desserts", name: "קינוחים" },
];

// allergens: "contains" | "free" | "unknown" per allergen. Unknown is never shown as safe.
export const dishes = [
  {
    id: "tabbouleh", category: "salads", name: "סלט טאבולה",
    description: "בורגול, פטרוזיליה, נענע, עגבנייה ולימון",
    price: 180, unit: "tray", serves: "10–12", kashrut: "parve", diet: ["vegan", "vegetarian"],
    allergens: { gluten: "contains", sesame: "free", nuts: "free", eggs: "free", milk: "free" },
    photo: "/assets/photos/tabbouleh.jpg", available: true,
  },
  {
    id: "eggplant", category: "salads", name: "חציל קלוי בטחינה",
    description: "חציל שרוף על האש, טחינה, סילאן ורימונים",
    price: 160, unit: "tray", serves: "8–10", kashrut: "parve", diet: ["vegan", "vegetarian"],
    allergens: { gluten: "free", sesame: "contains", nuts: "free", eggs: "free", milk: "free" },
    photo: "/assets/photos/roasted-eggplant.jpg", available: true,
  },
  {
    id: "caesar", category: "salads", name: "סלט קיסר עם פרמזן",
    description: "חסה, קרוטונים, שבבי פרמזן ורוטב קיסר",
    price: 210, unit: "tray", serves: "10–12", kashrut: "dairy", diet: ["vegetarian"],
    allergens: { gluten: "contains", sesame: "free", nuts: "unknown", eggs: "unknown", milk: "contains" },
    photo: "/assets/photos/caesar-salad.jpg", available: true,
  },
  {
    id: "skewers", category: "mains", name: "שיפודי פרגית",
    description: "פרגית על הגריל עם עשבי תיבול",
    price: 95, unit: "kg", serves: null, kashrut: "meat", diet: [],
    allergens: { gluten: "free", sesame: "free", nuts: "free", eggs: "free", milk: "free" },
    photo: "/assets/photos/chicken-skewers.jpg", available: true,
  },
  {
    id: "mujadara", category: "mains", name: "מג׳דרה עם בצל מטוגן",
    description: "עדשים, אורז ובצל מקורמל",
    price: 150, unit: "tray", serves: "8–10", kashrut: "parve", diet: ["vegan", "vegetarian"],
    allergens: { gluten: "free", sesame: "free", nuts: "free", eggs: "free", milk: "free" },
    photo: null, available: true,
  },
  {
    id: "quiche", category: "bakes", name: "מיני קיש בטטה",
    description: "בצק חמאה במילוי בטטה צלויה ועשבי תיבול",
    price: 28, unit: "item", serves: null, kashrut: "dairy", diet: ["vegetarian"],
    allergens: { gluten: "contains", sesame: "free", nuts: "free", eggs: "contains", milk: "contains" },
    photo: "/assets/photos/mini-quiche.jpg", available: true,
  },
];

export const unitLabels = { guest: "לאורח", tray: "למגש", kg: "לק״ג", item: "ליחידה" };
export const unitNouns = { guest: "אורחים", tray: "מגשים", kg: "ק״ג", item: "יח׳" };
export const kashrutLabels = { meat: "בשרי", dairy: "חלבי", parve: "פרווה" };
export const dietLabels = { vegan: "טבעוני", vegetarian: "צמחוני" };
export const allergenLabels = { gluten: "גלוטן", sesame: "שומשום", nuts: "אגוזים", eggs: "ביצים", milk: "חלב" };

export const eventTypes = ["בר/בת מצווה", "יום הולדת", "שבת חתן", "ברית", "ארוחה משפחתית", "אחר"];
export const timeSlots = [
  { id: "10-12", label: "10:00–12:00", full: false },
  { id: "12-14", label: "12:00–14:00", full: false },
  { id: "16-18", label: "16:00–18:00", full: true },
];
export const deliveryZone = { name: "שרון", fee: 120 };
export const blockedDates = ["2026-12-24", "2026-12-25"];

// A draft order and one assistant proposal, as the customer flow would load them.
export const draftOrder = {
  version: 1,
  event: {
    type: "בר/בת מצווה", date: "2026-12-14", delivery: true, address: "הרצל 12, רעננה",
    slot: "12-14", adults: 60, kids: 18, vegetarian: 6, vegan: 2, notes: "",
  },
  lines: { tabbouleh: 2, skewers: 9, quiche: 20 },
};

export const assistantProposal = {
  question: "יש לנו 6 צמחונים ו-2 טבעונים. חסר משהו?",
  answer: "אין בהזמנה מנה עיקרית טבעונית, ולפי מספר האורחים חסרים סלטים. זו ההצעה שלי:",
  changes: [
    { dishId: "mujadara", from: 0, to: 2 },
    { dishId: "tabbouleh", from: 2, to: 4 },
  ],
};

// Placeholder rule for the salad recommendation until the business sets the real
// serving formulas (OPEN_DECISIONS #3); the backend will compute this in Phase 3.
export const recommendedSaladTrays = (guests) => Math.ceil(guests / 20);

// The owner's incoming quotation requests (admin A1).
export const quoteRequests = [
  { id: "Q-1042", customer: "משפחת לוי", eventType: "בר מצווה", date: "2026-12-14", guests: 78, total: 2555, status: "pending" },
  { id: "Q-1043", customer: "משפחת ברק", eventType: "יום הולדת", date: "2026-12-18", guests: 45, total: 3400, status: "pending" },
  { id: "Q-1045", customer: "רועי ומיכל כהן", eventType: "שבת חתן", date: "2026-12-20", guests: 60, total: 4120, status: "pending" },
  { id: "Q-1038", customer: "משפחת רוזנברג", eventType: "ברית", date: "2026-12-08", guests: 30, total: 1850, status: "approved" },
  { id: "Q-1036", customer: "משפחת שגיא", eventType: "יום הולדת", date: "2026-12-05", guests: 25, total: 1400, status: "rejected" },
];

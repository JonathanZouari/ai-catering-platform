// Mock catalog until the backend serves /api/dishes. Prices are per tray in ILS.
// `serves` = adult portions per tray; a child counts as CHILD_FACTOR of an adult.
// Nutrition is per single portion and is information only, never a recommendation.

export const CHILD_FACTOR = 0.5;

export const CATEGORIES = [
  { id: "bread", label: "מאפים" },
  { id: "salad", label: "סלטים וממרחים" },
  { id: "main", label: "עיקריות" },
  { id: "side", label: "תוספות" },
  { id: "dessert", label: "קינוחים" },
];

export const KASHRUT = { meat: "בשרי", parve: "פרווה", dairy: "חלבי" };

export const DISHES = [
  {
    id: "challah", category: "bread", name: "חלה קלועה בשומשום", img: "challah",
    blurb: "נאפית בבוקר האירוע, קלועה בשש.", price: 48, unit: "חלה", serves: 12,
    kashrut: "parve", diet: ["vegetarian"], allergens: ["גלוטן", "שומשום", "ביצים"],
    nutrition: { kcal: 190, protein: 6, carbs: 34, fat: 3 },
  },
  {
    id: "bourekas", category: "bread", name: "בורקס קטנים", img: "bourekas",
    blurb: "גבינה ותפוחי אדמה, בצק עלים בחמאה.", price: 165, unit: "מגש", serves: 14,
    kashrut: "dairy", diet: ["vegetarian"], allergens: ["גלוטן", "חלב", "ביצים", "שומשום"],
    nutrition: { kcal: 260, protein: 7, carbs: 22, fat: 16 },
  },
  {
    id: "hummus", category: "salad", name: "חומוס עם גרגרים ושמן זית", img: "hummus",
    blurb: "חומוס חם, פפריקה מתוקה ופטרוזיליה.", price: 120, unit: "מגש", serves: 16,
    kashrut: "parve", diet: ["vegan"], allergens: ["שומשום"],
    nutrition: { kcal: 170, protein: 7, carbs: 15, fat: 9 },
  },
  {
    id: "eggplant", category: "salad", name: "חציל קלוי, טחינה ורימון", img: "eggplant",
    blurb: "חצילים על האש, טחינה גולמית ופטרוזיליה.", price: 165, unit: "מגש", serves: 12,
    kashrut: "parve", diet: ["vegan"], allergens: ["שומשום"],
    nutrition: { kcal: 140, protein: 4, carbs: 12, fat: 9 },
  },
  {
    id: "tabbouleh", category: "salad", name: "טאבולה ירוקה", img: "tabbouleh",
    blurb: "הרבה פטרוזיליה, נענע, בורגול ולימון.", price: 140, unit: "מגש", serves: 14,
    kashrut: "parve", diet: ["vegan"], allergens: ["גלוטן"],
    nutrition: { kcal: 110, protein: 3, carbs: 16, fat: 4 },
  },
  {
    id: "quinoa", category: "salad", name: "קינואה, בטטה וחומוס", img: "quinoa",
    blurb: "בטטה צלויה, בצל סגול ועשבי תיבול.", price: 155, unit: "מגש", serves: 14,
    kashrut: "parve", diet: ["vegan"], allergens: [],
    nutrition: { kcal: 180, protein: 6, carbs: 28, fat: 5 },
  },
  {
    id: "chicken", category: "main", name: "פרגיות על האש, סומק וזעתר", img: "chicken",
    blurb: "נצלות על גחלים, לימון צלוי לצד.", price: 340, unit: "מגש", serves: 10,
    kashrut: "meat", diet: [], allergens: [],
    nutrition: { kcal: 290, protein: 32, carbs: 2, fat: 17 },
  },
  {
    id: "salmon", category: "main", name: "סלמון אפוי בעשבים", img: "salmon",
    blurb: "פילה טרי, עגבניות שרי ולימון.", price: 420, unit: "מגש", serves: 10,
    kashrut: "parve", diet: [], allergens: ["דגים"],
    nutrition: { kcal: 310, protein: 30, carbs: 3, fat: 20 },
  },
  {
    id: "schnitzel", category: "main", name: "שניצלונים לילדים", img: "schnitzel",
    blurb: "חזה עוף בפירורי לחם, לא מטוגן בשמן עמוק.", price: 210, unit: "מגש", serves: 10,
    kashrut: "meat", diet: [], allergens: ["גלוטן", "ביצים"], kids: true,
    nutrition: { kcal: 250, protein: 22, carbs: 14, fat: 12 },
  },
  {
    id: "mujadara", category: "side", name: "מג'דרה עם בצל מטוגן", img: "mujadara",
    blurb: "אורז, עדשים חומות ובצל מקורמל עמוק.", price: 130, unit: "מגש", serves: 14,
    kashrut: "parve", diet: ["vegan"], allergens: [],
    nutrition: { kcal: 230, protein: 8, carbs: 38, fat: 6 },
  },
  {
    id: "potatoes", category: "side", name: "תפוחי אדמה צלויים ברוזמרין", img: "potatoes",
    blurb: "פריכים מבחוץ, שום שלם ורוזמרין.", price: 120, unit: "מגש", serves: 14,
    kashrut: "parve", diet: ["vegan"], allergens: [],
    nutrition: { kcal: 160, protein: 3, carbs: 26, fat: 5 },
  },
  {
    id: "fruit", category: "dessert", name: "מגש פירות העונה", img: "fruit",
    blurb: "אבטיח, מלון, ענבים, תותים וקיווי.", price: 240, unit: "מגש", serves: 16,
    kashrut: "parve", diet: ["vegan"], allergens: [],
    nutrition: { kcal: 80, protein: 1, carbs: 20, fat: 0 },
  },
  {
    id: "malabi", category: "dessert", name: "מלבי ורדים ופיסטוק", img: "malabi",
    blurb: "בכוסות אישיות, סירופ ורדים וקוקוס.", price: 15, unit: "כוס", serves: 1,
    kashrut: "dairy", diet: ["vegetarian"], allergens: ["חלב", "אגוזים"],
    nutrition: { kcal: 210, protein: 5, carbs: 32, fat: 7 },
  },
];

export const DISH_BY_ID = Object.fromEntries(DISHES.map((d) => [d.id, d]));

export const EVENT_TYPES = ["יום הולדת", "בר / בת מצווה", "ברית", "שבת משפחתית", "אירוע חברה", "אחר"];

export const TIME_SLOTS = ["11:00 עד 12:00", "12:00 עד 13:00", "17:00 עד 18:00", "18:00 עד 19:00"];

export const DELIVERY_ZONES = [
  { id: "center", label: "תל אביב והסביבה", fee: 120 },
  { id: "sharon", label: "השרון", fee: 160 },
  { id: "shfela", label: "השפלה", fee: 160 },
  { id: "jlm", label: "ירושלים", fee: 220 },
];

export const unitWord = (d, n) => (d.unit === "כוס" ? (n === 1 ? "כוס" : "כוסות") : d.unit === "חלה" ? (n === 1 ? "חלה" : "חלות") : n === 1 ? "מגש" : "מגשים");

export function img(id, base = "/assets/dishes/") {
  return `${base}${DISH_BY_ID[id]?.img ?? id}.webp`;
}

export function portionsNeeded(guests) {
  return guests.adults + guests.children * CHILD_FACTOR;
}

// A guest eats about one portion per course, not a full portion of every dish.
// Each course's need is split evenly across its dishes; quantities the customer
// set by hand stay as they are and the rest of the course balances around them.
// Kids dishes form their own group, sized on the children only.
export function balance(items, guests, manual = {}) {
  const out = { ...items };
  const groups = {};
  for (const id of Object.keys(items)) {
    const d = DISH_BY_ID[id];
    if (!d) continue;
    const key = `${d.category}|${d.kids ? 1 : 0}`;
    (groups[key] ??= []).push(d);
  }
  for (const list of Object.values(groups)) {
    const need = list[0].kids ? guests.children : portionsNeeded(guests);
    const fixed = list.filter((d) => manual[d.id]).reduce((sum, d) => sum + items[d.id] * d.serves, 0);
    const auto = list.filter((d) => !manual[d.id]);
    const share = Math.max(0, need - fixed) / Math.max(1, auto.length);
    for (const d of auto) out[d.id] = Math.max(1, Math.ceil(share / d.serves));
  }
  return out;
}

// What a dish would come to if it were added now.
export function recommendedQty(dish, guests, items = {}, manual = {}) {
  return balance({ ...items, [dish.id]: items[dish.id] || 1 }, guests, manual)[dish.id];
}

const ILS = new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS", maximumFractionDigits: 0 });
export const money = (n) => ILS.format(Math.round(n));

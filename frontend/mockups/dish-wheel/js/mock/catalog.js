// SAMPLE DATA for design review only. Shapes mirror docs/DATABASE_SCHEMA.md
// (pricing_unit, kashrut_class, nullable is_vegan/is_vegetarian, allergen_status
// contains | free | unknown). null = unknown and must never render as yes/no.
// v4: Hebrew copy. `short` is the wheel label; `variants` are the option pills and stand in
// for the real build's tray sizes / per-guest presets. Prices are illustrative only.
//
// loadCatalog() is the only read the screen should use. It stands in for:
//   GET /api/catalog/categories
//   GET /api/catalog/dishes          (price, unit, dietary; unknown fields are null)
//   GET /api/catalog/dishes/{id}     (component allergen statuses)
// Swap the body for frontend/js/api.js when those routes exist. Do not compute
// authoritative prices from this payload in the real build (ADR 0003).
import { money } from "../format.js";

export const SAMPLE_EVENT = {
  date: new Date(2026, 10, 19), // Thu 19 Nov 2026
  adults: 40,
  children: 12,
  fulfillment: "משלוח",
};
export const GUESTS = SAMPLE_EVENT.adults + SAMPLE_EVENT.children;

export const CATEGORIES = [
  { id: "salads", name: "סלטים", all: "כל הסלטים" },
  { id: "mains", name: "עיקריות", all: "כל העיקריות" },
  { id: "sides", name: "תוספות", all: "כל התוספות" },
  { id: "desserts", name: "קינוחים", all: "כל הקינוחים" },
];

// unit: what one quantity step buys. `per` labels a price ("₪95 למגש"), `count` labels a quantity.
// Hebrew counts: one is written as a word after the noun ("מגש אחד"), 2+ as digits before it.
export const UNITS = {
  tray: { per: "למגש", count: (q) => (q === 1 ? "מגש אחד" : `${q} מגשים`) },
  bowl: { per: "לקערה", count: (q) => (q === 1 ? "קערה אחת" : `${q} קערות`) },
  piece: { per: "ליחידה", count: (q) => (q === 1 ? "יחידה אחת" : `${q} יחידות`) },
  kg: { per: "לק״ג", count: (q) => `${q} ק״ג` },
  box: { per: "למארז", count: (q) => (q === 1 ? "מארז אחד" : `${q} מארזים`) },
  guest: { per: "לסועד", count: (q) => (q === 1 ? "סועד אחד" : `${q} סועדים`) },
};
const serves = (n) => `מספיק לכ־${n} סועדים`;
const tray = (half, full, s = [5, 10]) => [
  { id: "half", label: "חצי מגש", price: half, unit: "tray", note: serves(s[0]) },
  { id: "full", label: "מגש מלא", price: full, unit: "tray", note: serves(s[1]) },
];

// Allergen names, keyed so the copy reads "מכיל גלוטן" / "ללא שומשום".
const A = { gluten: "גלוטן", nuts: "אגוזים", sesame: "שומשום", mustard: "חרדל", milk: "חלב", egg: "ביצים",
  soy: "סויה", fish: "דגים", peanuts: "בוטנים", celery: "סלרי" };

export const DISHES = [
  {
    id: "quinoa", category: "salads", short: "סלט קשת", name: "סלט קשת עם גרגרי חומוס",
    description: "גרגרי חומוס, אבוקדו, בטטה צלויה, עגבניות שרי, צנונית ועלים ירוקים, עם שקדים קלויים ורוטב לימון וסילאן.",
    image: "img/quinoa.webp", alt: "קערה במבט מלמעלה: גרגרי חומוס, אבוקדו, עגבניות, בטטה ועלים ירוקים",
    variants: tray(95, 165), kashrut: "pareve", is_vegetarian: true, is_vegan: true, is_available: true,
    components: [
      { name: "גרגרי חומוס ואבוקדו", allergens: [[A.gluten, "free"]] },
      { name: "בטטה צלויה וצנונית", allergens: [] },
      { name: "שקדים קלויים", allergens: [[A.nuts, "contains"]] },
      { name: "רוטב לימון וסילאן", allergens: [[A.sesame, "unknown"], [A.mustard, "free"]] },
    ],
  },
  {
    id: "lentil", category: "salads", short: "סלט כפרי", name: "סלט כפרי עם פטה",
    description: "עגבניות, מלפפון, פלפלים, בצל סגול וזיתים, ומעליהם פרוסת פטה בולגרית עבה, אורגנו ושמן זית.",
    image: "img/lentil.webp", alt: "צלחת לבנה במבט מלמעלה: סלט עגבניות, מלפפון ופלפלים עם פרוסת פטה",
    variants: tray(80, 140), kashrut: "dairy", is_vegetarian: true, is_vegan: false, is_available: true,
    components: [
      { name: "עגבנייה, מלפפון, פלפל ובצל", allergens: [] },
      { name: "פטה בולגרית", allergens: [[A.milk, "contains"]] },
      { name: "זיתים ואורגנו", allergens: [] },
      { name: "שמן זית ולימון", allergens: [[A.mustard, "free"]] },
    ],
  },
  {
    id: "tahini-bowl", category: "salads", short: "קערת ביצים", name: "קערת ביצים וסלק",
    description: "קערה אישית: ביצים רכות, שעועית ירוקה, אפונה, סלק כבוש, מלפפון, כרוב סגול וטחינה.",
    image: "img/tahini-bowl.webp", alt: "קערה במבט מלמעלה: חצאי ביצים רכות, שעועית ירוקה, אפונה, קוביות סלק וכרוב",
    variants: [
      { id: "regular", label: "רגילה", price: 42, unit: "bowl", min: 10, note: "מינימום 10 קערות" },
      { id: "large", label: "גדולה", price: 52, unit: "bowl", min: 10, note: "מינימום 10 קערות" },
    ],
    kashrut: "pareve", is_vegetarian: true, is_vegan: false, is_available: true,
    components: [
      { name: "ביצים רכות", allergens: [[A.egg, "contains"]] },
      { name: "שעועית ירוקה, אפונה ואדממה", allergens: [[A.soy, "contains"]] },
      { name: "טחינה גולמית", allergens: [[A.sesame, "contains"]] },
      { name: "קישוט (תערובת הבית)", allergens: [[A.nuts, "unknown"], [A.peanuts, "unknown"]] },
    ],
  },
  {
    id: "salmon", category: "mains", short: "סלמון", name: "סלמון אפוי ברוטב עשבים",
    description: "פילה סלמון אפוי עם שום ושמיר, ברוטב עשבי תיבול ירוק ולצדו תפוחי אדמה קטנים.",
    image: "img/salmon.webp", alt: "פלטה אובלית במבט מלמעלה: סלמון אפוי ברוטב עשבים עם תפוחי אדמה",
    variants: [
      { id: "half", label: "חצי פילה", price: 135, unit: "piece", note: "כ־0.7 ק״ג, מספיק לכ־5" },
      { id: "whole", label: "פילה שלם", price: 265, unit: "piece", note: "כ־1.4 ק״ג, מספיק לכ־10" },
    ],
    kashrut: "pareve", is_vegetarian: false, is_vegan: false, is_available: true,
    components: [
      { name: "פילה סלמון", allergens: [[A.fish, "contains"]] },
      { name: "רוטב עשבים ופירורי לחם", allergens: [[A.gluten, "contains"], [A.egg, "unknown"]] },
      { name: "תפוחי אדמה קטנים", allergens: [] },
    ],
  },
  {
    id: "chicken", category: "mains", short: "פרגיות", name: "פרגיות על האש",
    description: "פרגיות ללא עצם במרינדת סומק ופפריקה, צלויות על הגריל, עם סחוג ירוק ובצל כבוש.",
    image: "img/chicken.webp", alt: "צלחת במבט מלמעלה: נתחי עוף צלויים עם רוטב ירוק, בצל ולימון",
    variants: [
      { id: "classic", label: "קלאסי", price: 149, unit: "kg", note: "ק״ג מספיק לכ־5" },
      { id: "spicy", label: "חריף", price: 155, unit: "kg", note: "ק״ג מספיק לכ־5" },
    ],
    kashrut: "meat", is_vegetarian: false, is_vegan: false, is_available: true,
    components: [
      { name: "פרגית", allergens: [] },
      { name: "מרינדת סומק ופפריקה", allergens: [[A.mustard, "unknown"], [A.sesame, "free"]] },
    ],
  },
  {
    id: "meatballs", category: "mains", short: "קציצות", name: "קציצות בקר ברוטב עגבניות",
    description: "קציצות בקר ועשבי תיבול בעבודת יד, בבישול איטי ברוטב עגבניות מתובל.",
    image: "img/meatballs.webp", alt: "קערה במבט מלמעלה: שלוש קציצות ברוטב עגבניות",
    variants: tray(140, 260), kashrut: "meat", is_vegetarian: false, is_vegan: false, is_available: true,
    components: [
      { name: "קציצות בקר ועשבי תיבול", allergens: [[A.gluten, "contains"], [A.egg, "contains"]] },
      { name: "רוטב עגבניות מתובל", allergens: [[A.celery, "unknown"]] },
    ],
  },
  {
    id: "grill", category: "mains", short: "מעורב על האש", name: "מגש מעורב על האש",
    description: "שיפודי עוף וקבב מתובלים, צלויים על הגחלים ומוגשים במגש.",
    image: "img/grill.webp", alt: "מגש במבט מלמעלה: שיפודים צלויים ומבריקים",
    variants: [
      { id: "adults", label: `מבוגרים · ${SAMPLE_EVENT.adults}`, price: 68, unit: "guest", preset: SAMPLE_EVENT.adults, min: 20, note: `${money(68)} לסועד` },
      { id: "all", label: `כולם · ${GUESTS}`, price: 68, unit: "guest", preset: GUESTS, min: 20, note: `${money(68)} לסועד` },
    ],
    kashrut: "meat", is_vegetarian: false, is_vegan: false,
    is_available: false, unavailable_reason: "לא זמין בתאריך האירוע שלכם",
    components: [
      { name: "קבב בקר", allergens: [] },
      { name: "שיפודי עוף", allergens: [] },
      { name: "זיגוג", allergens: [[A.mustard, "unknown"]] },
    ],
  },
  {
    id: "potatoes", category: "sides", short: "תפוחי אדמה", name: "תפוחי אדמה קטנים צלויים",
    description: "תפוחי אדמה פריכים עם פטרוזיליה, קונפי שום ומלח גס, צלויים בתבנית.",
    image: "img/potatoes.webp", alt: "מחבת במבט מלמעלה: קוביות תפוחי אדמה זהובות עם פטרוזיליה",
    variants: tray(55, 95), kashrut: "pareve", is_vegetarian: true, is_vegan: null, is_available: true,
    components: [
      { name: "תפוחי אדמה", allergens: [] },
      { name: "פטרוזיליה וקונפי שום", allergens: [] },
    ],
  },
  {
    id: "cauliflower", category: "sides", short: "חומוס קריספי", name: "חומוס קריספי וכרוב ניצנים",
    description: "גרגרי חומוס פריכים מהתנור, כרוב ניצנים צלוי וכרובית מתובלת עם זרעים קלויים.",
    image: "img/cauliflower.webp", alt: "קערה אפורה במבט מלמעלה: גרגרי חומוס פריכים, נבטים וירקות צלויים",
    variants: tray(65, 110), kashrut: null, is_vegetarian: true, is_vegan: true, is_available: true,
    components: [
      { name: "חומוס, כרוב ניצנים וכרובית", allergens: [] },
      { name: "תערובת תבלינים וזרעים", allergens: [[A.mustard, "unknown"], [A.sesame, "unknown"]] },
    ],
  },
  {
    id: "malabi", category: "desserts", short: "מלבי", name: "כוסות מלבי קוקוס",
    description: "מלבי משיי על בסיס חלב קוקוס, עם סירופ ורדים, פירות יער טריים וניבס קקאו.",
    image: "img/malabi.webp", alt: "כוס מלבי במבט מלמעלה, ועליה תות ואוכמנית",
    variants: [
      { id: "12", label: "מארז 12", price: 180, unit: "box", note: "12 כוסות במארז" },
      { id: "24", label: "מארז 24", price: 340, unit: "box", note: "24 כוסות במארז" },
    ],
    kashrut: "pareve", is_vegetarian: true, is_vegan: true, is_available: true,
    components: [
      { name: "מלבי חלב קוקוס", allergens: [[A.milk, "free"]] },
      { name: "סירופ ורדים", allergens: [] },
      { name: "פירות יער וניבס קקאו", allergens: [[A.nuts, "unknown"]] },
    ],
  },
  {
    id: "tiramisu", category: "desserts", short: "טירמיסו", name: "מגש טירמיסו",
    description: "קרם מסקרפונה, בישקוטים טבולים באספרסו ואבקת קקאו.",
    image: "img/tiramisu.webp", alt: "צלחת במבט מלמעלה: ריבוע טירמיסו מפודר בקקאו",
    variants: tray(120, 220, [6, 12]), kashrut: "dairy", is_vegetarian: true, is_vegan: false, is_available: true,
    components: [
      { name: "קרם מסקרפונה", allergens: [[A.milk, "contains"], [A.egg, "contains"]] },
      { name: "בישקוטים באספרסו", allergens: [[A.gluten, "contains"]] },
      { name: "קקאו", allergens: [] },
    ],
  },
];

// One swap point for the screen. `event` is preview context, not a catalogue route.
export async function loadCatalog() {
  return {
    categories: CATEGORIES,
    dishes: DISHES,
    event: SAMPLE_EVENT,
    guests: GUESTS,
    units: UNITS,
  };
}

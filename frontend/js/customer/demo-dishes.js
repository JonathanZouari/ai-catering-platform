// FICTIONAL demo catalog for the UI prototype only.
// Names, descriptions and prices are invented. They do not come from the backend
// and say nothing about real availability, allergens, kashrut or pricing.

export const CATEGORIES = [
  { id: "all", label: "כל התפריט" },
  { id: "fried", label: "מטוגנים" },
  { id: "wok", label: "מוקפצים" },
  { id: "oven", label: "מהתנור" },
  { id: "salad", label: "סלטים" },
];

// prep: preparation method label (and the illustrated scene used by the dialog's
//       illustration mode, which the menu no longer links to).
// video: AI-generated preparation clip for THIS dish; enables the name hover/tap preview.
//        { src, seconds, startTime?, endTime? } — start/end restrict a segment of a
//        combined source file.
// ingredients/tone/thumb: legacy fields from earlier layouts; unused by the menu.
export const DEMO_DISHES = [
  {
    id: "demo-crispy-cutlets",
    category: "fried",
    name: "שניצלונים פריכים",
    description: "נתחים דקים בציפוי פירורי לחם, מטוגנים עד הזהבה ומוגשים עם פלחי לימון.",
    price: 120,
    unit: "למגש",
    ingredients: ["פירורי לחם", "לימון", "פטרוזיליה"],
    tone: "charcoal",
    prep: { type: "fried", shape: "cutlet" },
    // AI-generated illustrative clip supplied by the product owner. Schnitzel ONLY:
    // never reuse this footage for other dishes.
    video: { src: "/assets/video/schnitzel-preparation.mp4", seconds: 10 },
    thumb: ["#c98a2e", "#d99a3a", "#f4d34a"],
  },
  {
    id: "demo-herb-falafel",
    category: "fried",
    name: "כדורי פלאפל ירוקים",
    description: "חומוס גרוס ועשבי תיבול, מטוגנים לקרום פריך ורך מבפנים.",
    price: 75,
    unit: "למגש",
    ingredients: ["חומוס", "כוסברה", "פטרוזיליה", "כמון"],
    tone: "olive",
    prep: { type: "fried", shape: "ball" },
    video: { src: "/assets/video/falafel-preparation.mp4", seconds: 10 },
    thumb: ["#8a5a24", "#9b6a2c", "#6f9b4a"],
  },
  {
    id: "demo-wok-noodles",
    category: "wok",
    name: "אטריות מוקפצות בירקות",
    description: "אטריות עם פלפלים, גזר ובצל ירוק, מוקפצות על אש גבוהה.",
    price: 95,
    unit: "למגש",
    ingredients: ["אטריות", "פלפל אדום", "גזר", "בצל ירוק"],
    tone: "charcoal",
    prep: { type: "wok" },
    // Combined source file: 0–10 s is falafel, 10.1–20 s is noodles. Only the
    // noodles segment may ever play or be shown for this dish (see video-segment.js).
    video: { src: "/assets/video/noodles-preparation.mp4", startTime: 10.1, endTime: 20, seconds: 10 },
    thumb: ["#e2b25c", "#d9562f", "#5d9b46"],
  },
  {
    id: "demo-roast-roots",
    category: "oven",
    name: "ירקות שורש צלויים",
    description: "בטטה, גזר וסלק בשמן זית ורוזמרין, צלויים בתנור עד לקרמול.",
    price: 85,
    unit: "למגש",
    ingredients: ["בטטה", "סלק", "גזר", "רוזמרין"],
    tone: "wine",
    prep: { type: "oven" },
    // Standalone AI-generated clip for this dish only (10 s, not a combined file).
    video: { src: "/assets/video/roast-roots-preparation.mp4", seconds: 10 },
    thumb: ["#e07b2e", "#9c2f4a", "#f0a541"],
  },
  {
    id: "demo-leaf-salad",
    category: "salad",
    name: "סלט עלים וצנוניות",
    description: "עלים טריים, צנוניות פרוסות ורוטב לימון.",
    price: 60,
    unit: "לקערה",
    ingredients: ["עלים", "צנונית", "לימון", "שמן זית"],
    tone: "ivory",
    prep: null,
    // Standalone AI-generated clip for this dish only (10 s).
    video: { src: "/assets/video/leaf-radish-salad-preparation.mp4", seconds: 10 },
    thumb: ["#6f9b4a", "#4f7f37", "#d24a6a"],
  },
  {
    id: "demo-arabic-salad",
    category: "salad",
    name: "סלט ירקות ערבי",
    description: "עגבניות ומלפפונים קצוצים דק, בצל ופטרוזיליה, בתיבול לימון טרי ושמן זית.",
    price: 60,
    unit: "לקערה",
    ingredients: ["עגבניות", "מלפפונים", "פטרוזיליה", "לימון"],
    tone: "olive",
    prep: null,
    // Standalone AI-generated clip for this dish only (10 s).
    video: { src: "/assets/video/arabic-salad-preparation.mp4", seconds: 10 },
    thumb: ["#c84a36", "#4f7f37", "#e9ca68"],
  },
];

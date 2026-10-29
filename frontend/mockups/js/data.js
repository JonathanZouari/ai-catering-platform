/* Fake sample data for the mockups. No backend calls anywhere. */
window.MOCK = {
  business: { name: "המטבח של סבתא" },
  today: "2026-10-29",
  eventTypes: [
    { id: "batmitzvah", label: "בר/בת מצווה" },
    { id: "birthday", label: "יום הולדת" },
    { id: "shabbat", label: "ארוחת שבת" },
    { id: "family", label: "אירוע משפחתי" },
    { id: "other", label: "אחר" }
  ],
  slots: [
    { id: "s1", label: "08:00–10:00" },
    { id: "s2", label: "10:00–12:00" },
    { id: "s3", label: "12:00–14:00" },
    { id: "s4", label: "16:00–18:00" }
  ],
  // Every Saturday is blocked in code (weekday 6); these are extra blocked dates.
  blockedDates: ["2027-01-12", "2027-01-21"],
  // First and last month the calendar can show.
  calendarRange: { from: [2026, 10], to: [2027, 2] },
  zones: [
    { id: "raanana", label: "רעננה", fee: 60 },
    { id: "kfarsaba", label: "כפר סבא", fee: 60 },
    { id: "herzliya", label: "הרצליה", fee: 80 },
    { id: "telaviv", label: "תל אביב", fee: 100 }
  ],
  pickupPoint: "רחוב הרימון 8, כפר סבא",
  event: {
    type: "batmitzvah",
    date: "2027-01-15",
    slot: "s2",
    adults: 40,
    children: 15,
    vegetarian: 6,
    vegan: 2,
    notes: "",
    fulfillment: "delivery",
    address: "רחוב אחוזה 120, רעננה",
    zone: "raanana"
  },
  categories: [
    { id: "starters", label: "פתיחה וסלטים" },
    { id: "mains", label: "עיקריות" },
    { id: "sides", label: "תוספות" },
    { id: "pastry", label: "מאפים וקינוחים" }
  ],
  // unit: tray | kg | item. step = how much one tap adds. allergens: null = not verified.
  dishes: [
    { id: "hummus", cat: "starters", name: "חומוס ביתי", desc: "חומוס חלק עם טחינה ושמן זית.", price: 85, unit: "tray", step: 1, kashrut: "pareve", veg: "vegan", allergens: ["שומשום"], photo: null },
    { id: "chopped", cat: "starters", name: "סלט ירקות קצוץ", desc: "מלפפון, עגבנייה ובצל בלימון ושמן זית.", price: 70, unit: "tray", step: 1, kashrut: "pareve", veg: "vegan", allergens: null, photo: null },
    { id: "falafel", cat: "starters", name: "פלאפל ביתי", desc: "כדורי חומוס פריכים, עם טחינה בצד.", price: 90, unit: "tray", step: 1, kashrut: "pareve", veg: "vegan", allergens: ["שומשום"],
      photo: { src: "photos/falafel.jpg", alt: "כדורי פלאפל בקערת חרס עם רוטב טחינה", pos: "50% 30%" } },
    { id: "salmon", cat: "starters", name: "כריכוני סלמון ואבוקדו", desc: "חצאי לחמניות קלויות, אבוקדו וסלמון מעושן.", price: 14, unit: "item", step: 6, kashrut: "pareve", veg: null, allergens: ["דגים", "גלוטן"],
      photo: { src: "photos/salmon.jpg", alt: "כריכוני סלמון מעושן ואבוקדו על צלחת לבנה", pos: "50% 80%" } },
    { id: "schnitzel", cat: "mains", name: "שניצל עוף פריך", desc: "חזה עוף בציפוי פירורי לחם, מטוגן עד הזהבה.", price: 120, unit: "kg", step: 1, kashrut: "meat", veg: null, allergens: ["גלוטן", "ביצים"],
      photo: { src: "photos/schnitzel.jpg", alt: "שניצל עוף פריך על פירה, עם סלט", pos: "50% 64%" } },
    { id: "stew", cat: "mains", name: "תבשיל בקר ברוזמרין", desc: "נתחי בקר בבישול ארוך, ברוטב יין ועשבי תיבול.", price: 165, unit: "kg", step: 1, kashrut: "meat", veg: null, allergens: null,
      photo: { src: "photos/stew.jpg", alt: "תבשיל בקר בסיר כתום עם ענף רוזמרין", pos: "50% 68%" } },
    { id: "shakshuka", cat: "mains", name: "שקשוקה עם גבינה", desc: "רוטב עגבניות חריף, ביצים וקוביות גבינה.", price: 90, unit: "tray", step: 1, kashrut: "dairy", veg: "vegetarian", allergens: ["חלב", "ביצים"],
      photo: { src: "photos/shakshuka.jpg", alt: "שקשוקה בתבנית ברזל עם גבינה ופטרוזיליה", pos: "50% 72%" } },
    { id: "rice", cat: "sides", name: "אורז לבן עם שקדים", desc: "אורז פלפל מבושל, עם שקדים קלויים.", price: 60, unit: "tray", step: 1, kashrut: "pareve", veg: "vegan", allergens: ["שקדים"], photo: null },
    { id: "veg", cat: "sides", name: "ירקות קלויים", desc: "ירקות עונה בתנור, עם שמן זית וטחינה.", price: 75, unit: "tray", step: 1, kashrut: "pareve", veg: "vegan", allergens: ["שומשום"], photo: null },
    { id: "burekas", cat: "pastry", name: "בורקס תפוחי אדמה", desc: "בצק עלים פריך במילוי תפוחי אדמה.", price: 6, unit: "item", step: 10, kashrut: "pareve", veg: "vegetarian", allergens: ["גלוטן", "ביצים"], photo: null },
    { id: "cake", cat: "pastry", name: "עוגת שוקולד", desc: "עוגה רכה בציפוי שוקולד מריר.", price: 90, unit: "item", step: 1, kashrut: "pareve", veg: "vegetarian", allergens: ["גלוטן", "ביצים", "סויה"], photo: null }
  ],
  seedItems: [
    { dishId: "falafel", qty: 2 },
    { dishId: "salmon", qty: 30 },
    { dishId: "schnitzel", qty: 4 },
    { dishId: "stew", qty: 3 },
    { dishId: "rice", qty: 3 },
    { dishId: "burekas", qty: 40 },
    { dishId: "cake", qty: 2 }
  ]
};

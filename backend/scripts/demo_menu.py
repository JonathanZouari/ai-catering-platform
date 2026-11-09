"""Sample menu for trying the site, not real business data. Photos are in demo_photos/.

Each dish: name, price, unit label, description, photo, (kashrut, vegetarian, vegan),
calories, gluten status. Used by dev_server and seed_supabase.
"""

from pathlib import Path

from app.models.enums import CategoryType, KashrutClass

PHOTOS = Path(__file__).with_name("demo_photos")
K = KashrutClass
DEMO_MENU = {
    ("מנות עיקריות", CategoryType.MAIN): [
        (
            "בטטה צלויה",
            "160",
            "10 סועדים",
            "בטטה בתנור עם שעועית, סלסה ושמנת חמוצה.",
            "potato.jpg",
            (K.DAIRY, True, False),
            240,
            None,
        ),
        (
            "מנת השף",
            "200",
            None,
            "מנה חמה משתנה לפי העונה וחומרי הגלם הטריים ביותר בשוק.",
            "chef.jpg",
            (K.MEAT, False, False),
            None,
            None,
        ),
        (
            "פסטה ברוטב עגבניות",
            "180",
            None,
            "פסטה, עגבניות שרי, בזיליקום וגבינה לבנה איטלקית.",
            "pasta.jpg",
            (K.DAIRY, True, False),
            210,
            "contains",
        ),
    ],
    ("סלטים", CategoryType.SALAD): [
        (
            "מגש ירקות העונה",
            "120",
            None,
            "ירקות טריים קלופים וחתוכים עם מטבלי טחינה ועשבי תיבול.",
            "veg.jpg",
            (K.PAREVE, True, True),
            120,
            "free",
        ),
        (
            "קערת בריאות",
            "90",
            "קערה אישית",
            "קינואה, ירקות צלויים, אדממה ורוטב לימון.",
            "bowl.jpg",
            (K.PAREVE, True, True),
            None,
            None,
        ),
    ],
    ("תוספות חמות", CategoryType.SIDE): [
        ("אורז לבן", "60", None, None, None, None, None, None),
    ],
    ("קינוחים", CategoryType.DESSERT): [
        (
            "מגש פטיפורים ומראות שוקולד",
            "190",
            "24 יחידות",
            "כיפות מוס שוקולד, טארטלטים פריכים וכוסות שוט.",
            "petit.jpg",
            (K.DAIRY, True, False),
            None,
            "contains",
        ),
        (
            "פחזניות שו קראקלין",
            "175",
            "20 יחידות",
            "פחזניות במעטפת קראקלין פריכה עם קרם וניל.",
            "choux.jpg",
            None,
            None,
            None,
        ),
        (
            "פבלובה אישית ומגש פירות",
            "160",
            "16 יחידות",
            "קינוחי מרנג פריכים עם פירות יער טריים.",
            "pavlova.jpg",
            (K.PAREVE, True, False),
            None,
            "free",
        ),
        (
            "מגדל מקרונים",
            "185",
            "30 יחידות",
            "מבחר מקרונים במגוון טעמים.",
            "macaron.jpg",
            (K.PAREVE, True, False),
            None,
            "free",
        ),
        (
            "עוגת אירועים מעוצבת",
            "280",
            "קוטר 24 ס״מ",
            "עוגת שכבות בציפוי קרם מסקרפונה ופירות יער.",
            "cake.jpg",
            (K.DAIRY, True, False),
            None,
            "contains",
        ),
    ],
}

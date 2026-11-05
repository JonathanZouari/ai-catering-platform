// Single money/date formatter. Currency is OPEN_DECISIONS #17, so it lives in one place.
const CURRENCY = "ILS";
const LOCALE = "he-IL";
const whole = new Intl.NumberFormat(LOCALE, { style: "currency", currency: CURRENCY, maximumFractionDigits: 0 });
const cents = new Intl.NumberFormat(LOCALE, { style: "currency", currency: CURRENCY, minimumFractionDigits: 2, maximumFractionDigits: 2 });
// he-IL renders "‏165 ₪" (RLM + no-break space). Whole amounts drop decimals; fractional ones show two.
export const money = (value) => (Number.isInteger(value) ? whole : cents).format(value);
// For HTML templates: isolate every amount so ₪, digits and × never reorder against neighbouring text.
export const moneyHTML = (value) => `<bdi class="money">${money(value)}</bdi>`;
export const KASHRUT = { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" };
// "יום ה׳, 19 בנובמבר" (short) and "יום ה׳, 19 בנובמבר 2026" (long)
export const dateShort = (d) => new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "long" }).format(d);
export const dateLong = (d) => new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "long", year: "numeric" }).format(d);

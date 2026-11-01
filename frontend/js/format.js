// Display formatting. One locale and currency for the whole UI (OPEN_DECISIONS #12, #17).
export const LOCALE = "he-IL";
export const CURRENCY = "ILS";

const money = new Intl.NumberFormat(LOCALE, { style: "currency", currency: CURRENCY, maximumFractionDigits: 0 });
const date = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "numeric", year: "numeric" });
const weekdayDate = new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "numeric", year: "numeric" });
const dateTime = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });

export const formatPrice = (amount) => money.format(amount);
export const formatSignedPrice = (amount) => (amount > 0 ? "+" : "") + money.format(amount);
export const formatDate = (iso) => date.format(new Date(iso));
export const formatWeekdayDate = (iso) => weekdayDate.format(new Date(iso));
export const formatDateTime = (iso) => dateTime.format(new Date(iso));

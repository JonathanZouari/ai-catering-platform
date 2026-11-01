// OPEN #17 (currency) and #14 (VAT/rounding): ₪ with whole numbers is a placeholder format.
export const ils = (n) => `₪${Math.round(n).toLocaleString("en-US")}`;
export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
export const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

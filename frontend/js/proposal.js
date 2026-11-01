// Display logic for the order screen until the catalog and AI APIs exist.
// shortcut: sample prices from the PRD example, replace with backend pricing in Phase 2.
const BASE_TOTAL = 6540;
const VEGAN_DISH = 75;
const SAMPLE_EVENT = { name: "שבת חתן", guests: 80, vegans: 5 };

const isCount = (n) => Number.isInteger(n) && n >= 0;

// sessionStorage is user-editable, so anything malformed falls back to the sample.
export function readEvent(raw) {
  try {
    const { name, guests, vegans } = JSON.parse(raw);
    if (typeof name === "string" && name && isCount(guests) && guests > 0 && isCount(vegans) && vegans <= guests) {
      return { name: name.slice(0, 40), guests, vegans };
    }
  } catch {
    // Falls through to the sample event.
  }
  return SAMPLE_EVENT;
}

export const totalFor = ({ vegans }, added) => BASE_TOTAL + (added ? vegans * VEGAN_DISH : 0);

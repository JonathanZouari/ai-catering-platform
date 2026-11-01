// Guest counting rules for the event form. Subgroups are "out of" the total,
// so a guest is never counted twice.
// shortcut: 500 is a placeholder ceiling, replace when the business sets one.
export const MAX_GUESTS = 500;

const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

export function setGuests(state, n) {
  const guests = clamp(n, 1, MAX_GUESTS);
  const vegetarians = Math.min(state.vegetarians, guests);
  return {
    ...state,
    guests,
    kids: Math.min(state.kids, guests),
    vegetarians,
    vegans: Math.min(state.vegans, guests - vegetarians),
  };
}

export const setKids = (state, n) => ({ ...state, kids: clamp(n, 0, state.guests) });
export const setVegetarians = (state, n) => ({ ...state, vegetarians: clamp(n, 0, state.guests - state.vegans) });
export const setVegans = (state, n) => ({ ...state, vegans: clamp(n, 0, state.guests - state.vegetarians) });

// What still blocks moving on, or "" when the form is complete.
export function missingField({ date, delivery, address }, today) {
  if (!date) return "נשאר לבחור תאריך";
  if (date < today) return "נשאר לבחור תאריך עתידי";
  if (delivery && !address.trim()) return "נשאר למלא כתובת למשלוח";
  return "";
}

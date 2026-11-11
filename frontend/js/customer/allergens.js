// A missing allergen relation never establishes absence, including legacy [] lists.
export function allergenStatus(dish, name) {
  const entry = dish?.allergenStatuses?.find((value) => value.name === name);
  if (entry && ['contains', 'free', 'unknown'].includes(entry.status)) return entry.status;
  return dish?.allergens?.includes(name) ? 'contains' : 'unknown';
}

export function allergenSummary(dish) {
  const entries = dish.allergenStatuses;
  if (!Array.isArray(entries) || !entries.length) {
    return {contains: dish.allergens ?? [], free: [], unknown: [], incomplete: true};
  }
  return {
    contains: entries.filter(a => a.status === 'contains').map(a => a.name),
    free: entries.filter(a => a.status === 'free').map(a => a.name),
    unknown: entries.filter(a => !['contains','free'].includes(a.status)).map(a => a.name),
    incomplete: entries.some(a => !['contains','free'].includes(a.status)),
  };
}

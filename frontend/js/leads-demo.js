import { h, fill } from './lib/dom.js';

const root = document.getElementById('leads');
const status = document.getElementById('status');
const filter = document.getElementById('filter');
const sort = document.getElementById('sort');
const percent = new Intl.NumberFormat('he-IL', { style: 'percent', maximumFractionDigits: 0 });
let leads = [];

function render() {
  const visible = leads.filter(row => filter.value === 'all' || row.demo_class === filter.value);
  if (sort.value === 'score') visible.sort((a, b) => b.demo_probability - a.demo_probability);
  fill(root, visible.map(row => h('article', {},
    h('h2', { text: row.name }),
    h('p', { class: 'score', text: `ציון הדגמה: ${percent.format(row.demo_probability)}` }),
    h('p', { text: row.demo_class === 'higher' ? 'סיווג: סיכוי גבוה יותר בהדגמה' : 'סיווג: סיכוי נמוך יותר בהדגמה' }),
    h('dl', {},
      h('dt', { text: 'אורחים' }), h('dd', { text: row.guest_count }),
      h('dt', { text: 'ימים עד האירוע' }), h('dd', { text: row.days_until_event ?? 'לא נמסר' }),
      h('dt', { text: 'תקציב לאורח' }), h('dd', { text: row.budget_per_guest == null ? 'לא נמסר' : `${row.budget_per_guest} ₪` })),
    h('p', { dir: 'ltr', text: row.email }),
    h('p', { text: 'פנייה חדשה לדוגמה — לא נשלחת הודעה ולא נוצרת הזמנה.' })
  )));
  status.textContent = `מוצגות ${visible.length} פניות סינתטיות`;
}
filter.addEventListener('change', render);
sort.addEventListener('change', render);
try {
  const response = await fetch('/demo/leads.json');
  if (!response.ok) throw new Error('Demo unavailable');
  const data = await response.json();
  if (data.synthetic_only !== true || data.leads.some(row => row.is_synthetic !== true)) throw new Error('Synthetic data only');
  leads = data.leads;
  render();
} catch {
  status.textContent = 'לא ניתן לטעון את נתוני ההדגמה. נסו לרענן את הדף.';
}

import { parseCloudConfig } from './helpers.js';

const status = document.getElementById('status');
const form = document.getElementById('recovery');
const password = document.getElementById('password');
const confirm = document.getElementById('confirm');
const button = form.querySelector('button');
// Accept only a recovery callback, not a previously stored staff session.
const isRecovery = new URLSearchParams(location.hash.slice(1)).get('type') === 'recovery';

async function boot() {
  if (!isRecovery) {
    history.replaceState(null, '', location.pathname);
    status.textContent = 'יש לפתוח את הקישור מתוך הודעת שחזור הסיסמה. קישור חסר או שפג תוקפו אינו מאפשר החלפה.';
    return;
  }
  const response = await fetch('/api/cloud-config', { cache: 'no-store' });
  if (!response.ok) throw new Error('config');
  const config = parseCloudConfig(await response.json());
  if (!config.configured) throw new Error('config');
  const client = window.supabase.createClient(config.url, config.publishableKey, {
    auth: { persistSession: false, detectSessionInUrl: true, autoRefreshToken: false, flowType: 'implicit' },
  });
  const initialized = await client.auth.initialize();
  history.replaceState(null, '', location.pathname);
  if (initialized.error) throw new Error('expired');
  const { data, error } = await client.auth.getUser();
  if (error || !data.user) throw new Error('expired');
  status.textContent = 'בחר סיסמה חדשה לחשבון שלך.';
  form.hidden = false;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (password.value !== confirm.value) {
      status.textContent = 'שתי הסיסמאות אינן זהות.';
      return;
    }
    if (!form.reportValidity()) return;
    button.disabled = true;
    try {
      const { error } = await client.auth.updateUser({ password: password.value });
      if (error) {
        status.textContent = 'הסיסמה לא עודכנה. נסה סיסמה חזקה ושונה מהקודמת; אם הקישור פג, בקש קישור חדש.';
        return;
      }
      form.reset();
      form.hidden = true;
      await client.auth.signOut({ scope: 'local' });
      status.textContent = 'הסיסמה עודכנה. כעת אפשר לחזור לכניסת הצוות ולהתחבר עם הסיסמה החדשה.';
    } catch {
      status.textContent = 'לא ניתן להשלים את הבקשה כרגע. בדוק את החיבור ונסה שוב.';
    } finally {
      button.disabled = false;
    }
  });
}

boot().catch(() => {
  history.replaceState(null, '', location.pathname);
  form.hidden = true;
  status.textContent = 'לא ניתן לאמת את קישור השחזור. ייתכן שפג תוקפו או שחיבור הרשת אינו זמין.';
});

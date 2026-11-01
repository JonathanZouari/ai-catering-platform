// Order assistant (C4). Local rules stand in for the backend agent until Phase 4:
// it reads the table, proposes a diff, and the order changes only on approval.
import { DISH_BY_ID, CATEGORIES, money, recommendedQty, balance } from "./data.js";
import { coverage, guestsOf, totals } from "./order.js";

const SUGGESTIONS = ["מה חסר על השולחן?", "יש לנו הרבה ילדים", "חלק מהאורחים טבעונים", "איך מורידים קצת מהמחיר?"];

export function createAssistant({ root, store, onOpenChange }) {
  const chat = root.querySelector("[data-bind=chat]");
  const suggest = root.querySelector("[data-bind=suggest]");
  const form = root.querySelector("[data-bind=chat-form]");
  const input = form.querySelector("input");
  let greeted = false;
  let proposalEl = null;

  suggest.innerHTML = SUGGESTIONS.map((s) => `<button class="chip" type="button">${s}</button>`).join("");
  suggest.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) ask(b.textContent);
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) { input.focus(); return; }
    input.value = "";
    ask(text);
  });

  function bubble(text, who = "bot") {
    const li = document.createElement("li");
    li.className = `msg msg--${who}`;
    li.textContent = text;
    chat.append(li);
    chat.scrollTop = chat.scrollHeight;
    return li;
  }

  function typing() {
    const li = document.createElement("li");
    li.className = "msg msg--bot msg--typing";
    li.setAttribute("aria-label", "העוזר כותב");
    li.innerHTML = "<span></span><span></span><span></span>";
    chat.append(li);
    chat.scrollTop = chat.scrollHeight;
    return li;
  }

  function ask(text) {
    bubble(text, "user");
    const t = typing();
    setTimeout(() => {
      t.remove();
      const reply = think(text, store.get());
      bubble(reply.text);
      if (reply.changes?.length) showProposal(reply);
    }, 650 + Math.random() * 400);
  }

  function showProposal({ changes, title }) {
    const s = store.get();
    if (s.proposal) store.resolveProposal(false);
    // The card must show everything approval would change, including dishes in
    // the same course that rebalance around the new quantities.
    const requested = new Set(changes.map((c) => c.id));
    const after = { ...s.items };
    const manual = { ...s.manual };
    for (const c of changes) { if (c.to <= 0) { delete after[c.id]; delete manual[c.id]; } else { after[c.id] = c.to; manual[c.id] = true; } }
    const settled = balance(after, guestsOf(s), manual);
    changes = [...new Set([...Object.keys(s.items), ...Object.keys(settled)])]
      .map((id) => ({ id, from: s.items[id] ?? 0, to: settled[id] ?? 0 }))
      .filter((c) => c.from !== c.to);
    if (!changes.length) return;
    const before = totals(s).total;
    const next = totals(s, settled).total;
    const diff = next - before;
    // what the assistant asked for is pinned; the rest stays free to rebalance later
    store.propose({ changes, title, pinned: changes.filter((c) => requested.has(c.id) && c.to > 0).map((c) => c.id) });

    const li = document.createElement("li");
    li.className = "proposal";
    li.innerHTML = `
      <span class="proposal__title"><i class="ph ph-sparkle" aria-hidden="true"></i>${title}</span>
      <ul>${changes.map((c) => {
        const d = DISH_BY_ID[c.id];
        const label = c.from === 0 ? `הוספה, ${c.to}` : c.to <= 0 ? "הסרה" : `מ־${c.from} ל־${c.to}`;
        return `<li><span>${d.name}</span><b class="num">${label}</b></li>`;
      }).join("")}</ul>
      <div class="proposal__total"><span>סה״כ חדש <s class="num">${money(before)}</s> <b class="num">${money(next)}</b></span><span class="pill-diff num ${diff >= 0 ? "up" : "down"}">${diff >= 0 ? "תוספת" : "חיסכון"} ${money(Math.abs(diff))}</span></div>
      <div class="proposal__actions">
        <button class="btn btn--sm btn--primary" type="button" data-accept>לאשר</button>
        <button class="btn btn--sm" type="button" data-reject>לא עכשיו</button>
      </div>`;
    chat.append(li);
    chat.scrollTop = chat.scrollHeight;
    proposalEl?.querySelector(".proposal__actions") && settle(proposalEl, "replaced");
    proposalEl = li;
    li.querySelector("[data-accept]").addEventListener("click", () => store.resolveProposal(true));
    li.querySelector("[data-reject]").addEventListener("click", () => store.resolveProposal(false));
  }

  function settle(el, kind) {
    const map = {
      applied: ["ph-check-circle", "הוחל על השולחן"],
      rejected: ["ph-x-circle", "נדחה, השולחן לא השתנה"],
      expired: ["ph-clock-counter-clockwise", "ההזמנה השתנתה בינתיים. אפשר לבקש שוב."],
      replaced: ["ph-arrows-clockwise", "הוחלף בהצעה חדשה"],
    };
    const [icon, text] = map[kind];
    const hadFocus = el.contains(document.activeElement);
    el.querySelector(".proposal__actions")?.replaceWith(Object.assign(document.createElement("span"), {
      className: "proposal__state", innerHTML: `<i class="ph ${icon}" aria-hidden="true"></i>${text}`,
    }));
    if (hadFocus) input.focus();
  }

  store.subscribe((s, change) => {
    if (!proposalEl) return;
    if (change.type === "proposal-applied") settle(proposalEl, "applied");
    else if (change.type === "proposal-rejected") settle(proposalEl, "rejected");
    else if (change.type === "proposal-expired") settle(proposalEl, "expired");
    else return;
    proposalEl = null;
  });

  return {
    open() {
      root.hidden = false;
      onOpenChange?.(true);
      if (!greeted) {
        greeted = true;
        const g = guestsOf(store.get());
        bubble(`שלום. אני רואה שולחן ל־${g.adults + g.children} אורחים. אפשר לשאול אותי מה חסר, לבקש התאמה לילדים או לטבעונים, או לבקש להוריד מחיר. כל שינוי מחכה לאישור שלכם.`);
      }
      setTimeout(() => input.focus(), 60);
    },
    close() { root.hidden = true; onOpenChange?.(false); },
    ask,
  };
}

// --- rules ---------------------------------------------------------------

const has = (t, ...words) => words.some((w) => t.includes(w));

function change(s, id, to) {
  return { id, from: s.items[id] ?? 0, to };
}

function think(text, s) {
  const t = text.replace(/[?!.,]/g, " ");
  const g = guestsOf(s);
  const items = s.items;

  if (has(t, "ילד", "ילדים", "קטנים")) {
    const changes = [];
    const kids = recommendedQty(DISH_BY_ID.schnitzel, g, items);
    if ((items.schnitzel ?? 0) < kids) changes.push(change(s, "schnitzel", kids));
    if (!items.potatoes) changes.push(change(s, "potatoes", recommendedQty(DISH_BY_ID.potatoes, g, items)));
    if (!items.fruit) changes.push(change(s, "fruit", Math.max(1, Math.ceil(g.children / 12))));
    if (!changes.length) return { text: `ל־${g.children} ילדים השולחן כבר מכוסה: יש שניצלונים, תוספת שילדים אוכלים ופירות.` };
    return {
      title: `התאמה ל־${g.children} ילדים`,
      text: `ל־${g.children} ילדים הייתי מוסיף מה שילדים באמת אוכלים באירועים. הסימון המקווקו על השולחן מראה איפה זה יישב.`,
      changes,
    };
  }

  if (has(t, "טבעונ", "צמחונ", "בלי בשר")) {
    const changes = [];
    for (const id of ["quinoa", "eggplant", "mujadara"]) {
      if (!items[id]) changes.push(change(s, id, Math.max(1, Math.ceil(recommendedQty(DISH_BY_ID[id], g, items) * 0.6))));
      else changes.push(change(s, id, items[id] + 1));
      if (changes.length === 2) break;
    }
    return {
      title: "חיזוק המנות הטבעוניות",
      text: "כדי שלאורחים הטבעוניים תהיה ארוחה מלאה ולא רק סלטים, הייתי מחזק שתי מנות טבעוניות משביעות.",
      changes,
    };
  }

  if (has(t, "מחיר", "יקר", "לחסוך", "להוריד", "תקציב", "זול")) {
    const lines = totals(s).lines.sort((a, b) => b.line - a.line);
    if (!lines.length) return { text: "השולחן עוד ריק, אז אין מה להוריד. הוסיפו מנות ואחזור עם הצעה." };
    const changes = [];
    for (const l of lines) {
      const rec = recommendedQty(l.dish, g, s.items);
      if (l.qty > rec) changes.push(change(s, l.dish.id, rec));
    }
    if (!changes.length) {
      const top = lines[0];
      if (top.qty > 1) changes.push(change(s, top.dish.id, top.qty - 1));
    }
    if (!changes.length) return { text: "הכמויות כבר צמודות למספר האורחים. אפשר להחליף מנה יקרה בזולה, למשל סלמון בפרגיות." };
    return {
      title: "חיסכון בלי שהשולחן ירגיש ריק",
      text: "הורדתי רק מנות שהכמות שלהן מעל מה שמספר האורחים צריך. אף אחד לא יישאר רעב.",
      changes,
    };
  }

  // default: find the weakest course and fill it
  const cov = coverage(s);
  const missing = CATEGORIES.filter((c) => !(cov.byCat[c.id] > 0));
  const picks = { bread: "challah", salad: "hummus", main: "chicken", side: "potatoes", dessert: "fruit" };
  if (missing.length) {
    const changes = missing.slice(0, 3).map((c) => change(s, picks[c.id], recommendedQty(DISH_BY_ID[picks[c.id]], g, items)));
    return {
      title: "השלמת השולחן",
      text: `חסרות על השולחן ${missing.map((c) => c.label).join(", ")}. הנה השלמה במנות הכי מבוקשות אצלנו.`,
      changes,
    };
  }
  const short = CATEGORIES.map((c) => ({ c, have: cov.byCat[c.id] ?? 0 })).filter((x) => x.have < cov.need).sort((a, b) => a.have - b.have)[0];
  if (short) {
    const id = Object.keys(items).find((i) => DISH_BY_ID[i].category === short.c.id);
    return {
      title: `עוד קצת ${short.c.label}`,
      text: `${short.c.label} מספיקות כרגע לכ־${Math.floor(short.have)} מנות מתוך ${Math.ceil(cov.need)}. מגש אחד נוסף סוגר את הפער.`,
      changes: [change(s, id, items[id] + 1)],
    };
  }
  return { text: "השולחן נראה מאוזן: יש מכל סוג, והכמויות מכסות את כל האורחים. אפשר להמשיך לסיכום." };
}

// Live records for authorized staff: table list, paginated grid and the live-update channel.
import { clear, errorBlock, h, ident } from "./dom.js";
import { openRowForm } from "./forms.js";
import {
  DISH_BUCKET,
  PAGE_SIZES,
  SIGNED_URL_SECONDS,
  createRequestGuard,
  describeError,
  formatCell,
  isLtrCell,
  jsonCellText,
  pageInfo,
  pageRange,
} from "./helpers.js";
import { createRealtimeController } from "./realtime.js";
import { GROUPS, RELATIONS, TABLES, getTable, labelSelect, primaryKey, selectList } from "./schema.js";

const LIVE_STATUS = {
  idle: { text: "עדכונים חיים: כבויים", className: "" },
  connecting: { text: "עדכונים חיים: מתחבר…", className: "badge-warning" },
  live: { text: "עדכונים חיים: מחובר", className: "badge-green" },
  offline: { text: "עדכונים חיים: מנותק. הנתונים עשויים להיות ישנים.", className: "badge-danger" },
};

const rowKey = (table, row) => primaryKey(table).map((key) => row[key]).join("|");

export function createDataView({ client, container, onSessionLost }) {
  const state = {
    table: TABLES[0],
    page: 0,
    pageSize: PAGE_SIZES[0],
    rows: [],
    count: 0,
    loaded: false,
    loading: false,
    error: null,
    lookups: {},
    images: {},
    loadedAt: null,
  };
  const guard = createRequestGuard();
  const signedUrlCache = new Map();
  let alive = true;
  let dialog = null;

  /* ---------- static layout ---------- */

  const tableButtons = new Map();
  const sidebar = h(
    "nav",
    { class: "table-nav", "aria-label": "טבלאות" },
    GROUPS.map((group) =>
      h(
        "div",
        { class: "table-nav-group" },
        h("h2", { class: "group-title" }, group.label),
        TABLES.filter((table) => table.group === group.id && !table.hiddenFromData).map((table) => {
          const button = h(
            "button",
            { type: "button", class: "table-link", onclick: () => selectTable(table.name) },
            h("span", { class: "cell-title" }, table.label),
            ident(table.name),
          );
          tableButtons.set(table.name, button);
          return button;
        }),
      ),
    ),
  );

  const titleArea = h("div", { class: "data-title" });
  const toolbar = h("div", { class: "data-toolbar" });
  const liveBadge = h("span", { class: "badge", role: "status" });
  const loadedLabel = h("span", { class: "muted small" });
  const messageArea = h("div", {});
  const gridArea = h("div", { class: "table-scroll grid-area", tabindex: "0", role: "region", "aria-label": "רשומות הטבלה" });
  const pagerArea = h("div", { class: "pager" });
  container.append(
    h("div", { class: "data-layout" }, sidebar, h("section", { class: "data-main" }, titleArea, toolbar, h("div", { class: "live-row" }, liveBadge, loadedLabel), messageArea, gridArea, pagerArea)),
  );

  const realtime = createRealtimeController({
    client,
    onRefresh: () => load({ quiet: true }),
    onStatus: (status) => {
      const info = LIVE_STATUS[status];
      liveBadge.textContent = info.text;
      liveBadge.className = `badge ${info.className}`;
    },
  });

  const onOnline = () => realtime.networkChanged(true);
  const onOffline = () => realtime.networkChanged(false);
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);

  /* ---------- reads ---------- */

  async function load({ quiet = false } = {}) {
    const token = guard.next();
    const table = state.table;
    state.loading = true;
    if (!quiet) {
      state.error = null;
      renderGrid();
      renderMessage();
    }
    const { from, to } = pageRange(state.page, state.pageSize);
    let query = client.from(table.name).select(selectList(table), { count: "exact" });
    for (const key of primaryKey(table)) {
      // Newest first for numbered records; a full key keeps paging stable.
      query = query.order(key, { ascending: table.columns.find((c) => c.name === key).type !== "id" });
    }
    const result = await query.range(from, to);
    if (!alive || !guard.isCurrent(token)) return;
    state.loading = false;

    if (result.error) {
      // Asking past the last page after rows were removed: return to the first page.
      if (result.error.code === "PGRST103" && state.page > 0) {
        state.page = 0;
        load({ quiet });
        return;
      }
      state.error = result.error;
      renderGrid();
      renderMessage();
      if (result.error.code === "PGRST301" || result.error.code === "PGRST303") onSessionLost();
      return;
    }

    state.rows = result.data ?? [];
    state.count = result.count ?? 0;
    state.error = null;
    state.loaded = true;
    state.loadedAt = new Date();
    // Rows can vanish between pages: step back instead of showing an empty page.
    if (state.rows.length === 0 && state.page > 0) {
      state.page = Math.max(0, Math.ceil(state.count / state.pageSize) - 1);
      load({ quiet });
      return;
    }
    await Promise.all([loadLookups(token, table), loadImages(token, table)]);
    if (!alive || !guard.isCurrent(token)) return;
    renderGrid();
    renderMessage();
  }

  // Replaces foreign key numbers with readable names. If this fails the numbers still show.
  async function loadLookups(token, table) {
    const relations = RELATIONS.filter((relation) => relation.from === table.name && labelSelect(getTable(relation.to)));
    const lookups = {};
    await Promise.all(
      relations.map(async (relation) => {
        const column = relation.columns[0];
        const ids = [...new Set(state.rows.map((row) => row[column]).filter((value) => value !== null && value !== undefined))];
        if (ids.length === 0) return;
        const target = getTable(relation.to);
        const { data, error } = await client.from(target.name).select(labelSelect(target)).in("id", ids);
        if (!error) lookups[column] = Object.fromEntries((data ?? []).map((row) => [row.id, row.label]));
      }),
    );
    if (guard.isCurrent(token)) state.lookups = lookups;
  }

  async function loadImages(token, table) {
    if (table.name !== "dishes") {
      state.images = {};
      return;
    }
    const now = Date.now();
    const paths = state.rows.map((row) => row.image_path).filter(Boolean);
    const missing = paths.filter((path) => !(signedUrlCache.get(path)?.expires > now));
    const failed = new Set();
    if (missing.length > 0) {
      const { data, error } = await client.storage.from(DISH_BUCKET).createSignedUrls(missing, SIGNED_URL_SECONDS);
      if (error) missing.forEach((path) => failed.add(path));
      for (const item of data ?? []) {
        if (item.signedUrl) signedUrlCache.set(item.path, { url: item.signedUrl, expires: now + (SIGNED_URL_SECONDS - 300) * 1000 });
        else failed.add(item.path);
      }
    }
    if (!guard.isCurrent(token)) return;
    state.images = Object.fromEntries(paths.map((path) => [path, failed.has(path) ? null : signedUrlCache.get(path)?.url ?? null]));
  }

  /* ---------- rendering ---------- */

  function renderTitle() {
    const table = state.table;
    clear(titleArea).append(
      h("h2", {}, table.label),
      ident(table.name),
      h("p", { class: "muted" }, table.description),
    );
    const canEdit = table.editable === true;
    clear(toolbar).append(
      canEdit
        ? h("button", { class: "btn btn-primary", type: "button", onclick: () => openForm(null) }, "רשומה חדשה")
        : h("p", { class: "notice notice-inline" }, table.readOnlyReason),
      h("button", { class: "btn btn-secondary", type: "button", onclick: () => load() }, "רענון"),
    );
  }

  function renderMessage() {
    clear(messageArea);
    if (state.error) {
      const description = describeError(state.error);
      messageArea.append(
        errorBlock(
          state.loaded ? { ...description, message: `${description.message} הרשומות המוצגות הן מהטעינה הקודמת.` } : description,
          { onRetry: () => load() },
        ),
      );
    }
    loadedLabel.textContent = state.loadedAt
      ? `נטען לאחרונה בשעה ${state.loadedAt.toLocaleTimeString("he-IL", { timeZone: "Asia/Jerusalem" })}`
      : "";
  }

  function cellContent(column, row) {
    const value = row[column.name];
    if (value === null || value === undefined) {
      if (column.name === "image_path") return h("span", { class: "muted" }, "אין תמונה");
      if (column.nullLabel) return h("span", { class: "badge badge-warning" }, column.nullLabel);
      return h("span", { class: "muted", "aria-label": "ריק" }, "—");
    }
    if (column.name === "image_path") {
      const url = state.images[value];
      return url
        ? h("img", { class: "thumb", src: url, alt: `תמונת המנה ${row.name ?? ""}`, loading: "lazy" })
        : h("span", { class: "muted" }, "התמונה לא נטענה");
    }
    if (column.type === "jsonb" || column.type === "jsontext") {
      return h("details", { class: "json-cell" }, h("summary", {}, "הצגת התוכן"), h("pre", { dir: "ltr" }, jsonCellText(column, value)));
    }
    if (column.fk) {
      const label = state.lookups[column.name]?.[value];
      return label ? h("div", {}, h("span", { class: "cell-title" }, label), h("span", { class: "muted small block" }, `רשומה ${value}`)) : `רשומה ${value}`;
    }
    const text = formatCell(column, value, row);
    if (isLtrCell(column)) return h("code", { class: "ident", dir: "ltr" }, text);
    return h("span", { dir: "auto" }, text);
  }

  function renderGrid() {
    const table = state.table;
    if (!state.loaded) {
      clear(gridArea);
      if (state.loading) gridArea.append(h("div", { class: "skeleton grid-skeleton", role: "status", "aria-label": "טוען רשומות" }));
      renderPager();
      return;
    }
    const focusedKey = document.activeElement?.dataset?.rowKey;
    const canEdit = table.editable === true;
    clear(gridArea).append(
      state.rows.length === 0
        ? h("p", { class: "empty-state" }, "אין רשומות בטבלה הזו.")
        : h(
            "table",
            { class: "grid" },
            h("caption", { class: "visually-hidden" }, `רשומות הטבלה ${table.label}`),
            h(
              "thead",
              {},
              h(
                "tr",
                {},
                canEdit && h("th", { scope: "col" }, h("span", { class: "visually-hidden" }, "פעולות")),
                table.columns.map((column) =>
                  h(
                    "th",
                    { scope: "col" },
                    h("span", { class: "cell-title" }, column.label),
                    ident(column.name),
                    column.fk && h("span", { class: "fk-note" }, `קשר אל ${getTable(column.fk.table).label}`),
                  ),
                ),
              ),
            ),
            h(
              "tbody",
              {},
              state.rows.map((row) =>
                h(
                  "tr",
                  {},
                  canEdit &&
                    h(
                      "td",
                      {},
                      h(
                        "button",
                        {
                          class: "btn btn-ghost",
                          type: "button",
                          "data-row-key": rowKey(table, row),
                          "aria-label": `עריכת רשומה ${rowKey(table, row)}`,
                          onclick: () => openForm(row),
                        },
                        "עריכה",
                      ),
                    ),
                  table.columns.map((column) => h("td", {}, cellContent(column, row))),
                ),
              ),
            ),
          ),
    );
    // A background refresh must not move keyboard focus off the row being worked on.
    if (focusedKey) {
      [...gridArea.querySelectorAll("[data-row-key]")].find((element) => element.dataset.rowKey === focusedKey)?.focus();
    }
    renderPager();
  }

  function renderPager() {
    const info = pageInfo(state.count, state.page, state.pageSize);
    clear(pagerArea);
    if (!state.loaded) return;
    pagerArea.append(
      h("p", { class: "pager-summary", "aria-live": "polite" }, info.total === 0 ? "0 רשומות" : `רשומות ${info.first} עד ${info.last} מתוך ${info.total}`),
      h(
        "div",
        { class: "pager-controls" },
        h("label", { class: "pager-size" }, "בכל עמוד", h(
          "select",
          {
            class: "input",
            onchange: (event) => {
              state.pageSize = Number(event.target.value);
              state.page = 0;
              load();
            },
          },
          PAGE_SIZES.map((size) => h("option", { value: String(size), selected: size === state.pageSize }, String(size))),
        )),
        h("button", { class: "btn btn-secondary", type: "button", disabled: !info.hasPrev, onclick: () => { state.page -= 1; load(); } }, "הקודם"),
        h("span", {}, `עמוד ${state.page + 1} מתוך ${info.totalPages}`),
        h("button", { class: "btn btn-secondary", type: "button", disabled: !info.hasNext, onclick: () => { state.page += 1; load(); } }, "הבא"),
      ),
    );
  }

  /* ---------- actions ---------- */

  function openForm(row) {
    if (!state.table.editable) return;
    openRowForm({
      client,
      table: state.table,
      row,
      isSessionAlive: () => alive,
      onSaved: () => load({ quiet: true }),
      registerDialog: (value) => { dialog = value; },
    });
  }

  function selectTable(name) {
    state.table = getTable(name);
    state.page = 0;
    state.rows = [];
    state.count = 0;
    state.loaded = false;
    state.error = null;
    state.lookups = {};
    state.images = {};
    state.loadedAt = null;
    for (const [tableName, button] of tableButtons) {
      if (tableName === name) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
    renderTitle();
    load();
    realtime.switchTo(name);
  }

  selectTable(state.table.name);

  return {
    destroy() {
      alive = false;
      guard.invalidate();
      realtime.stop();
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      dialog?.close();
      signedUrlCache.clear();
      clear(container);
    },
  };
}

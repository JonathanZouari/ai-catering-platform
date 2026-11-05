// Schema-only views: table structure and the relationship diagram. They use static metadata
// from schema.js and never touch the network, so they also work with no cloud connection.
import { clear, h, ident, svg } from "./dom.js";
import { edgePath } from "./helpers.js";
import { GROUPS, RELATIONS, TABLES, getTable, relationsOf } from "./schema.js";

const TYPE_LABELS = {
  id: "מספר רץ",
  text: "טקסט",
  longtext: "טקסט ארוך",
  email: "דוא״ל",
  phone: "טלפון",
  int: "מספר שלם",
  fk: "מספר רשומה מקושרת",
  money: "סכום באגורות",
  milli: "כמות באלפיות",
  timestamp: "תאריך ושעה",
  date: "תאריך",
  bool: "כן או לא",
  enum: "ערך מרשימה",
  jsonb: "מסמך מובנה",
  jsontext: "טקסט בתבנית מסמך מובנה",
};

const relationIdent = (relation) =>
  `${relation.from} (${relation.columns.join(", ")}) → ${relation.to} (${relation.toColumns.join(", ")})`;

function relationItem(relation, direction) {
  const other = getTable(direction === "out" ? relation.to : relation.from);
  const prefix = direction === "out" ? "מצביעה אל" : "מצביעה אליה";
  const suffix = relation.optional ? "קשר אופציונלי" : "קשר חובה";
  return h(
    "li",
    { class: "relation-item" },
    h("span", {}, `${prefix}: ${other.label} (${suffix})`),
    ident(relationIdent(relation)),
  );
}

function columnNotes(column) {
  const notes = [];
  if (column.pk) notes.push("מפתח ראשי");
  if (column.unique) notes.push("ערך ייחודי");
  if (column.fk) notes.push(`קשר אל ${getTable(column.fk.table).label}`);
  if (column.generated) notes.push("מנוהל בידי המסד");
  if (column.masked) notes.push("מוצג מקוצר");
  if (column.options) notes.push(Object.values(column.options).join(", "));
  return notes.join(" · ");
}

function tableCard(table) {
  const { outgoing, incoming } = relationsOf(table.name);
  return h(
    "article",
    { class: "schema-card", id: `schema-${table.name}`, tabindex: "-1" },
    h(
      "header",
      { class: "schema-card-head" },
      h("h3", {}, table.label),
      ident(table.name),
      h("p", { class: "muted" }, table.description),
    ),
    h(
      "div",
      { class: "table-scroll", tabindex: "0", role: "region", "aria-label": `עמודות הטבלה ${table.label}` },
      h(
        "table",
        { class: "grid schema-grid" },
        h("thead", {}, h("tr", {}, ["עמודה", "סוג", "חובה", "הערות"].map((text) => h("th", { scope: "col" }, text)))),
        h(
          "tbody",
          {},
          table.columns.map((column) =>
            h(
              "tr",
              {},
              h("th", { scope: "row" }, h("span", { class: "cell-title" }, column.label), ident(column.name)),
              h("td", {}, TYPE_LABELS[column.type]),
              h("td", {}, column.nullable ? "לא" : "כן"),
              h("td", { class: "muted" }, columnNotes(column)),
            ),
          ),
        ),
      ),
    ),
    outgoing.length + incoming.length > 0
      ? h(
          "div",
          { class: "schema-relations" },
          h("h4", {}, "קשרים"),
          h("ul", { class: "relation-list" }, outgoing.map((r) => relationItem(r, "out")), incoming.map((r) => relationItem(r, "in"))),
        )
      : h("p", { class: "muted schema-relations" }, "אין לטבלה קשרים לטבלאות אחרות."),
  );
}

export function renderSchemaView(container) {
  clear(container).append(
    h(
      "div",
      { class: "view-head" },
      h("h2", {}, "מבנה הטבלאות"),
      h("p", { class: "muted" }, `${TABLES.length} טבלאות ו־${RELATIONS.length} קשרים. המסך הזה מציג מבנה בלבד, בלי אף רשומה.`),
    ),
    h(
      "nav",
      { class: "chip-nav", "aria-label": "מעבר לטבלה" },
      TABLES.map((table) =>
        h(
          "button",
          {
            type: "button",
            class: "chip",
            onclick: () => focusSchemaCard(table.name),
          },
          table.label,
        ),
      ),
    ),
    ...GROUPS.map((group) =>
      h(
        "section",
        { class: "schema-group", "aria-label": group.label },
        h("h3", { class: "group-title" }, group.label),
        h("div", { class: "schema-cards" }, TABLES.filter((table) => table.group === group.id).map(tableCard)),
      ),
    ),
  );
}

export function focusSchemaCard(tableName) {
  const card = document.getElementById(`schema-${tableName}`);
  card?.scrollIntoView({ block: "start" });
  card?.focus({ preventScroll: true });
}

/* ---------- relationship diagram ---------- */

const NODE = { width: 200, height: 68 };
const COLUMN_X = [1340, 1040, 740, 440, 140]; // Right to left, matching the reading direction.
const ROW_Y = [60, 190, 320, 450, 580];
const VIEW = { width: 1580, height: 700 };
const MIN_DIAGRAM_WIDTH = 980;
const ZOOM_STEPS = [0.75, 1, 1.25, 1.5, 2];

// Where each table sits: [column, row].
export const ERD_LAYOUT = {
  customers: [0, 0],
  addresses: [0, 1],
  events: [1, 0],
  orders: [1, 1],
  order_items: [1, 2],
  order_submissions: [1, 3],
  delivery_zones: [3, 0],
  dish_categories: [2, 1],
  dish_dietary: [3, 1],
  dishes: [2, 2],
  dish_allergens: [2, 3],
  allergens: [3, 3],
  time_slots: [0, 3],
  blocked_dates: [0, 4],
  ai_conversations: [4, 0],
  ai_messages: [4, 1],
  ai_change_proposals: [4, 2],
};

function nodeBox(name) {
  const [column, row] = ERD_LAYOUT[name];
  return { x: COLUMN_X[column], y: ROW_Y[row], ...NODE };
}

function groupBox(groupId) {
  const boxes = TABLES.filter((table) => table.group === groupId).map((table) => nodeBox(table.name));
  const left = Math.min(...boxes.map((box) => box.x)) - 14;
  const top = Math.min(...boxes.map((box) => box.y)) - 34;
  const right = Math.max(...boxes.map((box) => box.x + box.width)) + 14;
  const bottom = Math.max(...boxes.map((box) => box.y + box.height)) + 12;
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function nodeSummary(table) {
  const { outgoing, incoming } = relationsOf(table.name);
  return `${table.label}. מצביעה אל ${outgoing.length} טבלאות, ומקבלת הצבעה מ־${incoming.length} קשרים. לחיצה מדגישה את הקשרים.`;
}

export function renderErdView(container, { onOpenTable }) {
  let selected = null;
  let zoomIndex = 1;

  const detail = h("div", { class: "erd-detail", "aria-live": "polite" });
  const edges = RELATIONS.map((relation) => {
    const fromBox = nodeBox(relation.from);
    return {
      relation,
      element: svg("path", {
        class: `erd-edge${relation.optional ? " erd-edge-optional" : ""}`,
        d: edgePath(fromBox, relation.from === relation.to ? fromBox : nodeBox(relation.to)),
        "marker-end": "url(#erd-arrow)",
      }),
    };
  });

  const nodes = TABLES.map((table) => {
    const box = nodeBox(table.name);
    const element = svg(
      "g",
      {
        class: "erd-node",
        tabindex: "0",
        role: "button",
        "aria-pressed": "false",
        "aria-label": nodeSummary(table),
        onclick: () => select(table.name),
        onkeydown: (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            select(table.name);
          }
        },
      },
      svg("rect", { x: box.x, y: box.y, width: box.width, height: box.height, rx: 12 }),
      svg("text", { class: "erd-label", x: box.x + box.width / 2, y: box.y + 29, "text-anchor": "middle" }, table.label),
      svg("text", { class: "erd-ident", x: box.x + box.width / 2, y: box.y + 51, "text-anchor": "middle", direction: "ltr" }, table.name),
    );
    return { name: table.name, element };
  });

  const groupElements = GROUPS.map((group) => {
    const box = groupBox(group.id);
    return svg(
      "g",
      { class: "erd-group" },
      svg("rect", { ...box, rx: 16 }),
      svg("text", { x: box.x + box.width - 12, y: box.y + 21, "text-anchor": "end", direction: "rtl" }, group.label),
    );
  });

  const diagram = svg(
    "svg",
    {
      class: "erd-svg",
      viewBox: `0 0 ${VIEW.width} ${VIEW.height}`,
      role: "group",
      "aria-label": "תרשים הקשרים בין הטבלאות. רשימת הקשרים המלאה מופיעה בטקסט מתחת לתרשים.",
    },
    svg(
      "defs",
      {},
      svg(
        "marker",
        { id: "erd-arrow", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" },
        svg("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "erd-arrowhead" }),
      ),
    ),
    groupElements,
    edges.map((edge) => edge.element),
    nodes.map((node) => node.element),
  );

  const viewport = h("div", { class: "erd-viewport", dir: "ltr", tabindex: "0", role: "region", "aria-label": "אזור גלילה של התרשים" }, diagram);
  const zoomLabel = h("output", { class: "zoom-value" });

  function applyZoom() {
    const base = Math.max(viewport.clientWidth - 2, MIN_DIAGRAM_WIDTH);
    diagram.style.width = `${Math.round(base * ZOOM_STEPS[zoomIndex])}px`;
    zoomLabel.textContent = `${Math.round(ZOOM_STEPS[zoomIndex] * 100)}%`;
    zoomOut.disabled = zoomIndex === 0;
    zoomIn.disabled = zoomIndex === ZOOM_STEPS.length - 1;
  }

  const zoomOut = h("button", { class: "btn btn-secondary", type: "button", onclick: () => { zoomIndex -= 1; applyZoom(); } }, "הקטנה");
  const zoomIn = h("button", { class: "btn btn-secondary", type: "button", onclick: () => { zoomIndex += 1; applyZoom(); } }, "הגדלה");
  const zoomReset = h("button", { class: "btn btn-ghost", type: "button", onclick: () => { zoomIndex = 1; applyZoom(); } }, "איפוס");

  function select(name) {
    selected = selected === name ? null : name;
    for (const node of nodes) {
      const related = selected !== null && RELATIONS.some((r) => (r.from === selected && r.to === node.name) || (r.to === selected && r.from === node.name));
      node.element.setAttribute("aria-pressed", String(node.name === selected));
      node.element.classList.toggle("is-selected", node.name === selected);
      node.element.classList.toggle("is-dimmed", selected !== null && node.name !== selected && !related);
    }
    for (const edge of edges) {
      const touches = edge.relation.from === selected || edge.relation.to === selected;
      edge.element.classList.toggle("is-active", selected !== null && touches);
      edge.element.classList.toggle("is-dimmed", selected !== null && !touches);
    }
    renderDetail();
  }

  function renderDetail() {
    clear(detail);
    if (!selected) {
      detail.append(h("p", { class: "muted" }, "בחירת טבלה בתרשים מדגישה את הקשרים שלה ומפרטת אותם כאן."));
      return;
    }
    const table = getTable(selected);
    const { outgoing, incoming } = relationsOf(selected);
    detail.append(
      h("h3", {}, table.label),
      ident(table.name),
      h("p", { class: "muted" }, table.description),
      outgoing.length + incoming.length > 0
        ? h("ul", { class: "relation-list" }, outgoing.map((r) => relationItem(r, "out")), incoming.map((r) => relationItem(r, "in")))
        : h("p", {}, "אין לטבלה קשרים לטבלאות אחרות."),
      h("button", { class: "btn btn-secondary", type: "button", onclick: () => onOpenTable(selected) }, "מעבר למבנה הטבלה"),
    );
  }

  clear(container).append(
    h(
      "div",
      { class: "view-head" },
      h("h2", {}, "תרשים קשרים"),
      h("p", { class: "muted" }, "כל חץ יוצא מהטבלה שמחזיקה את ההפניה ומסתיים בטבלה שאליה היא מצביעה. קיבוץ לפי תחום עסקי."),
    ),
    h(
      "div",
      { class: "erd-toolbar" },
      h("div", { class: "zoom-controls", role: "group", "aria-label": "שינוי גודל התרשים" }, zoomOut, zoomLabel, zoomIn, zoomReset),
      h(
        "ul",
        { class: "erd-legend" },
        h("li", {}, h("span", { class: "legend-line" }), "קשר חובה"),
        h("li", {}, h("span", { class: "legend-line legend-line-optional" }), "קשר אופציונלי"),
      ),
    ),
    viewport,
    detail,
    h(
      "section",
      { class: "erd-text", "aria-label": "רשימת כל הקשרים" },
      h("h3", {}, "כל הקשרים בטקסט"),
      h(
        "ul",
        { class: "relation-list relation-columns" },
        RELATIONS.map((relation) =>
          h(
            "li",
            { class: "relation-item" },
            h("span", {}, `${getTable(relation.from).label} מצביעה אל ${getTable(relation.to).label}`),
            ident(relationIdent(relation)),
          ),
        ),
      ),
    ),
  );
  renderDetail();
  applyZoom();

  return { refreshLayout: applyZoom };
}

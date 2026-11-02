// The home page's sample ticket and scroll story. Figures here only illustrate:
// real prices and quantities always come from the backend.

const MENUS = {
  birthday: {
    label: "יום הולדת",
    lines: [
      { kind: "salad", name: "סלט עונתי", price: 120, serves: 10 },
      { kind: "main", name: "עוף בתנור", price: 180, serves: 10 },
      { kind: "side", name: "אורז עם שקדים", price: 90, serves: 14 },
      { kind: "dessert", name: "מגש עוגות", price: 130, serves: 20 },
    ],
  },
  brit: {
    label: "ברית",
    lines: [
      { kind: "salad", name: "סלטים לפתיחה", price: 110, serves: 10 },
      { kind: "main", name: "דג אפוי", price: 240, serves: 10 },
      { kind: "side", name: "קוסקוס ירקות", price: 100, serves: 14 },
      { kind: "dessert", name: "פירות העונה", price: 140, serves: 15 },
    ],
  },
  office: {
    label: "אירוע חברה",
    lines: [
      { kind: "salad", name: "סלט קינואה", price: 130, serves: 10 },
      { kind: "main", name: "כריכים מיני", price: 150, serves: 8 },
      { kind: "side", name: "ירקות צלויים", price: 95, serves: 14 },
      { kind: "dessert", name: "עוגיות הבית", price: 90, serves: 20 },
    ],
  },
};

const shekels = (amount) => `₪${amount.toLocaleString("en-US")}`;
const trays = (count) => (count === 1 ? "מגש אחד" : `${count} מגשים`);

function span(className, text) {
  const element = document.createElement("span");
  element.className = className;
  element.textContent = text;
  return element;
}

function renderLine({ kind, name, price, serves }, guests) {
  const quantity = Math.ceil(guests / serves);
  const row = document.createElement("li");
  const icon = span(`dish dish-${kind}`, "");
  icon.setAttribute("aria-hidden", "true");
  row.append(
    icon,
    span("line-name", name),
    span("line-qty", trays(quantity)),
    span("line-price", shekels(quantity * price)),
  );
  return { row, cost: quantity * price };
}

function setUpDemo() {
  const form = document.querySelector("#demo");
  const slider = document.querySelector("#guests");
  const ticket = document.querySelector("#ticket");
  if (!form || !slider || !ticket) return;

  const render = () => {
    const guests = Number(slider.value);
    const menu = MENUS[form.elements.event.value];
    const lines = menu.lines.map((line) => renderLine(line, guests));
    const total = lines.reduce((sum, line) => sum + line.cost, 0);

    document.querySelector("#guests-value").textContent = guests;
    document.querySelector("#ticket-event").textContent = `${menu.label} · ${guests} אורחים`;
    document.querySelector("#ticket-lines").replaceChildren(...lines.map((line) => line.row));
    document.querySelector("#ticket-total").textContent = shekels(total);
  };

  slider.addEventListener("input", render);
  form.addEventListener("change", (event) => {
    if (event.target.name !== "event") return;
    render();
    // A new event prints a new ticket.
    ticket.classList.remove("is-printing");
    void ticket.offsetWidth;
    ticket.classList.add("is-printing");
  });
  form.addEventListener("submit", (event) => event.preventDefault());
}

function setUpStory() {
  const stage = document.querySelector("#stage");
  const steps = document.querySelectorAll(".step");
  if (!stage || !steps.length || !("IntersectionObserver" in window)) return;

  const show = (step) => {
    stage.dataset.step = step.dataset.step;
    steps.forEach((item) => item.classList.toggle("is-active", item === step));
  };
  const observer = new IntersectionObserver(
    (entries) => entries.filter((entry) => entry.isIntersecting).forEach((e) => show(e.target)),
    // Phones: a thin band just below the sticky stage. Computers: the middle of the screen.
    { rootMargin: window.innerWidth < 960 ? "-62% 0px -33% 0px" : "-48% 0px -48% 0px" },
  );
  steps.forEach((step) => observer.observe(step));
  show(steps[0]);
}

setUpDemo();
setUpStory();

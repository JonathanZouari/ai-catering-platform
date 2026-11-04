// The home page's sample ticket and scroll story. Figures here only illustrate:
// real prices and quantities always come from the backend.

const DISHES = {
  bowl: { name: "קערת בריאות", price: 120, serves: 10 },
  potato: { name: "בטטה צלויה", price: 160, serves: 10 },
  pasta: { name: "פסטה ברוטב עגבניות", price: 180, serves: 10 },
  chef: { name: "מנת השף", price: 200, serves: 20 },
  veg: { name: "מגש ירקות העונה", price: 120, serves: 12 },
};

const MENUS = {
  birthday: { label: "יום הולדת", dishes: ["bowl", "potato", "pasta", "chef"] },
  brit: { label: "ברית", dishes: ["veg", "chef", "potato", "bowl"] },
  office: { label: "אירוע חברה", dishes: ["bowl", "pasta", "veg", "potato"] },
};

const shekels = (amount) => `₪${amount.toLocaleString("en-US")}`;
const trays = (count) => (count === 1 ? "מגש אחד" : `${count} מגשים`);

function span(className, text) {
  const element = document.createElement("span");
  element.className = className;
  element.textContent = text;
  return element;
}

function renderLine(key, guests) {
  const { name, price, serves } = DISHES[key];
  const quantity = Math.ceil(guests / serves);
  const row = document.createElement("li");
  const photo = document.createElement("img");
  photo.className = "dish";
  photo.src = `/img/food/${key}.jpg`;
  photo.alt = "";
  row.append(
    photo,
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
    const lines = menu.dishes.map((key) => renderLine(key, guests));
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

// SPECIES comes from species_data.js, which is loaded first.
const grid = document.getElementById("grid");
const detail = document.getElementById("detail");
let filter = "all";

function showGrid() {
  grid.innerHTML = "";
  for (const animal of SPECIES) {
    if (filter !== "all" && animal.light_level !== filter) continue;

    const card = document.createElement("button");
    card.className = "card";
        card.innerHTML = `
      <img src="images/${animal.species_id}.jpg" alt="${animal.common_name}" onerror="this.remove()">
      <span>${animal.common_name}</span>
    `;
    card.onclick = () => selectAnimal(card, animal);
    grid.appendChild(card);
  }
}

function selectAnimal(card, animal) {
  for (const other of document.querySelectorAll(".card")) {
    other.classList.remove("selected");
  }
  card.classList.add("selected");

  const light = animal.light_level === "H" ? "bright light" : "low light";
  detail.innerHTML = `
  <img class="detail-photo" src="images/${animal.species_id}.jpg" alt="${animal.common_name}" onerror="this.remove()">  
  <h2>${animal.common_name}</h2>
    <p class="latin">${animal.latin_name}</p>
    <p>Flicker fusion: <strong>${animal.flicker_fusion_hz} Hz</strong> (human: 60 Hz)</p>
        <div class="blink-row">
      <span class="blink-label">Human</span>
      <span class="dot" style="animation-duration: ${20 / 60}s"></span>
      <span class="blink-label">${animal.common_name}</span>
      <span class="dot" style="animation-duration: ${20 / animal.flicker_fusion_hz}s"></span>
      <span class="blink-note">(shown 20× slower)</span>
    </div>
    <p>Body mass: ${animal.body_mass_g} g</p>
    <p>Lives in: ${light}</p>
  `;
}

for (const button of document.querySelectorAll(".filter")) {
  button.onclick = () => {
    filter = button.dataset.filter;
    for (const other of document.querySelectorAll(".filter")) {
      other.classList.remove("active");
    }
    button.classList.add("active");
    showGrid();
  };
}

showGrid();

// ---------- "How do they see it?" slider ----------

// Short text for each animal (numbers come from data/vision_parameters.csv)
const VISION_INFO = {
  "canis-lupus-familiaris": { name: "Dog", text: "Two kinds of colour cells (blue and yellow), so red and green look alike. About 12 cycles per degree of sharpness; humans have about 60." },
  "felis-catus": { name: "Cat", text: "Two kinds of colour cells, like the dog. About 8 cycles per degree of sharpness." },
  "gallus-gallus-domesticus": { name: "Chicken", text: "Four kinds of colour cells, including ultraviolet, which a screen cannot show. About 7 cycles per degree of sharpness." },
  "macaca-mulatta": { name: "Macaque", text: "Three kinds of colour cells, like us, and sharp vision: about 24 cycles per degree." },
  "pagophilus-groenlandicus": { name: "Harp seal", text: "Only one kind of cone, so no colour. About 5.6 cycles per degree (measured in harbour seals)." },
  "gekko-gecko": { name: "Gecko", text: "Three kinds of colour cells. Sharpness is a stand-in value of 2 cycles per degree, taken from a wall lizard." },
  "spermophilus-lateralis": { name: "Squirrel", text: "Two kinds of colour cells. About 4 cycles per degree of sharpness." },
  "columba-livia": { name: "Pigeon", text: "Four kinds of colour cells, including ultraviolet, which a screen cannot show. About 12.8 cycles per degree." }
};

const visionButtons = document.querySelectorAll("#vision-picker button");
const visionAnimalImg = document.getElementById("vision-animal");
const visionSlider = document.getElementById("vision-slider");
const visionName = document.getElementById("vision-animal-name");
const visionCaption = document.getElementById("vision-caption");

// Show the chosen animal's view and mark its button
function pickVisionAnimal(id) {
  visionAnimalImg.src = `vision/${id}.jpg`;
  visionName.textContent = VISION_INFO[id].name;
  visionCaption.textContent = VISION_INFO[id].text;
  visionButtons.forEach((button) => {
    button.classList.toggle("picked", button.dataset.id === id);
  });
}

// Clicking a picture picks that animal
visionButtons.forEach((button) => {
  button.addEventListener("click", () => pickVisionAnimal(button.dataset.id));
});

// Moving the slider fades the animal's picture in over the human one
visionSlider.addEventListener("input", () => {
  visionAnimalImg.style.opacity = visionSlider.value / 100;
});

// Start with the dog
pickVisionAnimal("canis-lupus-familiaris");

// ---------- Scroll reveal animation ----------
// When an element marked "reveal" scrolls into view, add the class "visible".
// The CSS then fades and slides it in.
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target);   // play only once
    }
  });
}, { threshold: 0.15 });

document.querySelectorAll(".reveal").forEach((element) => {
  revealObserver.observe(element);
});

// ---------- Interactive plot ----------
const PLOT = { width: 640, height: 400, left: 56, right: 40, top: 20, bottom: 52 };
const plotSvg = document.getElementById("plot");

// Helper: make one SVG shape (line, circle, text) and give it attributes
function svgEl(tag, attributes) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const name in attributes) {
    element.setAttribute(name, attributes[name]);
  }
  return element;
}

// The range of the axes, worked out from the data
const logMasses = SPECIES.map((animal) => Math.log10(animal.body_mass_g));
const xMin = Math.floor(Math.min(...logMasses));
const xMax = Math.ceil(Math.max(...logMasses));
const maxHz = Math.max(...SPECIES.map((animal) => animal.flicker_fusion_hz));
const yMax = Math.ceil((maxHz + 10) / 20) * 20;

// Turn a data value into a position on the drawing
function xPos(bodyMassG) {
  const fraction = (Math.log10(bodyMassG) - xMin) / (xMax - xMin);
  return PLOT.left + fraction * (PLOT.width - PLOT.left - PLOT.right);
}

function yPos(hz) {
  const fraction = hz / yMax;
  return PLOT.height - PLOT.bottom - fraction * (PLOT.height - PLOT.top - PLOT.bottom);
}

function massLabel(power) {
  const grams = 10 ** power;
  return grams >= 1000 ? `${grams / 1000} kg` : `${grams} g`;
}

// Horizontal grid lines and Hz numbers
for (let hz = 0; hz <= yMax; hz += 20) {
  plotSvg.appendChild(svgEl("line", {
    x1: PLOT.left, x2: PLOT.width - PLOT.right, y1: yPos(hz), y2: yPos(hz), class: "plot-grid"
  }));
  const label = svgEl("text", { x: PLOT.left - 8, y: yPos(hz) + 4, class: "plot-label", "text-anchor": "end" });
  label.textContent = hz;
  plotSvg.appendChild(label);
}

// Body-mass labels: one per power of ten (log scale)
for (let power = xMin; power <= xMax; power++) {
  plotSvg.appendChild(svgEl("line", {
    x1: xPos(10 ** power), x2: xPos(10 ** power),
    y1: PLOT.top, y2: PLOT.height - PLOT.bottom, class: "plot-grid"
  }));
  const label = svgEl("text", {
    x: xPos(10 ** power), y: PLOT.height - PLOT.bottom + 18, class: "plot-label", "text-anchor": "middle"
  });
  label.textContent = massLabel(power);
  plotSvg.appendChild(label);
}

// Axis titles
const xTitle = svgEl("text", {
  x: (PLOT.left + PLOT.width - PLOT.right) / 2, y: PLOT.height - 8, class: "plot-title", "text-anchor": "middle"
});
xTitle.textContent = "Body mass (log scale)";
plotSvg.appendChild(xTitle);

const yTitle = svgEl("text", {
  x: -(PLOT.height / 2), y: 16, class: "plot-title", "text-anchor": "middle", transform: "rotate(-90)"
});
yTitle.textContent = "Flicker fusion frequency (Hz)";
plotSvg.appendChild(yTitle);

// One dot per animal
SPECIES.forEach((animal, index) => {
  const dot = svgEl("circle", {
    cx: xPos(animal.body_mass_g),
    cy: yPos(animal.flicker_fusion_hz),
    r: 7,
    class: `plot-dot dot-${animal.light_level}`,
    tabindex: 0
  });
  dot.style.animationDelay = `${index * 50}ms`;
  dot.dataset.id = animal.species_id;
  plotSvg.appendChild(dot);
});

// ---------- Plot hover label ----------
const plotTooltip = document.getElementById("plot-tooltip");
const plotBox = document.getElementById("plot-box");

// Show the label next to the mouse
function showTooltip(event, animal) {
  const box = plotBox.getBoundingClientRect();
  plotTooltip.innerHTML =
    `<strong>${animal.common_name}</strong><br>${animal.flicker_fusion_hz} Hz &middot; ${animal.body_mass_g} g`;
  plotTooltip.style.left = `${event.clientX - box.left + 12}px`;
  plotTooltip.style.top = `${event.clientY - box.top + 12}px`;
  plotTooltip.hidden = false;
}

// Give every dot its hover behaviour
document.querySelectorAll(".plot-dot").forEach((dot) => {
  // Each dot remembers its species_id, so we can look up its animal
  const animal = SPECIES.find((item) => item.species_id === dot.dataset.id);
  dot.addEventListener("mousemove", (event) => showTooltip(event, animal));
  dot.addEventListener("mouseleave", () => {
    plotTooltip.hidden = true;
  });
});

// ---------- Click a dot: go to that animal's card ----------
function goToCard(speciesId) {
  const animal = SPECIES.find((item) => item.species_id === speciesId);

  // Look through the cards for the one with this animal's name
  function findCard() {
    return [...document.querySelectorAll("#grid .card")].find(
      (card) => card.querySelector("span").textContent === animal.common_name
    );
  }

  let card = findCard();
  if (!card) {
    // The filter may be hiding this animal, so show all animals and look again
    document.querySelector('[data-filter="all"]').click();
    card = findCard();
  }
  if (card) {
    card.click();   // runs your existing code: highlight card, fill the description
    document.getElementById("detail").scrollIntoView({ behavior: "smooth", block: "start" });  }
}

document.querySelectorAll(".plot-dot").forEach((dot) => {
  dot.addEventListener("click", () => goToCard(dot.dataset.id));
  // Keyboard users: press Enter on a focused dot
  dot.addEventListener("keydown", (event) => {
    if (event.key === "Enter") goToCard(dot.dataset.id);
  });
});

// ---------- Group names and plain-words description ----------
const LIGHT_NAMES = { all: "All species", H: "Bright light", L: "Dim light" };

// Turn the correlation number into a plain-words description
function linkStrength(r) {
  const size = Math.abs(r);
  if (size < 0.2) return "almost no link";
  if (size < 0.4) return "a weak link";
  if (size < 0.7) return "a moderate link";
  return "a strong link";
}

// ---------- Group buttons: highlight a group and explain it ----------
const groupButtons = document.querySelectorAll("#group-buttons button");
const groupBox = document.getElementById("group-box");

function selectGroup(group) {
  // Mark the chosen button
  groupButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.group === group);
  });

  // Fade the dots that are not in the group
  document.querySelectorAll(".plot-dot").forEach((dot) => {
    const animal = SPECIES.find((item) => item.species_id === dot.dataset.id);
    const inGroup = group === "all" || animal.light_level === group;
    dot.classList.toggle("faded", !inGroup);
  });

  // Fill the box with this group's numbers
  const row = FIT.find((item) => item.light_level === group);
  groupBox.innerHTML = `
    <h3>${LIGHT_NAMES[group]}</h3>
    <p class="result-big">r = ${row.correlation_r}</p>
    <p>${linkStrength(row.correlation_r)} between body mass and flicker fusion.</p>
    <p class="result-small">${row.n_species} species &middot; ${row.slope_hz_per_10x_mass} Hz for every 10&times; more body mass</p>
  `;

  drawTrendLine(group, row);
}

// Put everything back to the starting state: no group chosen
function clearGroup() {
  groupButtons.forEach((button) => button.classList.remove("active"));
  document.querySelectorAll(".plot-dot").forEach((dot) => dot.classList.remove("faded"));
  const oldLine = plotSvg.querySelector(".trend-line");
  if (oldLine) oldLine.remove();
  groupBox.innerHTML = "<p>Choose a group above to see its trend line and what it means.</p>";
}

// Clicking the active button again switches it off; any other click selects that group
groupButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (button.classList.contains("active")) {
      clearGroup();
    } else {
      selectGroup(button.dataset.group);
    }
  });
});

// ---------- Trend line for the chosen group ----------
function drawTrendLine(group, row) {
  // Remove the previous line, if there is one
  const oldLine = plotSvg.querySelector(".trend-line");
  if (oldLine) oldLine.remove();

  // The line runs over the body masses of the animals in this group
  const members = SPECIES.filter((animal) => group === "all" || animal.light_level === group);
  const logMassesInGroup = members.map((animal) => Math.log10(animal.body_mass_g));
  const logStart = Math.min(...logMassesInGroup);
  const logEnd = Math.max(...logMassesInGroup);

  // The fitted line from analyse_cff.py: Hz = intercept + slope * log10(body mass)
  const hzAt = (logMass) => row.intercept_hz + row.slope_hz_per_10x_mass * logMass;

  const line = svgEl("line", {
    x1: xPos(10 ** logStart), y1: yPos(hzAt(logStart)),
    x2: xPos(10 ** logEnd),   y2: yPos(hzAt(logEnd)),
    class: `trend-line trend-${group}`
  });
  // Put it before the dots in the drawing, so the dots stay on top
  plotSvg.insertBefore(line, plotSvg.querySelector(".plot-dot"));

  // Animate: draw the line from left to right
  const length = line.getTotalLength();
  line.style.strokeDasharray = length;
  line.style.strokeDashoffset = length;
  line.getBoundingClientRect();   // lets the browser register the starting state
  line.style.transition = "stroke-dashoffset 1s ease";
  line.style.strokeDashoffset = 0;
}
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
    <h2>${animal.common_name}</h2>
    <p class="latin">${animal.latin_name}</p>
    <p>Flicker fusion: <strong>${animal.flicker_fusion_hz} Hz</strong> (human: 60 Hz)</p>
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
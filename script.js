/* Other Eyes: vision demo, map, and fact cards.
   Species data lives in data/species.json. */

/* ------------------------------------------------------------------ */
/* 1. VISION MODES                                                     */
/* ------------------------------------------------------------------ */

const VISION = {
  human: {
    label: "Human",
    title: "Human vision",
    what: "Three kinds of colour receptors (red, green, blue) and sharp detail in the centre of the view.",
    how: "No effect applied.",
    accuracy: "This is the baseline for comparison."
  },
  dog: {
    label: "Dog",
    title: "Dog vision",
    what: "Dogs have two kinds of colour receptors, so reds and greens blur into yellowish-brown tones. Blues and yellows stay clear. Their eyesight is also less sharp than ours.",
    how: "A colour-blindness matrix removes the red-green difference, then the image is softened.",
    accuracy: "Fairly good for colour. The amount of blur is an estimate."
  },
  bee: {
    label: "Bee",
    title: "Bee vision",
    what: "Bees see ultraviolet, blue and green, but not red. Red looks dark. Their eyes resolve much less detail than ours.",
    how: "Channels are shifted so ultraviolet, blue and green show as blue, green and red, then the image is blurred.",
    accuracy: "False colour. This photo has no real ultraviolet data, so the UV layer is a rough guess."
  },
  eagle: {
    label: "Eagle",
    title: "Eagle vision",
    what: "Eagles resolve fine detail from far away and see extra colour range. Look at the small text on the sign.",
    how: "The image is sharpened and the colours are made richer.",
    accuracy: "Approximate. A photo cannot contain more detail than it already has, so this only hints at the difference."
  },
  fly: {
    label: "Fly",
    title: "Fly vision",
    what: "A compound eye is built from thousands of tiny lenses, so the picture is a mosaic with low detail. Flies also detect motion much faster than we do.",
    how: "The image is rebuilt from a grid of hexagons, one colour each.",
    accuracy: "Good for the mosaic look. Speed of motion cannot be shown in a still image."
  },
  snake: {
    label: "Pit viper",
    title: "Pit viper heat sense",
    what: "Pit vipers sense heat with pit organs and blend it with ordinary vision. Warm things glow and the picture is blurry.",
    how: "Brightness is used as a stand-in for warmth and mapped to a heat-camera colour scale, then blurred.",
    accuracy: "Illustration only. A normal photo has no temperature data, so bright areas are treated as warm."
  }
};

const IMAGE_PATH = "images/sample-scene.jpg";
const MAX_WIDTH = 960;

const origCanvas = document.getElementById("canvas-original");
const resCanvas = document.getElementById("canvas-result");
const origCtx = origCanvas.getContext("2d", { willReadFrequently: true });
const resCtx = resCanvas.getContext("2d", { willReadFrequently: true });
const slider = document.getElementById("slider");
const handle = document.getElementById("handle");
const tagRight = document.getElementById("tag-right");
const notes = document.getElementById("notes");
const picker = document.getElementById("mode-picker");
const fileInput = document.getElementById("file-input");

let sourceImage = null;
let currentMode = "dog";

/* Blur by shrinking then enlarging. Works in every browser. */
function blurred(canvas, factor) {
  const w = canvas.width, h = canvas.height;
  const small = document.createElement("canvas");
  small.width = Math.max(1, Math.round(w / factor));
  small.height = Math.max(1, Math.round(h / factor));
  const sctx = small.getContext("2d");
  sctx.imageSmoothingEnabled = true;
  sctx.imageSmoothingQuality = "high";
  sctx.drawImage(canvas, 0, 0, small.width, small.height);
  const big = document.createElement("canvas");
  big.width = w; big.height = h;
  const bctx = big.getContext("2d", { willReadFrequently: true });
  bctx.imageSmoothingEnabled = true;
  bctx.imageSmoothingQuality = "high";
  bctx.drawImage(small, 0, 0, w, h);
  return big;
}

const clamp = v => (v < 0 ? 0 : v > 255 ? 255 : v);

function applyDog() {
  const soft = blurred(origCanvas, 2.5);
  const img = soft.getContext("2d").getImageData(0, 0, soft.width, soft.height);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    d[i]     = clamp(0.625 * r + 0.375 * g);
    d[i + 1] = clamp(0.700 * r + 0.300 * g);
    d[i + 2] = clamp(0.300 * g + 0.700 * b);
  }
  resCtx.putImageData(img, 0, 0);
}

function applyBee() {
  const soft = blurred(origCanvas, 4);
  const img = soft.getContext("2d").getImageData(0, 0, soft.width, soft.height);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    const uv = 0.7 * b + 0.3 * (255 - r);   // rough stand-in for UV
    d[i]     = clamp(g);                    // green  -> red channel
    d[i + 1] = clamp(b);                    // blue   -> green channel
    d[i + 2] = clamp(uv);                   // UV     -> blue channel
  }
  resCtx.putImageData(img, 0, 0);
}

function applyEagle() {
  const w = origCanvas.width, h = origCanvas.height;
  const base = origCtx.getImageData(0, 0, w, h);
  const soft = blurred(origCanvas, 3).getContext("2d").getImageData(0, 0, w, h);
  const d = base.data, s = soft.data;
  for (let i = 0; i < d.length; i += 4) {
    let r = d[i] + 1.3 * (d[i] - s[i]);
    let g = d[i + 1] + 1.3 * (d[i + 1] - s[i + 1]);
    let b = d[i + 2] + 1.3 * (d[i + 2] - s[i + 2]);
    const l = 0.299 * r + 0.587 * g + 0.114 * b;   // boost saturation
    d[i]     = clamp(l + 1.2 * (r - l));
    d[i + 1] = clamp(l + 1.2 * (g - l));
    d[i + 2] = clamp(l + 1.2 * (b - l));
  }
  resCtx.putImageData(base, 0, 0);
}

function applyFly() {
  const w = origCanvas.width, h = origCanvas.height;
  const src = blurred(origCanvas, 1.5).getContext("2d").getImageData(0, 0, w, h).data;
  const R = Math.max(7, Math.round(w / 100));       // hexagon radius
  const colW = Math.sqrt(3) * R, rowH = 1.5 * R;
  resCtx.fillStyle = "#050806";
  resCtx.fillRect(0, 0, w, h);
  for (let row = 0, y = 0; y < h + R; row++, y += rowH) {
    const offset = row % 2 ? colW / 2 : 0;
    for (let x = -colW; x < w + colW; x += colW) {
      const cx = x + offset, cy = y;
      const px = Math.min(w - 1, Math.max(0, Math.round(cx)));
      const py = Math.min(h - 1, Math.max(0, Math.round(cy)));
      const i = (py * w + px) * 4;
      resCtx.fillStyle = `rgb(${src[i]},${src[i + 1]},${src[i + 2]})`;
      resCtx.beginPath();
      for (let k = 0; k < 6; k++) {
        const a = Math.PI / 6 + k * Math.PI / 3;
        const hx = cx + (R - 0.8) * Math.cos(a);
        const hy = cy + (R - 0.8) * Math.sin(a);
        k === 0 ? resCtx.moveTo(hx, hy) : resCtx.lineTo(hx, hy);
      }
      resCtx.closePath();
      resCtx.fill();
    }
  }
}

/* Heat-camera colour scale */
const HEAT_STOPS = [
  [0.00, [5, 0, 25]],
  [0.25, [70, 0, 120]],
  [0.50, [200, 30, 40]],
  [0.75, [255, 170, 20]],
  [1.00, [255, 250, 210]]
];
const HEAT_LUT = (() => {
  const lut = [];
  for (let n = 0; n < 256; n++) {
    const t = n / 255;
    let k = 0;
    while (k < HEAT_STOPS.length - 2 && t > HEAT_STOPS[k + 1][0]) k++;
    const [t0, c0] = HEAT_STOPS[k], [t1, c1] = HEAT_STOPS[k + 1];
    const f = (t - t0) / (t1 - t0);
    lut.push(c0.map((v, j) => Math.round(v + f * (c1[j] - v))));
  }
  return lut;
})();

function applySnake() {
  const soft = blurred(origCanvas, 6);
  const img = soft.getContext("2d").getImageData(0, 0, soft.width, soft.height);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const lum = Math.round(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]);
    const c = HEAT_LUT[lum];
    d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2];
  }
  resCtx.putImageData(img, 0, 0);
}

const EFFECTS = {
  human: () => resCtx.drawImage(origCanvas, 0, 0),
  dog: applyDog, bee: applyBee, eagle: applyEagle, fly: applyFly, snake: applySnake
};

function drawSource() {
  if (!sourceImage) return;
  const scale = Math.min(1, MAX_WIDTH / sourceImage.naturalWidth);
  const w = Math.round(sourceImage.naturalWidth * scale);
  const h = Math.round(sourceImage.naturalHeight * scale);
  origCanvas.width = resCanvas.width = w;
  origCanvas.height = resCanvas.height = h;
  origCtx.drawImage(sourceImage, 0, 0, w, h);
}

function render() {
  if (!sourceImage) return;
  EFFECTS[currentMode]();
}

function renderNotes() {
  const v = VISION[currentMode];
  const speciesLink = SPECIES.find(s => s.vision === currentMode);
  notes.innerHTML = `
    <h3 class="notes-title">${v.title}</h3>
    <div><h3>What changes</h3><p>${v.what}</p></div>
    <div><h3>How this image is made</h3><p>${v.how}</p></div>
    <div class="accuracy"><h3>How accurate is it?</h3><p>${v.accuracy}</p>
      ${speciesLink ? `<p style="margin-top:.6rem">${speciesLink.visionNote}</p>` : ""}</div>`;
}

function setMode(mode, scrollToDemo = false) {
  currentMode = mode;
  tagRight.textContent = VISION[mode].label;
  picker.querySelectorAll("button").forEach(b =>
    b.setAttribute("aria-checked", String(b.dataset.mode === mode)));
  render();
  renderNotes();
  if (scrollToDemo) document.getElementById("vision").scrollIntoView();
}

function buildPicker() {
  Object.entries(VISION).filter(([k]) => k !== "human").forEach(([key, v]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "radio");
    b.dataset.mode = key;
    b.textContent = v.label;
    b.addEventListener("click", () => setMode(key));
    picker.appendChild(b);
  });
}

function updateSlider() {
  const v = slider.value;
  resCanvas.style.clipPath = `inset(0 0 0 ${v}%)`;
  handle.style.left = v + "%";
}
slider.addEventListener("input", updateSlider);

function loadImage(src) {
  const img = new Image();
  img.onload = () => { sourceImage = img; drawSource(); render(); };
  img.onerror = () => { notes.innerHTML = `<p class="error-box">Could not load the image at ${src}.</p>`; };
  img.src = src;
}

fileInput.addEventListener("change", e => {
  const file = e.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);   // stays on your device, never uploaded
  loadImage(url);
});

/* ------------------------------------------------------------------ */
/* 2. MAP                                                              */
/* ------------------------------------------------------------------ */

let SPECIES = [];
let map, rangeLayers = {};

function initMap() {
  map = L.map("map-canvas", { worldCopyJump: true, minZoom: 1 }).setView([25, 10], 2);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
    maxZoom: 8
  }).addTo(map);

  SPECIES.forEach(s => {
    const layer = L.geoJSON(s.range, {
      style: { color: s.color, weight: 2, fillColor: s.color, fillOpacity: 0.35 }
    });
    layer.bindTooltip(`${s.name} (${s.latin})`, { sticky: true });
    rangeLayers[s.id] = layer;
  });

  const chips = document.getElementById("map-chips");
  const allBtn = makeChip("Show all", () => showSpecies(null));
  allBtn.dataset.id = "all";
  chips.appendChild(allBtn);
  SPECIES.forEach(s => {
    const b = makeChip(s.name, () => showSpecies(s.id));
    b.dataset.id = s.id;
    chips.appendChild(b);
  });
  showSpecies(null);
}

function makeChip(label, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

function showSpecies(id, scroll = false) {
  Object.values(rangeLayers).forEach(l => map.removeLayer(l));
  const targets = id ? [rangeLayers[id]] : Object.values(rangeLayers);
  targets.forEach(l => l.addTo(map));
  const group = L.featureGroup(targets);
  map.fitBounds(group.getBounds(), { padding: [30, 30], maxZoom: 4 });

  document.querySelectorAll("#map-chips button").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.id === (id || "all"))));

  const sp = SPECIES.find(s => s.id === id);
  document.getElementById("map-caption").textContent =
    (sp && sp.rangeNote ? sp.rangeNote + " " : "") +
    "Ranges on this map are rough placeholder shapes, not scientific data.";
  if (scroll) document.getElementById("map").scrollIntoView();
}

/* ------------------------------------------------------------------ */
/* 3. FACT CARDS                                                       */
/* ------------------------------------------------------------------ */

function esc(t) {
  const el = document.createElement("div");
  el.textContent = t;
  return el.innerHTML;
}

function buildCards() {
  const wrap = document.getElementById("cards");
  wrap.innerHTML = "";
  SPECIES.forEach(s => {
    const card = document.createElement("article");
    card.className = "card";
    card.style.setProperty("--accent", s.color);
    card.innerHTML = `
      <div>
        <h3>${esc(s.name)}</h3>
        <div class="latin">${esc(s.latin)}</div>
      </div>
      <dl>
        <dt>Group</dt><dd>${esc(s.group)}</dd>
        <dt>Status</dt><dd>${esc(s.status)}</dd>
        <dt>Size</dt><dd>${esc(s.size)}</dd>
        <dt>Diet</dt><dd>${esc(s.diet)}</dd>
      </dl>
      <ul>${s.facts.map(f => `<li>${esc(f)}</li>`).join("")}</ul>
      <div class="actions"></div>`;
    const actions = card.querySelector(".actions");
    const mapBtn = makeChip("Show range", () => showSpecies(s.id, true));
    mapBtn.className = "btn";
    actions.appendChild(mapBtn);
    if (s.vision) {
      const vb = makeChip("See how it sees", () => setMode(s.vision, true));
      vb.className = "btn";
      actions.appendChild(vb);
    }
    wrap.appendChild(card);
  });
}

/* ------------------------------------------------------------------ */
/* 4. START                                                            */
/* ------------------------------------------------------------------ */

async function start() {
  buildPicker();
  updateSlider();
  setMode(currentMode);
  loadImage(IMAGE_PATH);

  try {
    const res = await fetch("data/species.json");
    if (!res.ok) throw new Error(res.status);
    SPECIES = (await res.json()).species;
  } catch (err) {
    document.getElementById("cards").innerHTML =
      `<p class="error-box">Could not load data/species.json. If you opened index.html by double-clicking it, run a local server instead (for example <code>python -m http.server</code>) or use the GitHub Pages link.</p>`;
    return;
  }
  renderNotes();
  initMap();
  buildCards();
}

start();

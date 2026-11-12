import streamlit as st

st.set_page_config(layout="wide", page_title="Route")
st.markdown(
    "<style>.block-container{padding:0 !important;max-width:100% !important}"
    "header,footer{visibility:hidden}.stApp{background:#12151a}</style>",
    unsafe_allow_html=True,
)

html_code = r"""
<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500&family=Jost:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#12151a;--card:#181c22;--line:rgba(236,230,216,.1);--ink:#ece6d8;--mute:#8b8f96;--gold:#cdbb98;
--serif:'Cormorant Garamond',Georgia,serif;--sans:'Jost',system-ui,sans-serif}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font-family:var(--sans);font-weight:300;overflow:hidden}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer;padding:0}
button:focus-visible,input:focus-visible{outline:1px solid var(--gold);outline-offset:3px}

.stage{position:absolute;inset:0 0 76px;perspective:1900px;perspective-origin:50% 45%}
.card{position:absolute;left:50%;top:50%;width:var(--cw);height:var(--ch);margin:calc(var(--ch)/-2) 0 0 calc(var(--cw)/-2);
background:var(--card);border:1px solid var(--line);border-radius:6px;display:flex;flex-direction:column;overflow:hidden;
box-shadow:0 40px 80px -30px rgba(0,0,0,.7);pointer-events:none;will-change:transform,opacity}
.card:not(.active){cursor:pointer}
.card:not(.active)>*{pointer-events:none}
.card.active{pointer-events:auto}

.head{display:flex;align-items:center;justify-content:space-between;height:60px;padding:0 28px;border-bottom:1px solid var(--line);cursor:grab;touch-action:pan-y;user-select:none}
.head:active{cursor:grabbing}
.title{font-family:var(--serif);font-size:26px;font-weight:500;letter-spacing:.01em}
.tools{display:flex;align-items:center;gap:22px;font-size:13px;color:var(--mute)}
.tools button{transition:color .25s}.tools button:hover,.tools button.on{color:var(--gold)}
.seg{display:none;gap:18px}.drawing .seg{display:flex}
.tools .main{color:var(--ink);border:1px solid var(--line);padding:7px 16px;border-radius:30px;transition:all .25s}
.tools .main.on{background:var(--gold);color:#12151a;border-color:var(--gold)}
.sep{width:1px;height:16px;background:var(--line)}

.mapwrap{position:relative;flex:1;min-height:0}
#map{position:absolute;inset:0;background:#0f1216}
.leaflet-container{font-family:var(--sans)}
.leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.82) contrast(.88) saturate(.3)}
.leaflet-bar{border:1px solid var(--line)!important;box-shadow:none!important;border-radius:4px!important;overflow:hidden}
.leaflet-bar a{background:var(--card)!important;color:var(--ink)!important;border-color:var(--line)!important}
.leaflet-control-attribution{background:rgba(18,21,26,.7)!important;color:var(--mute)!important;font-size:10px}
.leaflet-control-attribution a{color:var(--mute)!important}
.dist{position:absolute;left:28px;bottom:22px;z-index:500;pointer-events:none}

.popover{display:none;position:absolute;top:20px;width:min(320px,calc(100% - 40px));z-index:1100;background:rgba(24,28,34,.94);border:1px solid var(--line);border-radius:6px;padding:16px 20px;backdrop-filter:blur(8px)}
.popover.open{display:block}
.places{left:20px}
.savebox{right:20px}
.popover input{display:block;width:100%;background:none;border:0;border-bottom:1px solid var(--line);color:var(--ink);font:300 16px var(--sans);padding:9px 0;margin-bottom:10px;border-radius:0;transition:border-color .25s}
.popover input::placeholder{color:#5d6168}
.popover input:focus{outline:0;border-color:var(--gold)}

.tags{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 4px}
.tags button{font-size:12px;color:var(--mute);border:1px solid var(--line);padding:4px 11px;border-radius:20px;transition:all .2s}
.tags button:hover{color:var(--ink);border-color:rgba(205,187,152,.4)}
.tags button.on{background:rgba(205,187,152,.15);color:var(--gold);border-color:var(--gold)}

.sug{display:none;position:absolute;z-index:5;background:#1d2229;border:1px solid var(--line);border-radius:4px;max-height:250px;overflow:auto;box-shadow:0 16px 30px -12px rgba(0,0,0,.6)}
.sug div{padding:9px 12px;font-size:14px;cursor:pointer;line-height:1.3}
.sug small{display:block;font-size:12px;color:var(--mute);margin-top:2px}
.sug div:hover,.sug .hl{background:rgba(205,187,152,.12)}
.prow{display:flex;justify-content:space-between;align-items:center;margin-top:14px;font-size:13px;color:var(--mute)}
.prow button{transition:color .25s}.prow button:hover{color:var(--gold)}
.prow .go{color:#12151a;background:var(--gold);padding:7px 18px;border-radius:30px}.prow .go:hover{color:#12151a}
.prow .go:disabled{opacity:.5;cursor:default}
.pmsg{margin:12px 0 0;font-size:13px;line-height:1.5;color:var(--mute)}
.leaflet-tooltip{background:var(--card);color:var(--ink);border:1px solid var(--line);box-shadow:none;font-family:var(--sans);font-size:12px}
.leaflet-tooltip:before{display:none}
.dist small{display:block;font-size:12px;color:var(--mute);margin-bottom:2px}
.dist b{font-family:var(--serif);font-weight:400;font-size:54px;line-height:1}
.dist span,.unit{font-family:var(--serif);font-size:22px;color:var(--gold);margin-left:6px}

.body{flex:1;min-height:0;padding:34px 44px 30px;display:flex;flex-direction:column}
.row{display:grid;grid-template-columns:repeat(3,1fr)}
.stat{padding:8px 0 8px 28px;border-left:1px solid var(--line)}.stat:first-child{border:0;padding-left:0}
.stat small{display:block;font-size:13px;color:var(--mute);margin-bottom:12px}
.stat b{font-family:var(--serif);font-weight:400;font-size:clamp(44px,6vw,76px);line-height:1}
.weight{margin-top:auto;padding-top:34px;border-top:1px solid var(--line)}
.weight header{display:flex;justify-content:space-between;align-items:baseline;font-size:14px;color:var(--mute)}
.weight header b{font-family:var(--serif);font-weight:400;font-size:34px;color:var(--ink)}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:1px;background:var(--line);margin:26px 0 8px}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:var(--gold);cursor:pointer;border:5px solid var(--card);box-shadow:0 0 0 1px var(--gold)}
input[type=range]::-moz-range-thumb{width:8px;height:8px;border-radius:50%;background:var(--gold);border:5px solid var(--card);box-shadow:0 0 0 1px var(--gold)}
.file{position:absolute;width:1px;height:1px;opacity:0}
.note{margin:26px 0 0;font-size:14px;color:var(--mute);max-width:52ch;line-height:1.6}
.mid{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center}
.stats .weight{margin-top:0;padding-top:26px}
.ctrl{display:grid;grid-template-columns:1fr 1fr;gap:40px;padding:24px 0 26px;border-top:1px solid var(--line)}
.field>span,.field>label{display:block;font-size:14px;color:var(--mute);margin-bottom:10px}
.pick{display:flex;gap:26px}
.pick button{font-size:17px;color:var(--mute);padding:4px 0;border-bottom:1px solid transparent;transition:all .25s}
.pick button:hover{color:var(--ink)}.pick button.on{color:var(--ink);border-color:var(--gold)}
.field input[type=text]{width:100%;background:none;border:0;border-bottom:1px solid var(--line);color:var(--ink);font-family:var(--serif);font-size:26px;padding:0 0 4px;border-radius:0;transition:border-color .25s}
.field input[type=text]::placeholder{font-family:var(--sans);font-weight:300;font-size:14px;color:#5d6168}
.field input[type=text]:focus{outline:0;border-color:var(--gold)}

.chart{position:relative;flex:1;min-height:0;margin-top:30px}
.msg{font-size:14px;color:var(--mute);margin:26px 0 0}

.dock{position:absolute;left:0;right:0;bottom:0;height:76px;display:flex;align-items:center;justify-content:center;gap:34px;font-size:14px}
.dock .arrow{width:38px;height:38px;border:1px solid var(--line);border-radius:50%;color:var(--mute);transition:all .25s;display:grid;place-items:center}
.dock .arrow:hover{color:var(--gold);border-color:var(--gold)}
.dock .tab{color:var(--mute);padding:8px 0;border-bottom:1px solid transparent;transition:all .3s}
.dock .tab.on{color:var(--ink);border-color:var(--gold)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head>
<body>
<div class="stage" id="stage">

  <section class="card" data-name="Route">
    <div class="head">
      <div class="title">Route</div>
      <div class="tools">
        <div class="seg" id="seg">
          <button data-mode="freehand" class="on">Freehand</button>
          <button data-mode="straight">Straight</button>
          <button data-mode="eraser">Eraser</button>
          <span class="sep"></span>
        </div>
        <button id="pl">Places</button>
        <button class="main" id="draw">Draw</button>
        <button id="clear">Clear</button>
        <button id="save">Save</button>
      </div>
    </div>
    <div class="mapwrap">
      <div id="map"></div>
      <div class="popover places" id="places">
        <div id="stops"></div>
        <div class="prow"><button id="addstop">Add stop</button><button id="find" class="go">Find route</button></div>
        <p class="pmsg" id="pmsg">Type addresses, places or coordinates. Walking and running follow footpaths; cycling follows bike routes.</p>
      </div>
      <div class="popover savebox" id="savebox">
        <input type="text" id="rname" placeholder="Route name (e.g. Vingio parkas)" autocomplete="off">
        <div class="tags" id="rtags">
          <button data-cat="Park / Forest" class="on">Park / Forest</button>
          <button data-cat="Urban">Urban</button>
          <button data-cat="Riverside">Riverside</button>
          <button data-cat="Hilly / Trail">Hilly / Trail</button>
        </div>
        <div class="prow">
          <button id="closesave">Cancel</button>
          <button id="dlbtn" class="go">Download GeoJSON</button>
        </div>
        <p class="pmsg" id="smsg">Exports route geometry with distance, elevation, and energy metadata for analysis.</p>
      </div>
      <div class="dist"><small>Distance</small><b id="d-map">0.00</b><span>km</span></div>
    </div>
  </section>

  <section class="card stats" data-name="Statistics">
    <div class="head"><div class="title">Statistics</div>
      <div class="tools"><label for="file" style="cursor:pointer" id="imp">Import route(s)</label></div>
      <input class="file" type="file" id="file" accept=".geojson,.json" multiple>
    </div>
    <div class="body">
      <div class="mid"><div class="row">
        <div class="stat"><small>Distance</small><b id="v-dist">0.00</b><span class="unit">km</span></div>
        <div class="stat"><small id="l-time">Estimated time</small><b id="v-time">0</b><span class="unit">min</span></div>
        <div class="stat"><small>Energy</small><b id="v-cal">0</b><span class="unit">kcal</span></div>
      </div>
      <p class="note" id="note"></p></div>
      <div class="ctrl">
        <div class="field"><span>Activity</span>
          <div class="pick" id="act">
            <button data-a="walk" class="on">Walking</button><button data-a="run">Running</button><button data-a="bike">Cycling</button>
          </div></div>
        <div class="field"><label for="t">Your time, optional</label>
          <input id="t" type="text" inputmode="decimal" autocomplete="off" placeholder="Minutes, or hours:minutes"></div>
      </div>
      <div class="weight">
        <header><span>Your weight</span><span><b id="w-val">70</b> kg</span></header>
        <input type="range" id="w" min="40" max="130" value="70" aria-label="Weight in kilograms">
      </div>
    </div>
  </section>

  <section class="card" data-name="Elevation">
    <div class="head"><div class="title">Elevation</div></div>
    <div class="body">
      <div class="row">
        <div class="stat"><small>Highest point</small><b id="e-max">–</b><span class="unit">m</span></div>
        <div class="stat"><small>Lowest point</small><b id="e-min">–</b><span class="unit">m</span></div>
        <div class="stat"><small>Total climb</small><b id="e-gain">–</b><span class="unit">m</span></div>
      </div>
      <p class="msg" id="e-msg">Draw a route to see its profile.</p>
      <div class="chart"><canvas id="chart"></canvas></div>
    </div>
  </section>
</div>

<nav class="dock">
  <button class="arrow" id="prev" aria-label="Previous"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor"><path d="M9 2 4 7l5 5"/></svg></button>
  <button class="tab on" data-i="0">Route</button>
  <button class="tab" data-i="1">Statistics</button>
  <button class="tab" data-i="2">Elevation</button>
  <button class="arrow" id="next" aria-label="Next"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor"><path d="m5 2 5 5-5 5"/></svg></button>
</nav>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
/* ---------- Ring carousel ---------- */
const stage = document.getElementById('stage'),
      cards = [...stage.querySelectorAll('.card')],
      tabs = [...document.querySelectorAll('.tab')], N = cards.length;
let pos = 0, target = 0, raf = null;
const mod = (a, n) => ((a % n) + n) % n;
const ease = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;

function layout() {
  const W = stage.clientWidth, H = stage.clientHeight,
        R = Math.min(760, Math.max(340, W * .5));
  stage.style.setProperty('--cw', Math.min(920, W * .8) + 'px');
  stage.style.setProperty('--ch', Math.min(660, H - 50) + 'px');
  cards.forEach((c, i) => {
    const d = mod(i - pos + N / 2, N) - N / 2, a = d * 2 * Math.PI / N,
          x = Math.sin(a) * R, z = (Math.cos(a) - 1) * R, ry = -Math.sin(a) * 26;
    c.style.transform = `translate3d(${x.toFixed(2)}px,0,${z.toFixed(2)}px) rotateY(${ry.toFixed(2)}deg)`;
    c.style.opacity = (.18 + .82 * Math.pow((Math.cos(a) + 1) / 2, 1.2)).toFixed(3);
    c.style.zIndex = Math.round(100 + Math.cos(a) * 100);
  });
}
function settle() {
  const idx = mod(Math.round(target), N);
  cards.forEach((c, i) => { c.classList.toggle('active', i === idx); });
  tabs.forEach((t, i) => t.classList.toggle('on', i === idx));
  setTimeout(() => { map.invalidateSize(); if (chart) chart.resize(); }, 30);
}
function go(delta) {
  target = Math.round(target) + delta;
  const from = pos, to = target, t0 = performance.now(), dur = 950;
  cards.forEach(c => c.classList.remove('active'));
  cancelAnimationFrame(raf);
  (function step(now) {
    const t = Math.min(1, (now - t0) / dur);
    pos = from + (to - from) * ease(t);
    layout();
    if (t < 1) raf = requestAnimationFrame(step); else { pos = to; layout(); settle(); }
  })(t0);
}
function goTo(i) {
  const d = mod(i - mod(Math.round(target), N) + N / 2, N) - N / 2;
  if (d) go(d);
}
document.getElementById('prev').onclick = () => go(-1);
document.getElementById('next').onclick = () => go(1);
tabs.forEach(t => t.onclick = () => goTo(+t.dataset.i));
cards.forEach((c, i) => c.addEventListener('click', () => { if (!c.classList.contains('active')) goTo(i); }));
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowRight') go(1); if (e.key === 'ArrowLeft') go(-1);
});

let acc = 0, lastWheel = 0, lastAbs = 0, trigAt = 0, locked = false;
document.addEventListener('wheel', e => {
  if (e.ctrlKey) return;
  const horizontal = Math.abs(e.deltaX) > Math.abs(e.deltaY);
  if (!horizontal && e.target.closest('#map')) return;
  e.preventDefault(); e.stopPropagation();
  const d = horizontal ? e.deltaX : e.deltaY, a = Math.abs(d), now = performance.now();
  if (now - lastWheel > 160) { acc = 0; locked = false; }
  else if (locked && now - trigAt > 600 && a > 12 && a > lastAbs * 1.6) { acc = 0; locked = false; }
  lastWheel = now; lastAbs = a;
  if (locked) return;
  acc += d;
  if (Math.abs(acc) > 70) { go(acc > 0 ? 1 : -1); acc = 0; locked = true; trigAt = now; }
}, { passive: false, capture: true });

document.querySelectorAll('.head').forEach(h => {
  let x0 = null;
  h.addEventListener('pointerdown', e => { if (!e.target.closest('button,label,input')) x0 = e.clientX; });
  addEventListener('pointerup', e => {
    if (x0 !== null && Math.abs(e.clientX - x0) > 50) go(e.clientX < x0 ? 1 : -1);
    x0 = null;
  });
});
addEventListener('resize', () => { layout(); map.invalidateSize(); });

/* ---------- Stats & Telemetry State ---------- */
let coords = [], distKm = 0, chart = null, timer = null;
let metrics = { min: 0, kcal: 0, speed: 5, elevMax: null, elevMin: null, elevGain: null, elevSeries: [] };
const $ = id => document.getElementById(id);

const ACT = {
  walk: { speed: 5,  met: [[3, 2.5], [4, 3], [5, 3.5], [6, 4.3], [7, 5.5], [8, 7]] },
  run:  { speed: 10, met: [[7, 6.5], [8, 8.3], [10, 9.8], [11.3, 11], [12.9, 11.8], [14.5, 12.8], [16, 14.5], [20, 18]] },
  bike: { speed: 18, met: [[8, 3.5], [16, 6.8], [19, 8], [22, 10], [25, 12], [30, 15.8]] }
};
let act = 'walk', routeCat = 'Park / Forest';

const interp = (t, v) => {
  if (v <= t[0][0]) return t[0][1];
  for (let i = 1; i < t.length; i++) if (v <= t[i][0]) { const [x0, y0] = t[i-1], [x1, y1] = t[i]; return y0 + (y1 - y0) * (v - x0) / (x1 - x0); }
  return t[t.length - 1][1];
};
const parseTime = s => {
  s = s.trim().replace(',', '.'); if (!s) return 0;
  if (s.includes(':')) {
    const p = s.split(':').map(Number); if (p.some(isNaN)) return 0;
    return p.length === 2 ? p[0] * 60 + p[1] : p.length === 3 ? p[0] * 60 + p[1] + p[2] / 60 : 0;
  }
  const n = parseFloat(s); return n > 0 ? n : 0;
};
function updateStats() {
  const w = +$('w').value, A = ACT[act], own = parseTime($('t').value), useOwn = own > 0 && distKm > 0;
  const min = useOwn ? own : distKm / A.speed * 60, speed = min > 0 ? distKm / (min / 60) : A.speed;
  const kcal = Math.round(interp(A.met, speed) * w * min / 60);
  metrics.min = Math.round(min); metrics.kcal = kcal; metrics.speed = +speed.toFixed(2);
  $('w-val').textContent = w;
  $('d-map').textContent = distKm.toFixed(2);
  $('v-dist').textContent = distKm.toFixed(2);
  $('v-time').textContent = Math.round(min);
  $('l-time').textContent = useOwn ? 'Your time' : 'Estimated time at ' + A.speed + ' km/h';
  $('v-cal').textContent = kcal;
  if (distKm > 0 && min > 0) {
    let pm = Math.floor(60 / speed), ps = Math.round((60 / speed - pm) * 60);
    if (ps === 60) { pm++; ps = 0; }
    $('note').textContent = 'Average pace ' + pm + ':' + String(ps).padStart(2, '0') + ' min/km, ' + speed.toFixed(1) + ' km/h.';
  } else $('note').textContent = 'Draw a route on the first view, or import saved ones.';
}
$('w').addEventListener('input', updateStats);
$('t').addEventListener('input', updateStats);
document.querySelectorAll('#act button').forEach(b => b.onclick = () => {
  act = b.dataset.a;
  document.querySelectorAll('#act button').forEach(x => x.classList.toggle('on', x === b));
  updateStats();
});

/* ---------- Elevation ---------- */
let reqId = 0;
async function getElevations(pts) {
  const lat = pts.map(p => p[1].toFixed(5)).join(','), lon = pts.map(p => p[0].toFixed(5)).join(',');
  try {
    const r = await fetch(`https://api.open-meteo.com/v1/elevation?latitude=${lat}&longitude=${lon}`);
    const d = await r.json();
    if (Array.isArray(d.elevation) && d.elevation.length === pts.length) return d.elevation;
  } catch (e) {}
  const loc = pts.map(p => p[1].toFixed(5) + ',' + p[0].toFixed(5)).join('|');
  const r = await fetch('https://api.opentopodata.org/v1/srtm30m?locations=' + encodeURIComponent(loc));
  const d = await r.json();
  if (!d.results) throw new Error(d.error || 'no data');
  return d.results.map(x => x.elevation);
}
function fetchElevation() {
  if (coords.length < 2) {
    reqId++; if (chart) { chart.destroy(); chart = null; }
    metrics.elevMax = metrics.elevMin = metrics.elevGain = null; metrics.elevSeries = [];
    ['e-max','e-min','e-gain'].forEach(k => $(k).textContent = '–');
    $('e-msg').textContent = 'Draw a route to see its profile.'; return;
  }
  $('e-msg').textContent = 'Loading terrain data…';
  const my = ++reqId;
  const step = Math.max(1, Math.ceil(coords.length / 60)), pts = [];
  for (let i = 0; i < coords.length; i += step) pts.push(coords[i]);
  pts.push(coords[coords.length - 1]);
  const km = []; let acc = 0;
  pts.forEach((p, i) => { if (i) acc += L.latLng(pts[i-1][1], pts[i-1][0]).distanceTo(L.latLng(p[1], p[0])) / 1000; km.push(acc.toFixed(2)); });
  getElevations(pts).then(el => {
      if (my !== reqId) return;
      let gain = 0; el.forEach((v, i) => { if (i && v > el[i-1]) gain += v - el[i-1]; });
      metrics.elevMax = Math.round(Math.max(...el));
      metrics.elevMin = Math.round(Math.min(...el));
      metrics.elevGain = Math.round(gain);
      metrics.elevSeries = el.map((v, i) => ({ km: +km[i], elevation_m: Math.round(v) }));
      $('e-max').textContent = metrics.elevMax;
      $('e-min').textContent = metrics.elevMin;
      $('e-gain').textContent = metrics.elevGain;
      $('e-msg').textContent = 'Elevation along the route, in metres.';
      if (chart) chart.destroy();
      const ctx = $('chart').getContext('2d'), g = ctx.createLinearGradient(0, 0, 0, 320);
      g.addColorStop(0, 'rgba(205,187,152,.28)'); g.addColorStop(1, 'rgba(205,187,152,0)');
      const tick = { color: '#8b8f96', font: { family: 'Jost', size: 12 } };
      chart = new Chart(ctx, { type: 'line',
        data: { labels: km, datasets: [{ data: el, borderColor: '#cdbb98', backgroundColor: g, fill: true, tension: .4, borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false, animation: { duration: 700 },
          plugins: { legend: { display: false }, tooltip: { displayColors: false, backgroundColor: '#12151a', borderColor: 'rgba(236,230,216,.15)', borderWidth: 1, titleColor: '#8b8f96', bodyColor: '#ece6d8',
            callbacks: { title: i => i[0].label + ' km', label: i => Math.round(i.raw) + ' m' } } },
          scales: { x: { ticks: { ...tick, maxTicksLimit: 8 }, grid: { display: false }, border: { color: 'rgba(236,230,216,.1)' } },
                    y: { ticks: tick, grid: { color: 'rgba(236,230,216,.06)' }, border: { display: false } } } } });
    }).catch(err => { if (my === reqId) $('e-msg').textContent = 'Terrain data is unavailable right now (' + (err && err.message ? err.message : 'network') + ').'; });
}

/* ---------- Map ---------- */
const map = L.map('map', { keyboard: false, zoomControl: false }).setView([54.6872, 25.2797], 13);
L.control.zoom({ position: 'bottomright' }).addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19,
  attribution: '© OpenStreetMap contributors' }).addTo(map);

const routes = L.featureGroup().addTo(map), STYLE = { color: '#cdbb98', weight: 3, opacity: .95, lineJoin: 'round' };
let drawing = false, mode = 'freehand', start = null, temp = null, erasing = false;
const eraser = L.circleMarker([0, 0], { radius: 20, color: '#cdbb98', weight: 1, fillOpacity: .08, interactive: false });

function recalc() {
  distKm = 0; coords = [];
  routes.eachLayer(l => {
    const p = l.getLatLngs();
    for (let i = 0; i < p.length - 1; i++) distKm += p[i].distanceTo(p[i+1]) / 1000;
    p.forEach(q => coords.push([q.lng, q.lat]));
  });
  updateStats();
  clearTimeout(timer); timer = setTimeout(fetchElevation, 400);
}
function setDrawing(on) {
  drawing = on;
  document.body.classList.toggle('drawing', on);
  $('draw').classList.toggle('on', on); $('draw').textContent = on ? 'Done' : 'Draw';
  on ? map.dragging.disable() : map.dragging.enable();
  map.getContainer().style.cursor = on ? 'crosshair' : '';
  if (!on) { if (temp) map.removeLayer(temp); temp = start = null; map.removeLayer(eraser); }
  else if (mode === 'eraser') eraser.addTo(map);
}
$('draw').onclick = () => setDrawing(!drawing);
document.querySelectorAll('#seg [data-mode]').forEach(b => b.onclick = () => {
  mode = b.dataset.mode;
  document.querySelectorAll('#seg [data-mode]').forEach(x => x.classList.toggle('on', x === b));
  mode === 'eraser' ? eraser.addTo(map) : map.removeLayer(eraser);
});
$('clear').onclick = () => { routes.clearLayers(); pins.clearLayers(); recalc(); };

/* ---------- Enhanced Save with Analytical Metadata ---------- */
document.querySelectorAll('#rtags button').forEach(b => b.onclick = () => {
  routeCat = b.dataset.cat;
  document.querySelectorAll('#rtags button').forEach(x => x.classList.toggle('on', x === b));
});
$('save').onclick = () => {
  const o = $('savebox').classList.toggle('open');
  $('save').classList.toggle('on', o);
  if (o) $('rname').focus();
};
$('closesave').onclick = () => { $('savebox').classList.remove('open'); $('save').classList.remove('on'); };

$('dlbtn').onclick = () => {
  if (!routes.getLayers().length) { $('smsg').textContent = 'Draw or find a route first before saving.'; return; }
  const rawName = $('rname').value.trim() || 'unnamed_route';
  const slug = rawName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'route';
  const props = {
    route_name: rawName,
    category: routeCat,
    activity: act,
    distance_km: +distKm.toFixed(3),
    estimated_time_min: metrics.min,
    avg_speed_kmh: metrics.speed,
    calories_kcal: metrics.kcal,
    weight_kg: +$('w').value,
    elevation_max_m: metrics.elevMax,
    elevation_min_m: metrics.elevMin,
    elevation_gain_m: metrics.elevGain,
    elevation_profile: metrics.elevSeries,
    saved_at: new Date().toISOString()
  };
  const gj = {
    type: 'FeatureCollection',
    features: routes.getLayers().map((l, idx) => ({
      type: 'Feature',
      properties: { ...props, segment_id: idx + 1 },
      geometry: { type: 'LineString', coordinates: l.getLatLngs().map(p => [p.lng, p.lat]) }
    }))
  };
  const blob = new Blob([JSON.stringify(gj, null, 2)], { type: 'application/geo+json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = slug + '.geojson'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $('smsg').textContent = `Saved "${slug}.geojson" with full telemetry.`;
};

function erase(latlng) {
  const m = map.latLngToContainerPoint(latlng); let changed = false;
  routes.getLayers().forEach(l => {
    const pts = l.getLatLngs(), parts = []; let cur = [], hit = false;
    pts.forEach(p => {
      if (map.latLngToContainerPoint(p).distanceTo(m) < 20) { hit = true; if (cur.length > 1) parts.push(cur); cur = []; } else cur.push(p);
    });
    if (hit) { if (cur.length > 1) parts.push(cur); routes.removeLayer(l); parts.forEach(q => routes.addLayer(L.polyline(q, STYLE))); changed = true; }
  });
  if (changed) recalc();
}
map.on('mousedown', e => {
  if (!drawing) return;
  if (mode === 'eraser') { erasing = true; erase(e.latlng); return; }
  start = e.latlng;
  temp = L.polyline([start, start], mode === 'freehand' ? STYLE : { ...STYLE, dashArray: '2 8', opacity: .7 }).addTo(map);
});
map.on('mousemove', e => {
  if (mode === 'eraser') { eraser.setLatLng(e.latlng); if (erasing) erase(e.latlng); }
  else if (drawing && start && temp) mode === 'freehand' ? temp.addLatLng(e.latlng) : temp.setLatLngs([start, e.latlng]);
});
map.on('mouseup', e => {
  if (mode === 'eraser') { erasing = false; return; }
  if (!drawing || !start) return;
  const a = start, b = e.latlng, far = a.distanceTo(b) > 5;
  start = null;
  if (mode === 'freehand') { if (temp.getLatLngs().length > 2) { map.removeLayer(temp); routes.addLayer(L.polyline(temp.getLatLngs(), STYLE)); recalc(); } else map.removeLayer(temp); temp = null; return; }
  map.removeLayer(temp); temp = null;
  if (!far) return;
  if (mode === 'straight') {
    const n = Math.max(2, Math.floor(a.distanceTo(b) / 5)), pts = [];
    for (let i = 0; i <= n; i++) pts.push(L.latLng(a.lat + (b.lat - a.lat) * i / n, a.lng + (b.lng - a.lng) * i / n));
    routes.addLayer(L.polyline(pts, STYLE)); recalc();
  }
});

/* ---------- Multi-file GeoJSON Import ---------- */
$('file').addEventListener('change', async e => {
  const files = [...e.target.files]; if (!files.length) return;
  routes.clearLayers(); pins.clearLayers();
  for (const f of files) {
    try {
      const txt = await f.text();
      const data = JSON.parse(txt);
      (data.features || []).forEach(ft => {
        if (ft.geometry && ft.geometry.type === 'LineString') {
          const line = L.polyline(ft.geometry.coordinates.map(c => [c[1], c[0]]), STYLE);
          if (ft.properties && ft.properties.route_name) line.bindTooltip(ft.properties.route_name);
          routes.addLayer(line);
        }
      });
    } catch (err) { $('e-msg').textContent = 'One or more files could not be read as GeoJSON.'; }
  }
  if (routes.getLayers().length) map.fitBounds(routes.getBounds(), { padding: [40, 40] });
  recalc();
  e.target.value = '';
});

/* ---------- Places ---------- */
const pins = L.layerGroup().addTo(map), stopsEl = $('stops');
async function photon(q, n, signal) {
  const c = map.getCenter();
  try {
    const r = await fetch('https://photon.komoot.io/api/?limit=' + n + '&lat=' + c.lat.toFixed(4) + '&lon=' + c.lng.toFixed(4) + '&q=' + encodeURIComponent(q), { signal });
    const d = await r.json();
    return (d.features || []).map(f => {
      const p = f.properties, st = p.street ? p.street + (p.housenumber ? ' ' + p.housenumber : '') : '';
      return { main: p.name || st, sub: [p.name ? st : '', p.district || p.city || p.county || p.state].filter(Boolean).join(', '),
               pt: L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]) };
    }).filter(x => x.main);
  } catch (e) { if (e.name === 'AbortError') throw e; return []; }
}
const sug = document.createElement('div'); sug.className = 'sug'; $('places').appendChild(sug);
let sugFor = null, sugItems = [], sugIdx = -1, sugTimer = null, sugCtl = null;
function hideSug() { sug.style.display = 'none'; sugItems = []; sugIdx = -1; }
function pick(it) {
  sugFor.value = it.main + (it.sub ? ', ' + it.sub.split(', ').pop() : ''); sugFor._pt = it.pt; hideSug();
}
function showSug(i, items) {
  sugFor = i; sugItems = items; sugIdx = -1;
  if (!items.length) return hideSug();
  sug.innerHTML = '';
  items.forEach(it => {
    const d = document.createElement('div'); d.textContent = it.main;
    if (it.sub) { const s = document.createElement('small'); s.textContent = it.sub; d.appendChild(s); }
    d.onmousedown = e => { e.preventDefault(); pick(it); };
    sug.appendChild(d);
  });
  Object.assign(sug.style, { display: 'block', top: (i.offsetTop + i.offsetHeight) + 'px', left: i.offsetLeft + 'px', width: i.offsetWidth + 'px' });
}
function addField(ph, before) {
  const i = document.createElement('input');
  i.type = 'text'; i.placeholder = ph; i.autocomplete = 'off'; i.spellcheck = false;
  i.oninput = () => {
    i._pt = null; clearTimeout(sugTimer);
    const q = i.value.trim(); if (q.length < 2) return hideSug();
    sugTimer = setTimeout(async () => {
      if (sugCtl) sugCtl.abort(); sugCtl = new AbortController();
      try { showSug(i, await photon(q, 6, sugCtl.signal)); } catch (e) {}
    }, 280);
  };
  i.onblur = () => setTimeout(hideSug, 120);
  i.onkeydown = e => {
    if (sug.style.display === 'block' && sugFor === i && sugItems.length) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); sugIdx = mod(sugIdx + (e.key === 'ArrowDown' ? 1 : -1), sugItems.length);
        [...sug.children].forEach((c, k) => c.classList.toggle('hl', k === sugIdx)); return;
      }
      if (e.key === 'Enter' && sugIdx >= 0) { e.preventDefault(); pick(sugItems[sugIdx]); return; }
      if (e.key === 'Escape') return hideSug();
    }
    if (e.key === 'Enter') $('find').click();
  };
  stopsEl.insertBefore(i, before || null); return i;
}
addField('Start'); addField('Destination');
$('pl').onclick = () => { const o = $('places').classList.toggle('open'); $('pl').classList.toggle('on', o); };
$('addstop').onclick = () => addField('Stop', stopsEl.lastElementChild).focus();
const say = t => { $('pmsg').textContent = t; };

async function geocode(q) {
  const m = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (m) return L.latLng(+m[1], +m[2]);
  const f = await photon(q, 1); if (f.length) return f[0].pt;
  const b = map.getBounds();
  try {
    const r = await fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=' + encodeURIComponent(q) +
      '&viewbox=' + [b.getWest(), b.getNorth(), b.getEast(), b.getSouth()].join(','));
    const d = await r.json();
    if (d.length) return L.latLng(+d[0].lat, +d[0].lon);
  } catch (e) {}
  throw new Error('Could not find “' + q + '”. Try a street and number, or pick one from the suggestions.');
}
async function routeVia(pts) {
  const c = pts.map(p => p.lng.toFixed(6) + ',' + p.lat.toFixed(6)).join(';'), inst = act === 'bike' ? 'bike' : 'foot';
  for (const prof of ['driving', inst]) {
    try {
      const r = await fetch(`https://routing.openstreetmap.de/routed-${inst}/route/v1/${prof}/${c}?overview=full&geometries=geojson`);
      const d = await r.json();
      if (d.routes && d.routes.length) return d.routes[0].geometry.coordinates.map(x => [x[1], x[0]]);
    } catch (e) {}
  }
  throw new Error('No ' + (inst === 'bike' ? 'cycling' : 'walking') + ' route found between these places.');
}
$('find').onclick = async () => {
  const ins = [...stopsEl.querySelectorAll('input')].filter(i => i.value.trim()), qs = ins.map(i => i.value.trim()), btn = $('find');
  if (qs.length < 2) return say('Enter at least a start and a destination.');
  btn.disabled = true; btn.textContent = 'Finding…';
  try {
    const pts = [];
    for (let i = 0; i < qs.length; i++) { say('Finding ' + qs[i] + '…'); pts.push(ins[i]._pt || await geocode(qs[i])); }
    say('Planning the route…');
    const line = await routeVia(pts);
    routes.clearLayers(); pins.clearLayers();
    routes.addLayer(L.polyline(line, STYLE));
    pts.forEach((p, i) => L.circleMarker(p, { radius: 5, color: '#12151a', weight: 2, fillColor: '#cdbb98', fillOpacity: 1 })
      .bindTooltip(qs[i].split(',')[0], { permanent: true, direction: 'top', offset: [0, -6] }).addTo(pins));
    map.fitBounds(routes.getBounds(), { paddingTopLeft: [Math.min(360, map.getSize().x * .4), 60], paddingBottomRight: [60, 60] });
    recalc();
    say('Route found: ' + distKm.toFixed(2) + ' km. Time and energy are in Statistics.');
  } catch (e) { say(e.message || 'Something went wrong. Try again.'); }
  btn.disabled = false; btn.textContent = 'Find route';
};

layout(); settle(); updateStats();
</script>
</body></html>
"""

st.iframe(html_code, height=860)
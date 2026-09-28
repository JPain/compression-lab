// Screenshot Compression Lab -- the comparison viewer and the hold-to-compare
// figures. MIT licence. Reads data.json, written by tools/generate.py.
"use strict";

const SECTIONS = [
  { id: "webp-quality", title: "WebP quality", intro: "The main dial: how coarsely fine detail is rounded away. Every row is 1920 × 1080 and judged against the lossless 1920 × 1080 version." },
  { id: "webp-options", title: "Other WebP options", intro: "The same quality 82, with the encoder doing something different." },
  { id: "colour", title: "Colour resolution", intro: "Only the brightness/colour steps, with no compression, to show what each costs on its own." },
  { id: "jpeg", title: "JPEG", intro: "The long-standing format. Standard JPEG halves colour, like WebP." },
  { id: "avif", title: "AVIF", intro: "Built on the AV1 video codec. Current browsers display it; older iPhones and some link-preview crawlers don't." },
  { id: "jxl", title: "JPEG XL", intro: "The strongest at high quality here. By default it doesn't halve colour. Browser support is still patchy." },
  { id: "resolution", title: "Resolution", intro: "Judged against the 4K original as a 4K screen would show it full-screen: the harshest view. A forum column is narrower than all of these." }
];
const REGIONS = [
  { id: "van", label: "Van & buttons", tests: "grass texture, sharp icons, a thin blue trim on red" },
  { id: "sky", label: "Compass & sky", tests: "small lettering, fine dots and a smooth gradient" },
  { id: "tower", label: "Tower struts", tests: "thin dark diagonals against rock" },
  { id: "trees", label: "Distant trees", tests: "soft, low-contrast detail" },
  { id: "gauges", label: "Health gauges", tests: "bright coloured rings" }
];
const BANDS = [
  { min: 90, name: "visually lossless", v: "--s-vl" }, { min: 80, name: "very high", v: "--s-vh" },
  { min: 70, name: "high", v: "--s-hi" }, { min: 50, name: "medium", v: "--s-med" }, { min: -1e9, name: "low", v: "--s-low" }
];
const ZOOMS = [["fit", "Fit"], ["1", "1×"], ["2", "2×"], ["3", "3×"]];
const RENDERS = [["pixelated", "Sharp"], ["smooth", "Smooth"]];
const SHOWS = [["all", "All"], ["short", "Shortlist"]];

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const band = s => BANDS.find(b => s >= b.min);
const kb = n => n >= 1024 * 1000 ? (n / 1048576).toFixed(2) + " MB" : (n / 1024).toFixed(1) + " KB";
const store = {
  get(k, d) { try { return localStorage.getItem("lab." + k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("lab." + k, v); } catch {} }
};
const pick = (k, list, d) => { const v = store.get(k, d); return list.some(x => (x.id ?? x[0]) === v) ? v : d; };
const state = { region: pick("region", REGIONS, "van"), zoom: pick("zoom", ZOOMS, "2"), render: pick("render", RENDERS, "pixelated"), show: pick("show", SHOWS, "all") };
// The shortlist is kept in this browser only, like the other viewer settings.
const shortlist = new Set((() => { try { return JSON.parse(store.get("shortlist", "[]")); } catch { return []; } })());
const saveShortlist = () => store.set("shortlist", JSON.stringify([...shortlist]));
let ROWS = [];

// ---- hold to compare: works for the explanation figures and every viewer row
function hold(fig, on) {
  const img = fig.querySelector("img");
  img.src = on ? fig.dataset.b : fig.dataset.a;
  fig.classList.toggle("flip", on);
  const hint = fig.querySelector(".holdhint");
  if (hint) { hint.dataset.idle ??= hint.textContent; hint.textContent = on ? "showing the comparison" : hint.dataset.idle; }
}
document.addEventListener("pointerdown", e => {
  const fig = e.target.closest("figure.cmp"); if (!fig) return;
  e.preventDefault(); hold(fig, true);
  const end = () => { hold(fig, false); removeEventListener("pointerup", end); removeEventListener("pointercancel", end); };
  addEventListener("pointerup", end); addEventListener("pointercancel", end);
});
document.addEventListener("contextmenu", e => { if (e.target.closest("figure.cmp")) e.preventDefault(); });
document.addEventListener("keydown", e => { const f = e.target.closest?.("figure.cmp"); if (f && (e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); hold(f, true); } });
document.addEventListener("keyup", e => { const f = e.target.closest?.("figure.cmp"); if (f && (e.key === " " || e.key === "Enter")) hold(f, false); });

// ---- viewer ------------------------------------------------------------------
fetch("data.json").then(r => r.json()).then(init).catch(() => {});

function init(data) {
  ROWS = data.rows;
  for (const [k, v] of Object.entries(data.tools || {})) { const el = $("v-" + k); if (el) el.textContent = v; }

  const map = $("map");
  REGIONS.forEach(r => {
    const [x0, y0, x1, y1] = data.regions[r.id], b = document.createElement("button");
    b.type = "button"; b.dataset.region = r.id; b.textContent = r.label; b.title = `${r.label}: ${r.tests}`;
    Object.assign(b.style, { left: x0 / 19.2 + "%", top: y0 / 10.8 + "%", width: (x1 - x0) / 19.2 + "%", height: (y1 - y0) / 10.8 + "%" });
    b.addEventListener("click", () => set("region", r.id));
    map.append(b);
  });
  $("legend").innerHTML = `<span>SSIMULACRA 2, 100 = identical:</span>` +
    [...BANDS].reverse().map(b => `<span><i style="background:var(${b.v})"></i>${b.min > 0 ? b.min + "+" : "below 50"} ${b.name}</span>`).join("");

  const seg = (id, items, key) => {
    $(id).innerHTML = items.map(([v, l]) => `<button type="button" data-v="${v}">${l}</button>`).join("");
    $(id).addEventListener("click", e => { const b = e.target.closest("button"); if (b) set(key, b.dataset.v); });
  };
  seg("regionSeg", REGIONS.map(r => [r.id, r.label]), "region");
  seg("zoomSeg", ZOOMS, "zoom");
  seg("renderSeg", RENDERS, "render");
  seg("showSeg", SHOWS, "show");
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-star]"); if (!b) return;
    const id = b.dataset.star;
    shortlist.has(id) ? shortlist.delete(id) : shortlist.add(id);
    saveShortlist(); apply();
  });
  $("jump").innerHTML = SECTIONS.map(s => `<a href="#v-${s.id}">${s.title}</a>`).join("");

  $("rows").innerHTML = SECTIONS.map(sec => `
    <section class="vsec" id="v-${sec.id}">
      <div class="vsec-head"><h3>${sec.title}</h3><p>${sec.intro}</p></div>
      ${data.rows.filter(r => r.section === sec.id).map(row).join("")}
    </section>`).join("");
  apply();
}

function row(r) {
  const b = band(r.score), ref = r.ref === "4k" ? "ref4k" : "ref1080";
  const size = r.bytes == null ? `<span class="chip">not compressed</span>`
    : `<span class="chip"><b class="num">${kb(r.bytes)}</b></span><span class="chip"><b class="num">${Math.round(r.ratio)}×</b> smaller</span>`;
  return `<article class="row${r.served ? " current" : ""}" id="row-${r.id}" data-row="${r.id}">
    <div class="row-head"><h4>${esc(r.label)}</h4>
      <div class="stats">
        ${r.served ? `<span class="chip now">Served by the host · rank ${r.served}</span>` : ""}
        <span class="chip score num" style="background:var(${b.v})">${r.score.toFixed(1)} · ${b.name}</span>
        ${size}<span class="chip"><b class="num">${r.dims}</b></span>
        ${r.ms == null ? "" : `<span class="chip">encode <b class="num">${r.ms} ms</b></span>`}
      </div>
      <button type="button" class="star" data-star="${r.id}" aria-pressed="false"><span aria-hidden="true">☆</span> Shortlist</button></div>
    ${r.note ? `<p class="rownote">${esc(r.note)}</p>` : ""}
    <div class="pair">
      <figure class="tile"><img data-id="${ref}" alt="" loading="lazy" decoding="async" width="441" height="270"><figcaption>Original · lossless ${r.ref === "4k" ? "3840 × 2160" : "1920 × 1080"}</figcaption></figure>
      <figure class="tile cmp" tabindex="0" data-id="${r.id}" data-ref="${ref}" aria-label="${esc(r.label)}. Hold to show the original here.">
        <img data-id="${r.id}" alt="" loading="lazy" decoding="async" width="441" height="270">
        <figcaption>${esc(r.label)} · <span class="holdhint">hold to compare</span></figcaption></figure>
    </div></article>`;
}

function set(key, v) { state[key] = v; store.set(key, v); apply(); }

function apply() {
  const reg = REGIONS.find(r => r.id === state.region);
  document.querySelectorAll("#rows figure.cmp").forEach(f => {
    f.dataset.a = `tiles/${state.region}_${f.dataset.id}.png`;
    f.dataset.b = `tiles/${state.region}_${f.dataset.ref}.png`;
  });
  document.querySelectorAll("#rows img[data-id]").forEach(img => { img.src = `tiles/${state.region}_${img.dataset.id}.png`; img.alt = `${reg.label} crop`; });
  document.querySelectorAll("[data-region]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.region === state.region)));
  for (const [id, key] of [["regionSeg", "region"], ["zoomSeg", "zoom"], ["renderSeg", "render"]])
    document.querySelectorAll(`#${id} button`).forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === state[key])));
  // shortlist: stars, the Show filter, and the summary table
  document.querySelectorAll("#rows [data-star]").forEach(b => {
    const on = shortlist.has(b.dataset.star);
    b.setAttribute("aria-pressed", String(on));
    b.innerHTML = `<span aria-hidden="true">${on ? "★" : "☆"}</span> ${on ? "Shortlisted" : "Shortlist"}`;
    b.closest("article").classList.toggle("starred", on);
  });
  const only = state.show === "short";
  document.querySelectorAll("#rows article[data-row]").forEach(a => a.hidden = only && !shortlist.has(a.dataset.row));
  document.querySelectorAll("#rows .vsec").forEach(s => s.hidden = only && !s.querySelector("article[data-row]:not([hidden])"));
  const showBtn = document.querySelector('#showSeg button[data-v="short"]');
  if (showBtn) showBtn.textContent = `Shortlist (${shortlist.size})`;
  renderShortlist(only);
  const root = document.documentElement;
  root.style.setProperty("--tile-w", state.zoom === "fit" ? "50%" : `calc(441px * ${state.zoom})`);
  root.classList.toggle("smooth", state.render === "smooth");
}

function renderShortlist(only) {
  const box = $("shortlist"); if (!box) return;
  const picked = ROWS.filter(r => shortlist.has(r.id)).sort((a, b) => (a.bytes ?? Infinity) - (b.bytes ?? Infinity));
  if (!picked.length) {
    box.hidden = !only;
    box.innerHTML = `<p class="note">Nothing shortlisted yet. Press <b>☆ Shortlist</b> on any row to add it.</p>`;
    return;
  }
  box.hidden = false;
  box.innerHTML = `<h3>Shortlist <span class="note">smallest file first</span></h3>
    <div class="tablewrap"><table><thead><tr><th>Setting</th><th class="n">Size</th><th class="n">Score</th><th class="n">Smaller by</th><th></th></tr></thead><tbody>
    ${picked.map(r => { const b = band(r.score); return `<tr${r.served ? ' class="hl"' : ""}>
      <td><a href="#row-${r.id}">${esc(r.label)}</a>${r.served ? ` <span class="chip now">Served · rank ${r.served}</span>` : ""}</td>
      <td class="n">${r.bytes == null ? "–" : kb(r.bytes)}</td>
      <td class="n"><span class="chip score num" style="background:var(${b.v})">${r.score.toFixed(1)}</span></td>
      <td class="n">${r.ratio == null ? "–" : Math.round(r.ratio) + "×"}</td>
      <td class="n"><button type="button" class="star small" data-star="${r.id}" aria-label="Remove ${esc(r.label)} from the shortlist">Remove</button></td></tr>`; }).join("")}
    </tbody></table></div>`;
}

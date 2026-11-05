"use strict";
const $ = (id) => document.getElementById(id);
const state = { plate: null, analysis: null, draft: new Map() };
const fmt = (value) =>
  value === null || value === undefined
    ? "Unavailable"
    : Number(value).toPrecision(4);
function status(message, error = false) {
  $("status").textContent = message;
  $("status").className = error ? "error" : "";
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(value.detail)
      ? value.detail.map((e) => e.loc.join(".") + ": " + e.msg).join("; ")
      : value.detail;
    throw new Error(
      detail || "Request failed. Check your inputs and try again.",
    );
  }
  return value;
}
const post = (path, value) =>
  api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  });
function action(id, event, fn) {
  $(id).addEventListener(event, async (e) => {
    e.preventDefault();
    const button =
      e.submitter ||
      (e.currentTarget.tagName === "BUTTON" ? e.currentTarget : null);
    if (button) button.disabled = true;
    status("Working…");
    try {
      await fn(e);
    } catch (error) {
      status(error.message, true);
    } finally {
      if (button) button.disabled = false;
      syncEnabled();
    }
  });
}
function option(select, value, text) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = text;
  select.append(o);
}
function resetOptions(id, items, label, selected = "") {
  const el = $(id);
  el.replaceChildren();
  option(el, "", label);
  for (const item of items) option(el, item.id, item.name || item.id);
  el.value = String(selected || "");
}
async function refresh() {
  const [samples, lots, plates] = await Promise.all([
    api("/api/samples"),
    api("/api/lots"),
    api("/api/plates"),
  ]);
  const selected = $("plate-select").value;
  resetOptions("plate-select", plates, "Choose a plate", selected);
  resetOptions(
    "lot-select",
    lots,
    "Choose a reagent lot",
    $("lot-select").value,
  );
  resetOptions("new-sample", samples, "Choose a sample", $("new-sample").value);
  $("sample-list").textContent = samples.length
    ? samples.map((s) => s.id + ": " + s.description).join(" · ")
    : "No samples registered.";
  $("lot-list").textContent = lots.length
    ? lots.map((l) => l.id + " · expires " + l.expires_on).join(" / ")
    : "No lots registered.";
  await history();
}
function syncEnabled() {
  const has = !!state.plate;
  $("import-button").disabled = !has;
  $("generate").disabled = !has;
  $("analyse-button").disabled = !has || !$("import-select").value;
}
async function history() {
  const events = await api("/api/audit");
  $("audit").replaceChildren();
  for (const event of events.slice(-100).reverse()) {
    const row = document.createElement("tr");
    for (const value of [
      event.at.slice(0, 19).replace("T", " "),
      event.actor,
      event.action,
      event.entity,
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    $("audit").append(row);
  }
}
function drawPlate() {
  $("well-detail").textContent = "Select a well to inspect its contents.";
  const grid = $("plate-grid");
  grid.replaceChildren();
  const label = (text) => {
    const el = document.createElement("span");
    el.textContent = text;
    grid.append(el);
  };
  label("");
  for (let i = 1; i <= 12; i++) label(i);
  const wells = new Map((state.plate?.wells || []).map((w) => [w.well, w]));
  for (const row of "ABCDEFGH") {
    label(row);
    for (let col = 1; col <= 12; col++) {
      const address = row + col,
        well = wells.get(address),
        button = document.createElement("button");
      button.type = "button";
      button.textContent = address;
      button.className = well ? well.role : "empty";
      button.setAttribute(
        "aria-label",
        address + ": " + (well ? well.role : "unassigned"),
      );
      const result = state.analysis?.result.wells[address];
      if (result?.flags.length) button.classList.add("well-fail");
      button.addEventListener("click", () => {
        $("well-detail").textContent =
          address +
          ": " +
          (well
            ? well.role +
              (well.sample_id
                ? " · Sample " +
                  well.sample_id +
                  " · Dilution factor " +
                  well.dilution_factor
                : "") +
              (well.role === "standard"
                ? " · Known concentration " +
                  fmt(well.concentration) +
                  " " +
                  state.plate.unit
                : "")
            : "Unassigned") +
          (result
            ? " · Raw signal " +
              fmt(result.raw) +
              " · Corrected signal " +
              fmt(result.corrected) +
              " · Concentration " +
              fmt(result.concentration) +
              " " +
              (state.plate?.unit || "") +
              " · " +
              (result.flags.join(", ") || "No well flags")
            : "");
      });
      grid.append(button);
    }
  }
}
async function loadPlate(id) {
  state.plate = id ? await api("/api/plates/" + id) : null;
  state.analysis = null;
  $("results").hidden = true;
  $("protocol-result").hidden = true;
  $("import-select").replaceChildren();
  $("analysis-select").replaceChildren();
  option($("analysis-select"), "", "Choose a result");
  if (state.plate) {
    const p = state.plate;
    $("plate-detail").textContent =
      p.name +
      " · " +
      p.wells.length +
      " mapped wells · Lot " +
      p.lot_id +
      " · Expires " +
      p.lot.expires_on +
      " · " +
      p.unit;
    for (const i of p.imports)
      option($("import-select"), i.id, "#" + i.id + " · " + i.name);
    if (p.imports.length) $("import-select").value = p.imports.at(-1).id;
    for (const a of p.analyses)
      option(
        $("analysis-select"),
        a.id,
        "#" + a.id + " · " + a.model + " · import #" + a.import_id,
      );
    if (p.analyses.length) {
      $("analysis-select").value = p.analyses.at(-1).id;
      await loadAnalysis(p.analyses.at(-1).id);
    }
  } else
    $("plate-detail").textContent =
      "No plate selected. Open the demo or save a new plate map.";
  drawPlate();
  syncEnabled();
}
async function loadAnalysis(id) {
  if (!id) {
    state.analysis = null;
    $("results").hidden = true;
    drawPlate();
    return;
  }
  state.analysis = await api("/api/analyses/" + id);
  const r = state.analysis.result;
  $("results").hidden = false;
  $("qc-status").textContent = r.passed
    ? "Quality checks passed"
    : "Review required";
  $("qc-status").className = r.passed ? "pass" : "fail";
  $("qc-summary").textContent =
    "Analysis #" +
    id +
    " · Import #" +
    state.analysis.import_id +
    " · " +
    r.model +
    " · Blank mean " +
    fmt(r.blank_mean) +
    " · R² " +
    fmt(r.fit.r_squared) +
    " · Z-prime " +
    fmt(r.z_prime) +
    ". Limits: R² ≥ 0.98, CV ≤ 20%, Z-prime ≥ 0.5.";
  $("csv-link").href = "/api/analyses/" + id + "/csv";
  $("qc-flags").replaceChildren();
  const flags = [
    ...r.flags,
    ...Object.entries(r.wells).flatMap(([w, v]) =>
      v.flags.map((f) => w + ": " + f),
    ),
    ...r.groups.flatMap((g) => g.flags.map((f) => g.key + ": " + f)),
  ];
  for (const flag of flags) {
    const li = document.createElement("li");
    li.textContent = flag;
    $("qc-flags").append(li);
  }
  $("sample-results").replaceChildren();
  for (const group of r.groups.filter((g) => g.key.startsWith("sample:"))) {
    const row = document.createElement("tr");
    const flags = [
      ...group.flags,
      ...group.wells.flatMap((w) => r.wells[w].flags),
    ];
    for (const value of [
      group.key.slice(7),
      fmt(group.concentration) + " " + state.plate.unit,
      fmt(group.cv_percent),
      flags.join(", ") || "Pass",
    ]) {
      const td = document.createElement("td");
      td.textContent = value;
      row.append(td);
    }
    $("sample-results").append(row);
  }
  drawCurve(r.fit);
  drawPlate();
}
function drawCurve(fit) {
  const svg = $("curve");
  svg.replaceChildren();
  const make = (name, attrs, text) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    if (text !== undefined) el.textContent = text;
    svg.append(el);
    return el;
  };
  const max = fit.concentration_range[1],
    xmin = 55,
    xmax = 580,
    ymin = 25,
    ymax = 245;
  const points = fit.standards,
    low = Math.min(...points.map((p) => p.signal)),
    high = Math.max(...points.map((p) => p.signal));
  const x = (v) => xmin + (Math.log1p(v) / Math.log1p(max)) * (xmax - xmin);
  const y = (v) => ymax - ((v - low) / (high - low || 1)) * (ymax - ymin);
  make("line", { x1: xmin, y1: ymax, x2: xmax, y2: ymax, class: "axis" });
  make("line", { x1: xmin, y1: ymin, x2: xmin, y2: ymax, class: "axis" });
  make(
    "text",
    { x: 250, y: 290, class: "plot-label" },
    "Concentration (" + state.plate.unit + ")",
  );
  make("text", { x: 8, y: 14, class: "plot-label" }, "Corrected signal");
  for (const value of [0, max / 100, max / 10, max])
    make(
      "text",
      { x: x(value), y: 265, class: "plot-tick", "text-anchor": "middle" },
      fmt(value),
    );
  for (const value of [low, (low + high) / 2, high])
    make(
      "text",
      { x: 48, y: y(value) + 4, class: "plot-tick", "text-anchor": "end" },
      fmt(value),
    );
  const p = fit.parameters;
  const response = (v) =>
    fit.model === "linear"
      ? p.slope * v + p.intercept
      : p.low + (p.high - p.low) / (1 + (v / p.ec50) ** p.hill);
  let d = "";
  for (let i = 0; i <= 120; i++) {
    const v = Math.expm1((i / 120) * Math.log1p(max));
    d +=
      (i ? "L" : "M") + x(v).toFixed(2) + "," + y(response(v)).toFixed(2) + " ";
  }
  make("path", { d, class: "curve-line" });
  for (const point of points)
    make("circle", {
      cx: x(point.concentration),
      cy: y(point.signal),
      r: 3,
      class: "curve-point",
    });
}
function renderDraft() {
  $("map-count").textContent = state.draft.size + " wells assigned";
  $("draft-map").replaceChildren();
  for (const [address, well] of state.draft) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.textContent = address + " · " + well.role + " · remove";
    button.addEventListener("click", () => {
      state.draft.delete(address);
      renderDraft();
    });
    $("draft-map").append(button);
  }
}
function roleFields() {
  const sample = $("new-role").value === "sample";
  $("sample-label").hidden = !sample;
  $("dilution-label").hidden = !sample;
  $("concentration-label").hidden = $("new-role").value !== "standard";
}
action("demo", "click", async () => {
  const result = await post("/api/demo", {});
  await refresh();
  $("plate-select").value = result.plate_id;
  await loadPlate(result.plate_id);
  status(
    "Synthetic demo loaded. DEMO-S1 is 7 ng/mL; DEMO-S2 is 12 ng/mL. Review the recovered results below.",
  );
});
action("plate-select", "change", async () => {
  await loadPlate($("plate-select").value);
  status("Plate loaded.");
});
action("analysis-select", "change", async () => {
  await loadAnalysis($("analysis-select").value);
  status("Saved analysis loaded.");
});
action("import-form", "submit", async () => {
  const data = new FormData();
  data.append("file", $("reader-file").files[0]);
  const result = await api("/api/plates/" + state.plate.id + "/imports", {
    method: "POST",
    body: data,
  });
  await loadPlate(state.plate.id);
  $("import-select").value = result.id;
  await history();
  status(
    "Reader import #" +
      result.id +
      " saved. Choose a curve and calculate the results.",
  );
});
action("analysis-form", "submit", async () => {
  const result = await post(
    "/api/imports/" + $("import-select").value + "/analyses",
    { model: $("model").value },
  );
  await loadPlate(state.plate.id);
  $("analysis-select").value = result.id;
  await loadAnalysis(result.id);
  await history();
  status("Analysis #" + result.id + " saved with its quality checks.");
});
for (const kind of ["sample", "lot"])
  action(kind + "-form", "submit", async () => {
    const form = $(kind + "-form");
    await post(
      "/api/" + (kind === "sample" ? "samples" : "lots"),
      Object.fromEntries(new FormData(form)),
    );
    form.reset();
    await refresh();
    status((kind === "sample" ? "Sample" : "Reagent lot") + " registered.");
  });
action("template", "click", async () => {
  const wells = await api("/api/templates/synthetic-map");
  state.draft = new Map(wells.map((w) => [w.well, w]));
  renderDraft();
  status(
    "Demo layout copied into your draft. Register DEMO-S1 and DEMO-S2 before saving, or assign your own sample IDs.",
  );
});
action("assign", "click", async () => {
  const address = $("new-well")
    .value.trim()
    .toUpperCase()
    .replace(/^([A-H])0/, "$1");
  if (!/^[A-H]([1-9]|1[0-2])$/.test(address))
    throw new Error("Use a well address from A1 through H12.");
  const role = $("new-role").value;
  const well = { well: address, role };
  if (role === "standard")
    well.concentration = Number($("new-concentration").value);
  if (role === "sample") {
    well.sample_id = $("new-sample").value;
    well.dilution_factor = Number($("new-dilution").value);
    if (!well.sample_id) throw new Error("Register and choose a sample first.");
  }
  state.draft.set(address, well);
  renderDraft();
  status(address + " assigned to the draft.");
});
action("clear-map", "click", async () => {
  state.draft.clear();
  renderDraft();
  status("Draft map cleared. Saved records are unchanged.");
});
action("plate-form", "submit", async () => {
  if (!state.draft.size)
    throw new Error("Assign at least one well before saving.");
  const p = await post("/api/plates", {
    name: $("plate-name").value,
    lot_id: $("lot-select").value,
    unit: $("unit").value,
    wells: [...state.draft.values()],
  });
  await refresh();
  $("plate-select").value = p.id;
  await loadPlate(p.id);
  status("Plate map saved. It is ready for a reader export.");
});
$("new-role").addEventListener("change", roleFields);
roleFields();
$("protocol-kind").addEventListener("change", () => {
  const serial = $("protocol-kind").value === "serial";
  $("serial-fields").hidden = !serial;
  $("transfer-fields").hidden = serial;
});
action("robot-form", "submit", async () => {
  const kind = $("protocol-kind").value;
  let request = { kind };
  if (kind === "serial") {
    request = {
      ...request,
      steps: Number($("steps").value),
      factor: Number($("factor").value),
      final_volume: Number($("final-volume").value),
      row: $("robot-row").value,
    };
  } else {
    const lines = (value) =>
      value
        .trim()
        .split(/\r?\n/)
        .filter(Boolean)
        .map((line) => line.split(",").map((v) => v.trim()));
    const moves = lines($("moves").value),
      stock = lines($("stock").value);
    if (moves.some((a) => a.length !== 3) || stock.some((a) => a.length !== 2))
      throw new Error(
        "Use the labelled comma-separated format for each transfer and source volume.",
      );
    if (new Set(stock.map((a) => a[0])).size !== stock.length)
      throw new Error("Use one loading volume per source well.");
    request.moves = moves.map(([source, destination, volume]) => ({
      source,
      destination,
      volume: Number(volume),
    }));
    request.source_volumes = Object.fromEntries(
      stock.map(([well, v]) => [well, Number(v)]),
    );
  }
  const result = await post(
    "/api/plates/" + state.plate.id + "/protocols",
    request,
  );
  $("protocol-result").hidden = false;
  $("protocol-link").href = "/api/protocols/" + result.id + "/file";
  $("robot-plan").textContent = JSON.stringify(result.plan, null, 2);
  await history();
  status(
    "Protocol generated and recorded. Download it, then simulate that exact file.",
  );
});
action("refresh-history", "click", async () => {
  await history();
  status("Audit history refreshed. Showing the latest 100 events.");
});
drawPlate();
refresh()
  .then(syncEnabled)
  .catch((error) => status(error.message, true));

import {
  safeStr,
  iterCellSpaces,
  iterDualNodes,
  iterDualEdges,
  polygon2dToRings,
  polyhedronToTris,
  bboxFromPoints,
  pushRingPairs
} from "./geometry.js";

// Global State
let MODEL = null;
let RESULT2D = null;
let ROUTE = null;
let CURRENT_LEVEL = "__all__";
let CURRENT_MODE = "3d";
let SHOW_RESULT = true;
let SHOW_ROUTE = true;
let SHOW_DUAL = false;
let SHOW_SEG_MARKERS = true;
let SHOW_SEG_LABELS = false;
let ROUTE_SEGMENTS = [];

const plot3d = document.getElementById("plot3d");
const plot2d = document.getElementById("plot2d");
const statusDiv = document.getElementById("status");
const fileInput = document.getElementById("file-input");
const uploadButton = document.getElementById("upload-button");

/* ---------- Build Model (Enhanced logic from your working version) ---------- */

function buildBaseModel(indoorjson) {
  const cells = iterCellSpaces(indoorjson);
  const levels = new Set();
  const byLevel3d = new Map();
  const byLevel2d = new Map();
  const layers = indoorjson.layers || indoorjson.indoorFeatures?.layers || [];
  const thematicLayerCount = Array.isArray(layers) ? layers.length : 0;
  const nodes = iterDualNodes(indoorjson);
  const edges = iterDualEdges(indoorjson);

  const addLevel = (lvl) => {
    levels.add(lvl);
    if (!byLevel3d.has(lvl)) byLevel3d.set(lvl, { x: [], y: [], z: [], i: [], j: [], k: [] });
    if (!byLevel2d.has(lvl)) byLevel2d.set(lvl, { pairs: [] });
  };

  for (const cs of cells) {
    const lvl = safeStr(cs.level) || safeStr(cs.storey) || "UNKNOWN";
    addLevel(lvl);

    const geom = cs.cellSpaceGeom || cs.CellSpaceGeom || {};
    const g3 = geom.geometry3D || null;
    const g2 = geom.geometry2D || null;

    // 3D Logic
    if (g3 && g3.type === "Polyhedron") {
      const tris = polyhedronToTris(g3);
      const store = byLevel3d.get(lvl);
      for (const tri of tris) {
        const base = store.x.length;
        for (const p of tri) {
          store.x.push(p[0]); store.y.push(p[1]); store.z.push(p[2] ?? 0);
        }
        store.i.push(base); store.j.push(base + 1); store.k.push(base + 2);
      }
    }

    // 2D Logic - FIXED TO PREVENT OVERLAP
    const store2 = byLevel2d.get(lvl);
    if (g2 && (g2.type === "Polygon" || g2.type === "MultiPolygon")) {
      const rings = polygon2dToRings(g2);
      for (const ring of rings) {
        pushRingPairs(store2.pairs, ring); 
      }
    } 
    // Only use 3D bounding box if 2D is completely missing
    else if (g3 && g3.type === "Polyhedron") {
      const tris = polyhedronToTris(g3);
      const pts = tris.flat();
      const bb = bboxFromPoints(pts);
      if (bb) {
        const [x0, y0] = bb.min;
        const [x1, y1] = bb.max;
        pushRingPairs(store2.pairs, [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]);
      }
    }
  }

  return {
    _src: indoorjson,
    levels: Array.from(levels).sort(),
    byLevel3d,
    byLevel2d,
    dualNodes: nodes,
    dualEdges: edges,
    stats: {
      thematicLayers: thematicLayerCount,
      cellSpaces: cells.length,
      nodes: nodes.length,
      edges: edges.length
    }
  };
}

/* ---------- Rendering ---------- */

function renderAll() {
  if (!MODEL) return;
  // Update Level Dropdown
  const sel = document.getElementById("level");
  sel.innerHTML = '<option value="__all__">All</option>';
  for (const lvl of MODEL.levels) {
    const o = document.createElement("option");
    o.value = lvl; o.textContent = lvl; sel.appendChild(o);
  }

  render3D();
  render2D();
}

function render3D() {
  const traces = [];
  if (!MODEL) return;

  let zMin = -Infinity;
  let zMax = Infinity;

  // 1. Calculate Z-Bounds for the CURRENT_LEVEL
  if (CURRENT_LEVEL !== "__all__") {
    const base = MODEL.byLevel3d.get(CURRENT_LEVEL);
    if (base && base.z.length > 0) {
      // Find the min and max Z of the floor's 3D rooms
      const validZ = base.z.filter(v => v !== null && v !== undefined);
      zMin = Math.min(...validZ);
      zMax = Math.max(...validZ);
      
      // Padding: allows nodes slightly above or below the floor plane to show
      const pad = 0.1; 
      zMin -= pad;
      // zMax += pad;
    }
  }

  // 2. Mesh Rendering (Rooms)
  for (const [lvl, s] of MODEL.byLevel3d.entries()) {
    if (!s || !s.i.length) continue;
    traces.push({
      type: "mesh3d",
      name: lvl,
      x: s.x, y: s.y, z: s.z,
      i: s.i, j: s.j, k: s.k,
      opacity: 0.5,
      hoverinfo: "name",
      visible: (CURRENT_LEVEL === "__all__" || CURRENT_LEVEL === lvl)
    });
  }

  // 3. Dual Graph Rendering (Filtered)
  if (SHOW_DUAL && MODEL.dualNodes && MODEL.dualEdges) {
    const nx = [], ny = [], nz = [];
    const ex = [], ey = [], ez = [];

    // Filter Nodes by Z-range
    MODEL.dualNodes.forEach(n => {
      const p = n.geometry.coordinates;
      const z = p[2] || 0;
      if (CURRENT_LEVEL === "__all__" || (z >= zMin && z < zMax)) {
        nx.push(p[0]); ny.push(p[1]); nz.push(z);
      }
    });

    // Filter Edges by Z-range
    MODEL.dualEdges.forEach(edge => {
    const coords = edge.geometry.coordinates; // This is [[x,y,z], [x,y,z], [x,y,z]...]
    if (!Array.isArray(coords) || coords.length < 2) return;

    // 1. Check if ANY point in this LineString is within the Z-range
  const isInRange = CURRENT_LEVEL === "__all__" || coords.some(p => {
    const z = p[2] || 0;
    return z >= zMin && z < zMax;
  });

  // 2. If it's in range, render the whole thing
  if (isInRange) {
    for (const p of coords) {
      ex.push(p[0]);
      ey.push(p[1]);
      ez.push(p[2] || 0);
    }
    // 3. Lift the pen after the full line is drawn
    ex.push(null);
    ey.push(null);
    ez.push(null);
  }
});

    // Push Nodes Trace
    if (nx.length) {
      traces.push({
        type: "scatter3d", mode: "markers", name: "Nodes",
        x: nx, y: ny, z: nz,
        marker: { size: 4, color: "#f1c40f" }
      });
    }

    // Push Edges Trace
    if (ex.length) {
      traces.push({
        type: "scatter3d", mode: "lines", name: "Edges",
        x: ex, y: ey, z: ez,
        line: { color: "#e74c3c", width: 4 }
      });
    }
  }

  const layout = {
    margin: { l: 0, r: 0, t: 30, b: 0 },
    scene: { aspectmode: "data" },
    showlegend: true
  };

  Plotly.newPlot(plot3d, traces, layout);
}

function render2D() {
  if (!MODEL) return;
  const traces = [];

  for (const lvl of MODEL.levels) {
    const s = MODEL.byLevel2d.get(lvl);
    if (!s || !s.pairs.length) continue;

    const xs = s.pairs.map(p => p[0]);
    const ys = s.pairs.map(p => p[1]);

    traces.push({
      type: "scattergl",
      mode: "lines",
      name: lvl,
      x: xs,
      y: ys,
      line: { 
        width: 1, 
        color: "#333333", // Solid dark grey, no alpha transparency
        simplify: false   // Do NOT let Plotly decimate points
      },
      hoverinfo: "skip",
      visible: (CURRENT_LEVEL === "__all__" || CURRENT_LEVEL === lvl)
    });
  }

  const layout = {
    xaxis: { 
      scaleanchor: "y", 
      zeroline: false, 
      gridcolor: "#f0f0f0",
      constrain: "domain" 
    },
    yaxis: { zeroline: false, gridcolor: "#f0f0f0" },
    margin: { l: 40, r: 10, t: 30, b: 40 },
    plot_bgcolor: "#ffffff"
  };

  Plotly.newPlot(plot2d, traces, layout);
}

/* ---------- Events ---------- */

uploadButton.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  try {
    statusDiv.innerText = "Processing...";
    const json = JSON.parse(await file.text());
    
    MODEL = buildBaseModel(json);
    renderAll();

    // Updated status message with notation
    const s = MODEL.stats;
    statusDiv.innerHTML = `
      <strong>Loaded: ${file.name}</strong><br>
      Layers: ${s.thematicLayers} | 
      Cells: ${s.cellSpaces} | 
      Nodes: ${s.nodes} | 
      Edges: ${s.edges}
    `;
    
  } catch (err) {
    console.error(err);
    statusDiv.innerText = "Error parsing file.";
  }
});

/* ---------- Mode Switching (3D vs 2D) ---------- */

const btn3d = document.getElementById("btn3d");
const btn2d = document.getElementById("btn2d");

function setMode(mode) {
  CURRENT_MODE = mode;

  // 1. Update Buttons
  btn3d.classList.toggle("active", mode === "3d");
  btn2d.classList.toggle("active", mode === "2d");

  // 2. Update Plots visibility
  plot3d.classList.toggle("active", mode === "3d");
  plot2d.classList.toggle("active", mode === "2d");

  // 3. Force Plotly to recalculate the size of the newly visible div
  if (mode === "3d") Plotly.Plots.resize(plot3d);
  else Plotly.Plots.resize(plot2d);
}

// Attach listeners to your existing buttons
btn3d.addEventListener("click", () => setMode("3d"));
btn2d.addEventListener("click", () => setMode("2d"));

/* ---------- Level Selection ---------- */

document.getElementById("level").addEventListener("change", (e) => {
  CURRENT_LEVEL = e.target.value;
  
  // Re-render or Restyle based on the new level
  if (MODEL) {
    render3D();
    render2D();
  }
});

/* ---------- Dual View Toggle ---------- */
const toggleDual = document.getElementById("toggleDual");

toggleDual.addEventListener("change", (e) => {
  SHOW_DUAL = e.target.checked; // Update your global state
  renderAll();                  // Re-run the render loop
});

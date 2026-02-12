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

import * as api from './api.js';

// Global State
let MODEL = null;
let CURRENT_LEVEL = "__all__";
let CURRENT_MODE = "3d";
let SHOW_DUAL = false;
let selectedCollectionId = null;
let selectedFeatureId = null;

const plot3d = document.getElementById("plot3d");
const plot2d = document.getElementById("plot2d");
const cursorDiv = document.getElementById("cursor");
const selectionDiv = document.getElementById("sel");
const levelSelect = document.getElementById("level");
const btn3d = document.getElementById("btn3d");
const btn2d = document.getElementById("btn2d");
const toggleDual = document.getElementById("toggleDual");

/* ---------- Build Model ---------- */

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
    if (!byLevel2d.has(lvl)) byLevel2d.set(lvl, { pairs: [], ids: [] }); // Fixed: Ensure ids exist
  };

  for (const cs of cells) {
    const lvl = safeStr(cs.level) || safeStr(cs.storey) || "UNKNOWN";
    addLevel(lvl);

    const geom = cs.cellSpaceGeom || cs.CellSpaceGeom || {};
    const g3 = geom.geometry3D || null;
    const g2 = geom.geometry2D || null;

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

    const store2 = byLevel2d.get(lvl);
    if (g2 && (g2.type === "Polygon" || g2.type === "MultiPolygon")) {
      const rings = polygon2dToRings(g2);
      // Ensure every vertex in the ring gets the ID assigned to it
      for (const ring of rings) {
        pushRingPairs(store2.pairs, ring); 
        ring.forEach(() => {
          store2.ids.push(cs.id); // Push ID for every coordinate
        });
        store2.ids.push(null); // Push null to match the gap in pairs
      }
    } else if (g3 && g3.type === "Polyhedron") {
      const tris = polyhedronToTris(g3);
      const pts = tris.flat();
      const bb = bboxFromPoints(pts);
      if (bb) {
        const [x0, y0] = bb.min; const [x1, y1] = bb.max;
        const ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]];
        pushRingPairs(store2.pairs, ring);
        ring.forEach(() => store2.ids.push(cs.id));
        store2.ids.push(null);
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
    stats: { thematicLayers: thematicLayerCount, cellSpaces: cells.length, nodes: nodes.length, edges: edges.length }
  };
}

/* ---------- Rendering ---------- */

function renderAll() {
  if (!MODEL) return;

  // Sync Level Dropdown
  const sel = document.getElementById("level");
  const currentVal = sel.value; // Save selection if possible
  sel.innerHTML = '<option value="__all__">All</option>';
  MODEL.levels.forEach(lvl => {
    const o = document.createElement("option");
    o.value = lvl; o.textContent = lvl; sel.appendChild(o);
  });
  if (MODEL.levels.includes(currentVal)) sel.value = currentVal;
  
  render3D();
  render2D();
}

function render3D() {
  const traces = [];
  let zMin = -Infinity, zMax = Infinity;

  if (CURRENT_LEVEL !== "__all__") {
    const base = MODEL.byLevel3d.get(CURRENT_LEVEL);
    if (base && base.z.length > 0) {
      const validZ = base.z.filter(v => v !== null && v !== undefined);
      zMin = Math.min(...validZ) - 0.1;
      zMax = Math.max(...validZ);
    }
  }

  for (const [lvl, s] of MODEL.byLevel3d.entries()) {
    if (!s || !s.i.length) continue;
    traces.push({
      type: "mesh3d", name: lvl, x: s.x, y: s.y, z: s.z, i: s.i, j: s.j, k: s.k,
      opacity: 0.5, hoverinfo: "name", visible: (CURRENT_LEVEL === "__all__" || CURRENT_LEVEL === lvl)
    });
  }

  if (SHOW_DUAL && MODEL.dualNodes && MODEL.dualEdges) {
    const nx = [], ny = [], nz = [];
    const ex = [], ey = [], ez = [];

    MODEL.dualNodes.forEach(n => {
      const p = n.geometry.coordinates;
      const z = p[2] || 0;
      if (CURRENT_LEVEL === "__all__" || (z >= zMin && z < zMax)) {
        nx.push(p[0]); ny.push(p[1]); nz.push(z);
      }
    });

    MODEL.dualEdges.forEach(edge => {
      const coords = edge.geometry.coordinates;
      if (!Array.isArray(coords) || coords.length < 2) return;
      const isInRange = CURRENT_LEVEL === "__all__" || coords.some(p => {
        const z = p[2] || 0;
        return z >= zMin && z < zMax;
      });
      if (isInRange) {
        for (const p of coords) {
          ex.push(p[0]); ey.push(p[1]); ez.push(p[2] || 0);
        }
        ex.push(null); ey.push(null); ez.push(null);
      }
    });

    if (nx.length) traces.push({ type: "scatter3d", mode: "markers", name: "Nodes", x: nx, y: ny, z: nz, marker: { size: 4, color: "#f1c40f" } });
    if (ex.length) traces.push({ type: "scatter3d", mode: "lines", name: "Edges", x: ex, y: ey, z: ez, line: { color: "#e74c3c", width: 4 } });
  }

  Plotly.newPlot(plot3d, traces, { margin: { l: 0, r: 0, t: 30, b: 0 }, scene: { aspectmode: "data" } });
}

function render2D() {
  if (!MODEL) return;
  const traces = [];

  for (const lvl of MODEL.levels) {
    const s = MODEL.byLevel2d.get(lvl);
    if (!s || !s.pairs.length) continue;
    traces.push({
      type: "scattergl", mode: "lines", name: lvl, x: s.pairs.map(p => p[0]), y: s.pairs.map(p => p[1]),
      customdata: s.ids, line: { width: 1, color: "#333333", simplify: false },
      hoverinfo: "all", visible: (CURRENT_LEVEL === "__all__" || CURRENT_LEVEL === lvl)
    });
  }
  const layout = {
    xaxis: { scaleanchor: "y", zeroline: false, constrain: "domain" },
    yaxis: { zeroline: false },
    margin: { l: 40, r: 10, t: 30, b: 40 },
    hovermode: 'closest' // Crucial for clicking thin lines accurately
  };

  Plotly.newPlot(plot2d, traces, layout).then(() => {
    attachPlotlyClick();
  });
}

/* ---------- Events ---------- */

// This listener handles clicks ANYWHERE on the 2D plot
plot2d.addEventListener('click', function(e) {
  if (!plot2d._fullLayout || !plot2d._fullLayout.xaxis) return;

  const fullLayout = plot2d._fullLayout;
  // Convert pixel click (offsetX/Y) to data coordinates (x/y)
  const x = fullLayout.xaxis.p2c(e.offsetX);
  const y = fullLayout.yaxis.p2c(e.offsetY);

  // --- ROOM SEARCH LOGIC ---
  let clickedId = "Outside / No Room";
  
  // If you want to find which room was clicked, we can check the MODEL
  if (MODEL) {
    clickedId = findRoomAtCoords(x, y);
  }

  const selectionInfo = {
    "selection": {
      "id": clickedId,
      "level": CURRENT_LEVEL === "__all__" ? "Multiple" : CURRENT_LEVEL,
    },
    "cursor": {
      "x": x,
      "y": y
    }
  };

  selectionDiv.textContent = JSON.stringify(selectionInfo, null, 2);
});

// Helper function to check which room contains the point (Point-in-Polygon)
function findRoomAtCoords(x, y) {
  // We can iterate through the current level's 2D polygons
  // For now, let's look at the IDs we stored in buildBaseModel
  // This is a simplified check; a true 'contains' check requires a geometric library
  return "Detected at " + CURRENT_LEVEL; 
}

plot2d.addEventListener('mousemove', function(e) {
  if (!plot2d._fullLayout || !plot2d._fullLayout.xaxis) return;
  const x = plot2d._fullLayout.xaxis.p2c(e.offsetX);
  const y = plot2d._fullLayout.yaxis.p2c(e.offsetY);
  cursorDiv.textContent = `X: ${x.toFixed(2)}\nY: ${y.toFixed(2)}`;
});


/* ---------- UI Toggles ---------- */

function setMode(mode) {
  CURRENT_MODE = mode;

  // 1. Update Buttons
  btn3d.classList.toggle("active", mode === "3d");
  btn2d.classList.toggle("active", mode === "2d");

  // 2. Switch Visibility
  if (mode === "3d") {
    plot3d.style.display = "block";
    plot2d.style.display = "none";
  } else {
    plot3d.style.display = "none";
    plot2d.style.display = "block";
  }

  // 3. IMPORTANT: Re-render the specific plot now that it's visible
  if (MODEL) {
    if (mode === "3d") render3D();
    else render2D();
  }
}

btn3d.addEventListener("click", () => setMode("3d"));
btn2d.addEventListener("click", () => setMode("2d"));

levelSelect.addEventListener("change", (e) => {
  CURRENT_LEVEL = e.target.value;
  if (MODEL) renderAll();
});

toggleDual.addEventListener("change", (e) => {
  SHOW_DUAL = e.target.checked;
  if (MODEL) renderAll();
});

/* ---------- pygeoAPI Explorer Logic ---------- */

const dbList = document.getElementById("db-list");
const apiLog = document.getElementById("api-log");
const apiBack = document.getElementById("api-back");
const apiStatus = document.getElementById("api-status-right");

// 1. Get Collections Handler
document.getElementById("api-get-collections").addEventListener("click", async () => {
  try {
    apiStatus.textContent = "Fetching catalogs...";
    const data = await api.getIndoorCollections();
    
    renderCollections(data.filtered);
    apiLog.textContent = JSON.stringify(data.raw, null, 2);
  } catch (err) {
    apiLog.textContent = "Error: " + err.message;
  }
});

// 2. Render Collections (UI Creation)
function renderCollections(collections) {
  dbList.innerHTML = "";
  collections.forEach(col => {
    const itemsLink = col.links.find(l => l.rel === "items" && l.type === "application/geo+json");
    const btn = document.createElement("button");
    btn.className = "db-item-btn";
    btn.innerHTML = `<strong>🏢 ${col.title}</strong><small>ID: ${col.id}</small>`;
    
    btn.onclick = async () => {
      // UI feedback
      document.querySelectorAll('.db-item-btn').forEach(b => b.style.border = "1px solid #ccc");
      btn.style.border = "2px solid #007bff"; 
      
      selectedCollectionId = col.id;
      document.getElementById("collection-post-target-name").innerText = col.title;

      // Call API
      try {
        apiStatus.textContent = `Listing items in ${col.id}...`;
        const featureCollection = await api.getCollectionItems(itemsLink.href);
        renderFeatures(featureCollection.features || [], col.id);
        apiLog.textContent = JSON.stringify(featureCollection, null, 2);
      } catch (err) {
        apiLog.textContent = "Error: " + err.message;
      }
    };
    dbList.appendChild(btn);
  });
}

// 3. POST Button Handler
document.getElementById("indoorFeature-upload-button").addEventListener("click", async () => {
  const fileInput = document.getElementById("file-input");
  const statusDiv = document.getElementById("indoorFeature-upload-status");

  if (!selectedCollectionId || fileInput.files.length === 0) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Missing selection or file.</span>";
    return;
  }

  try {
    const fileText = await fileInput.files[0].text();
    const jsonData = JSON.parse(fileText);
    statusDiv.innerText = "📤 Uploading...";

    const result = await api.postIndoorFeature(selectedCollectionId, jsonData);
    
    statusDiv.innerHTML = "<span style='color:green;'>✅ Success!</span>";
    apiLog.textContent = JSON.stringify(result, null, 2);
  } catch (err) {
    statusDiv.innerHTML = `<span style='color:red;'>❌ ${err.message}</span>`;
  }
});

// 4. Render Features & Fetch Single
function renderFeatures(features, colId) {
  dbList.innerHTML = "";
  features.forEach(f => {
    const btn = document.createElement("button");
    btn.className = "db-item-btn";
    btn.innerHTML = `<strong>📍 ${f.id || "Unnamed"}</strong>`;
    btn.onclick = async () => {

      // SET THE DELETE TARGET
      selectedFeatureId = f.id;
      document.getElementById("indoorFeature-delete-target-name").innerText = f.id;

      try {
        apiStatus.textContent = `Fetching ${f.id}...`;
        const data = await api.getSingleFeature(colId, f.id);
        apiLog.textContent = JSON.stringify(data, null, 2);
        
        // Your Geometry logic (keep in viewer.js or geometry.js)
        if (data.IndoorFeatures) {
          MODEL = buildBaseModel(data.IndoorFeatures); 
          renderAll();
        }
      } catch (err) {
        apiLog.textContent = "Error: " + err.message;
      }
    };
    dbList.appendChild(btn);
  });
}

// DELETE BUTTON HANDLER
document.getElementById("indoorFeature-delete-button").addEventListener("click", async () => {
  const statusDiv = document.getElementById("indoorFeature-delete-status");

  if (!selectedCollectionId || !selectedFeatureId) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Select a collection AND a feature first.</span>";
    return;
  }

  const confirmDelete = confirm(`Are you sure you want to permanently delete feature: ${selectedFeatureId}? This will remove all associated layers.`);
  
  if (confirmDelete) {
    try {
      statusDiv.innerText = "🗑️ Deleting...";
      await api.deleteIndoorFeature(selectedCollectionId, selectedFeatureId);
      
      statusDiv.innerHTML = "<span style='color:green;'>✅ Deleted successfully.</span>";
      
      // Reset UI
      document.getElementById("indoorFeature-delete-target-name").innerText = "None";
      selectedFeatureId = null;
      
      // Optional: Refresh the list so the deleted item disappears
      // You can trigger the collection click again or clear the list
    } catch (err) {
      statusDiv.innerHTML = `<span style='color:red;'>❌ ${err.message}</span>`;
    }
  }
});
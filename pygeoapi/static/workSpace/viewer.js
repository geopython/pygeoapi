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
let selectedFeatureData = null; // Store the fetched GeoJSON here
let selectedILCId = null;
let selectedLayerId = null;
let selectedMemberId = null;

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
      document.getElementById("interLayerConnection-collection-name").innerText = col.title;
      document.getElementById("thematicLayer-collection-name").innerText = col.title;
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
      // 1. UI Feedback: Highlight selection
      document.querySelectorAll('.db-item-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // 2. Set IDs for Delete and Post steps
      selectedFeatureId = f.id;
      document.getElementById("indoorFeature-delete-target-name").innerText = f.id;
      document.getElementById("interLayerConnection-indoorFeature-name").innerText = f.id;
      document.getElementById("thematicLayer-indoorFeature-name").innerText = f.id;
      document.getElementById("thematicLayer-post-target-name").innerText = f.id;

      // Inside your renderFeatures function (right sidebar click):
      selectedLayerId = null;
      const layerDeleteName = document.getElementById("thematicLayers-delete-target-name");
      if (layerDeleteName) layerDeleteName.innerText = "None";
      document.getElementById("thematicLayers-db-list").innerHTML = '<div class="tiny">Click "Load" to see layers.</div>';

      try {
        apiStatus.textContent = `Fetching ${f.id} data...`;
        // Fetch the data and store it globally
        selectedFeatureData = await api.getSingleFeature(colId, f.id);
        
        apiLog.textContent = JSON.stringify(selectedFeatureData, null, 2);
        apiStatus.textContent = `Selected: ${f.id}. Click 'Visualize' to view.`;
      } catch (err) {
        apiLog.textContent = "Error fetching feature: " + err.message;
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

// Visualie button handler
document.getElementById("visualize").addEventListener("click", () => {
  const status = document.getElementById("api-status-right");

  if (!selectedFeatureData || !selectedFeatureData.IndoorFeatures) {
    alert("Please select a feature from the list first!");
    return;
  }

  try {
    status.textContent = "Generating 3D Model...";
    
    // 1. Clear existing model if necessary (depends on your geometry.js)
    // 2. Build the model from the stored data
    MODEL = buildBaseModel(selectedFeatureData.IndoorFeatures); 
    
    // 3. Trigger the 3D Render
    renderAll();
    
    status.textContent = `Visualizing: ${selectedFeatureId}`;
  } catch (err) {
    console.error("Visualization Error:", err);
    status.textContent = "Error during visualization.";
  }
});

document.getElementById("api-get-interLayerConnections").addEventListener("click", async () => {
  const dbListILC = document.getElementById("interLayerConnection-db-list");
  const status = document.getElementById("interLayerConnections-upload-status");

  // 1. Validation: Do we have a feature selected from the sidebar?
  if (!selectedCollectionId || !selectedFeatureId) {
    dbListILC.innerHTML = "<div class='tiny' style='color:red;'>Select a Feature on the right first!</div>";
    return;
  }

  try {
    dbListILC.innerHTML = "<div class='tiny'>Loading...</div>";
    
    // 2. Fetch from API
    const data = await api.getInterLayerConnections(selectedCollectionId, selectedFeatureId);
    const connections = data.layerConnections || [];

    // 3. Render the ILC list
    renderILCList(connections);
    
    apiLog.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    dbListILC.innerHTML = `<div class='tiny' style='color:red;'>Error: ${err.message}</div>`;
  }
});

/** Render the list of InterLayerConnections */
function renderILCList(connections) {
  const dbListILC = document.getElementById("interLayerConnection-db-list");
  dbListILC.innerHTML = "";

  if (connections.length === 0) {
    dbListILC.innerHTML = '<div class="tiny">No InterLayerConnections found for this feature.</div>';
    return;
  }

  connections.forEach(ilc => {
    const btn = document.createElement("button");
    btn.className = "db-item-btn";
    
    // ILCs link two layers, so let's show that in the label
    const layers = ilc.connectedLayers ? ilc.connectedLayers.join(" ↔ ") : "Unknown Layers";
    
    btn.innerHTML = `
      <strong>🔗 ${ilc.id}</strong><br>
      <small>${layers}</small>
    `;

    btn.onclick = () => {
      // Highlight selection
      document.querySelectorAll('#interLayerConnection-db-list .db-item-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Set target for DELETE
      selectedILCId = ilc.id;
      document.getElementById("interLayerConnections-delete-target-name").innerText = ilc.id;
      
      apiLog.textContent = JSON.stringify(ilc, null, 2);
    };

    dbListILC.appendChild(btn);
  });
}

document.getElementById("interLayerConnections-upload-button").addEventListener("click", async () => {
  const fileInput = document.getElementById("interLayerConnections-file-input");
  const statusDiv = document.getElementById("interLayerConnections-upload-status");

  // 1. Validation
  if (!selectedCollectionId || !selectedFeatureId) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Error: Select a Feature on the right sidebar first.</span>";
    return;
  }
  if (fileInput.files.length === 0) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Error: Please select a JSON file.</span>";
    return;
  }

  try {
    const file = fileInput.files[0];
    const text = await file.text();
    const jsonData = JSON.parse(text);

    statusDiv.innerText = "📤 Uploading InterLayerConnection...";

    // 2. Call API
    const result = await api.postInterLayerConnection(selectedCollectionId, selectedFeatureId, jsonData);

    // 3. Success UI
    statusDiv.innerHTML = "<span style='color:green;'>✅ ILC uploaded successfully!</span>";
    apiLog.textContent = JSON.stringify(result, null, 2);
    
    // Optional: Auto-refresh the ILC list to show the new connection
    document.getElementById("api-get-interLayerConnections").click();

  } catch (err) {
    statusDiv.innerHTML = `<span style='color:red;'>❌ ${err.message}</span>`;
    console.error(err);
  }
});

document.getElementById("interLayerConnections-delete-button").addEventListener("click", async () => {
  const statusDiv = document.getElementById("interLayerConnections-delete-status");

  // 1. Validation: Ensure all levels of the hierarchy are selected
  if (!selectedCollectionId || !selectedFeatureId || !selectedILCId) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Error: Select a Collection, Feature, and Connection first.</span>";
    return;
  }

  // 2. Confirmation
  const confirmMsg = `Are you sure you want to delete InterLayerConnection: ${selectedILCId}?`;
  if (!confirm(confirmMsg)) return;

  try {
    statusDiv.innerText = "🗑️ Deleting Connection...";

    // 3. Call API
    await api.deleteInterLayerConnection(selectedCollectionId, selectedFeatureId, selectedILCId);

    // 4. Success UI
    statusDiv.innerHTML = "<span style='color:green;'>✅ Connection deleted successfully.</span>";
    document.getElementById("interLayerConnections-delete-target-name").innerText = "None";
    
    // Clear selection
    selectedILCId = null;

    // 5. Refresh the ILC list automatically
    document.getElementById("api-get-interLayerConnections").click();

  } catch (err) {
    statusDiv.innerHTML = `<span style='color:red;'>❌ ${err.message}</span>`;
    console.error(err);
  }
});

document.getElementById("api-get-thematicLayers").addEventListener("click", async () => {
  const dbListLayers = document.getElementById("thematicLayers-db-list");

  if (!selectedCollectionId || !selectedFeatureId) {
    dbListLayers.innerHTML = "<div class='tiny' style='color:red;'>Select a Feature on the right sidebar first!</div>";
    return;
  }

  try {
    dbListLayers.innerHTML = "<div class='tiny'>Loading layers...</div>";
    
    const data = await api.getThematicLayers(selectedCollectionId, selectedFeatureId);
    
    // 1. Log the full response
    apiLog.textContent = JSON.stringify(data, null, 2);

    // 2. Render the layers list
    renderThematicLayerList(data.layers || [], data.levels || []);
    
  } catch (err) {
    dbListLayers.innerHTML = `<div class='tiny' style='color:red;'>Error: ${err.message}</div>`;
  }
});

/** Render the list of Thematic Layers */
function renderThematicLayerList(layers, levels) {
  const dbListLayers = document.getElementById("thematicLayers-db-list");
  dbListLayers.innerHTML = "";

  // Optional: Display available floor levels at the top
  if (levels.length > 0) {
    const levelInfo = document.createElement("div");
    levelInfo.className = "tiny";
    levelInfo.style = "background: #f8f9fa; padding: 5px; margin-bottom: 8px; border-radius: 4px;";
    levelInfo.innerHTML = `<strong>Available Levels:</strong> ${levels.join(", ")}`;
    dbListLayers.appendChild(levelInfo);
  }

  if (layers.length === 0) {
    const emptyMsg = document.createElement("div");
    emptyMsg.className = "tiny";
    emptyMsg.innerText = "No Thematic Layers found.";
    dbListLayers.appendChild(emptyMsg);
    return;
  }

  layers.forEach(layer => {
    const btn = document.createElement("button");
    btn.className = "db-item-btn";
    
    // Display theme and ID
    btn.innerHTML = `
      <strong>🎨 ${layer.theme || 'Unnamed Theme'}</strong><br>
      <small>ID: ${layer.id}</small>
    `;

    btn.onclick = () => {
      // Highlight UI
      document.querySelectorAll('#thematicLayers-db-list .db-item-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      document.getElementById("primalSpace-post-target-name").innerText = layer.id;
      // Set target for DELETE
      selectedLayerId = layer.id;
      document.getElementById("thematicLayers-delete-target-name").innerText = layer.id;
      
      apiLog.textContent = JSON.stringify(layer, null, 2);
    };

    dbListLayers.appendChild(btn);
  });
}

document.getElementById("thematicLayers-upload-button").addEventListener("click", async () => {
  const fileInput = document.getElementById("thematicLayers-file-input");
  const statusDiv = document.getElementById("thematicLayers-upload-status");

  // 1. Validation
  if (!selectedCollectionId || !selectedFeatureId) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Error: Select a Feature on the right sidebar first.</span>";
    return;
  }
  if (fileInput.files.length === 0) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Error: Please select a JSON file.</span>";
    return;
  }

  try {
    const file = fileInput.files[0];
    const text = await file.text();
    const jsonData = JSON.parse(text);

    statusDiv.innerText = "📤 Uploading Thematic Layer...";

    // 2. Call API
    const result = await api.postThematicLayer(selectedCollectionId, selectedFeatureId, jsonData);

    // 3. Success UI
    statusDiv.innerHTML = "<span style='color:green;'>✅ Layer uploaded successfully!</span>";
    apiLog.textContent = JSON.stringify(result, null, 2);
    
    // Auto-refresh the Layer list to show the new connection
    document.getElementById("api-get-thematicLayers").click();

  } catch (err) {
    statusDiv.innerHTML = `<span style='color:red;'>❌ ${err.message}</span>`;
    console.error("POST Error:", err);
  }
});

document.getElementById("thematicLayers-delete-button").addEventListener("click", async () => {
  const statusDiv = document.getElementById("thematicLayers-delete-status");

  // 1. Validation: Ensure we have the full path (Collection -> Feature -> Layer)
  if (!selectedCollectionId || !selectedFeatureId || !selectedLayerId) {
    statusDiv.innerHTML = "<span style='color:red;'>❌ Error: Select a Feature and a Layer first.</span>";
    return;
  }

  // 2. Confirmation
  const confirmMsg = `Are you sure you want to delete Thematic Layer: ${selectedLayerId}? This cannot be undone.`;
  if (!confirm(confirmMsg)) return;

  try {
    statusDiv.innerText = "🗑️ Deleting Layer...";

    // 3. Call API
    await api.deleteThematicLayer(selectedCollectionId, selectedFeatureId, selectedLayerId);

    // 4. Success UI
    statusDiv.innerHTML = "<span style='color:green;'>✅ Layer deleted successfully.</span>";
    document.getElementById("thematicLayers-delete-target-name").innerText = "None";
    
    // Reset local state
    selectedLayerId = null;

    // 5. Refresh the list so the UI reflects the deletion
    document.getElementById("api-get-thematicLayers").click();

  } catch (err) {
    statusDiv.innerHTML = `<span style='color:red;'>❌ ${err.message}</span>`;
    console.error("Delete Error:", err);
  }
});

document.getElementById("api-get-primalSpaceLayer").addEventListener("click", async () => {
  const listDiv = document.getElementById("primalSpaceLayer-db-list");
  
  if (!selectedCollectionId || !selectedFeatureId || !selectedLayerId) {
    listDiv.innerHTML = "<div class='tiny' style='color:red;'>Select a Thematic Layer first!</div>";
    return;
  }

  try {
    listDiv.innerHTML = "<div class='tiny'>Loading Primal Members...</div>";
    const data = await api.getPrimalSpaceLayer(selectedCollectionId, selectedFeatureId, selectedLayerId);
    
    apiLog.textContent = JSON.stringify(data, null, 2);
    renderPrimalMembers(data);
  } catch (err) {
    listDiv.innerHTML = `<div class='tiny' style='color:red;'>Error: ${err.message}</div>`;
  }
});

function renderPrimalMembers(data) {
  const listDiv = document.getElementById("primalSpaceLayer-db-list");
  listDiv.innerHTML = "";

  const cells = data.cellSpaceMember || [];
  const boundaries = data.cellBoundaryMember || [];

  const createBtn = (item, type) => {
    const btn = document.createElement("button");
    btn.className = "db-item-btn";
    const id = item.id || item; // Handle if it's an object or just a string ID
    btn.innerHTML = `<strong>${type === 'cell' ? '📦' : '🟦'} ${id}</strong><br><small>${type}</small>`;
    
    btn.onclick = () => {
      document.querySelectorAll('#primalSpaceLayer-db-list .db-item-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      selectedMemberId = id;
      document.getElementById("primalSpaceLayer-delete-target-name").innerText = id;
      apiLog.textContent = JSON.stringify(item, null, 2);
    };
    return btn;
  };

  cells.forEach(c => listDiv.appendChild(createBtn(c, 'cell')));
  boundaries.forEach(b => listDiv.appendChild(createBtn(b, 'boundary')));
}

// POST
document.getElementById("primalSpaceLayer-upload-button").onclick = async () => {
  const fileInput = document.getElementById("primalSpaceLayer-file-input");
  const status = document.getElementById("primalSpaceLayer-upload-status");
  
  try {
    const data = JSON.parse(await fileInput.files[0].text());
    await api.postPrimalMember(selectedCollectionId, selectedFeatureId, selectedLayerId, data);
    status.innerHTML = "<span style='color:green;'>✅ Member Added!</span>";
  } catch (err) { status.innerText = err.message; }
};

// PATCH
document.getElementById("primalSpaceLayer-patch-button").onclick = async () => {
  if (!selectedMemberId) return alert("Select a member first!");
  const fileInput = document.getElementById("primalSpaceLayer-file-input");
  
  try {
    const data = JSON.parse(await fileInput.files[0].text());
    await api.managePrimalMember(selectedCollectionId, selectedFeatureId, selectedLayerId, selectedMemberId, 'PATCH', data);
    alert("Member updated!");
  } catch (err) { alert(err.message); }
};

// DELETE
document.getElementById("primalSpaceLayer-delete-button").onclick = async () => {
  if (!selectedMemberId || !confirm(`Delete ${selectedMemberId}?`)) return;
  
  try {
    await api.managePrimalMember(selectedCollectionId, selectedFeatureId, selectedLayerId, selectedMemberId, 'DELETE');
    document.getElementById("api-get-primalSpaceLayer").click();
    document.getElementById("primalSpaceLayer-delete-target-name").innerText = "None";
    selectedMemberId = null;
  } catch (err) { alert(err.message); }
};
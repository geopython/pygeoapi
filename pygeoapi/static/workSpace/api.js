// api.js
const API_BASE = "http://localhost:5000";

/** Fetch all collections and filter for indoorfeature */
export async function getIndoorCollections() {
  const response = await fetch(`${API_BASE}/collections?f=json`);
  if (!response.ok) throw new Error("Failed to fetch collections");
  const data = await response.json();
  return {
    raw: data,
    filtered: (data.collections || []).filter(c => c.itemType === "indoorfeature")
  };
}

/** Fetch items within a specific collection */
export async function getCollectionItems(url) {
  const fetchUrl = url.includes('?') ? `${url}&f=json` : `${url}?f=json`;
  const response = await fetch(fetchUrl);
  if (!response.ok) throw new Error("Failed to list items");
  return await response.json();
}

/** Fetch a single feature by ID with a BBOX */
export async function getSingleFeature(colId, featureId) {
  const hugeBbox = "-1800,-900,1800,900"; 
  const url = `${API_BASE}/collections/${colId}/items/${featureId}?f=json&bbox=${hugeBbox}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Fetch error: ${response.status}`);
  return await response.json();
}

/** POST a new indoor feature */
export async function postIndoorFeature(colId, jsonData) {
  const url = `${API_BASE}/collections/${colId}/items`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jsonData)
  });
  if (!response.ok) {
    const msg = await response.text();
    throw new Error(msg || `Post failed with status ${response.status}`);
  }
  return await response.json();
}

/** DELETE an indoor feature */
export async function deleteIndoorFeature(colId, featureId) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}`;
  const response = await fetch(url, {
    method: 'DELETE'
  });

  if (!response.ok) {
    const msg = await response.text();
    throw new Error(msg || `Delete failed with status ${response.status}`);
  }
  // 204 No Content has no body, so we just return true
  return true; 
}

/** Fetch InterLayerConnections for a specific feature */
export async function getInterLayerConnections(colId, featureId) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}/interlayerconnections?f=json`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load connections: ${response.status}`);
  return await response.json(); // This returns the object containing layerConnections array
}

/** POST a new InterLayerConnection to a specific feature */
export async function postInterLayerConnection(colId, featureId, jsonData) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}/interlayerconnections`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jsonData)
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`ILC Upload Failed (${response.status}): ${errorText}`);
  }
  return await response.json();
}

/** DELETE a specific InterLayerConnection */
export async function deleteInterLayerConnection(colId, featureId, cnId) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}/interlayerconnections/${cnId}`;
  const response = await fetch(url, {
    method: 'DELETE'
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Delete Failed (${response.status}): ${errorText}`);
  }
  return true;
}

/** Fetch ThematicLayers for a specific feature */
export async function getThematicLayers(colId, featureId) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}/layers?f=json`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load layers: ${response.status}`);
  return await response.json(); // Returns { levels: [], layers: [] }
}

/** POST a new ThematicLayer to a specific feature */
export async function postThematicLayer(colId, featureId, jsonData) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}/layers`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jsonData)
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Layer Upload Failed (${response.status}): ${errorText}`);
  }
  return await response.json();
}

/** DELETE a specific ThematicLayer */
export async function deleteThematicLayer(colId, featureId, tId) {
  const url = `${API_BASE}/collections/${colId}/items/${featureId}/layers/${tId}`;
  const response = await fetch(url, {
    method: 'DELETE'
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Delete Failed (${response.status}): ${errorText}`);
  }
  return true;
}

/** GET full PrimalSpaceLayer */
export async function getPrimalSpaceLayer(colId, featId, tId) {
  const url = `${API_BASE}/collections/${colId}/items/${featId}/layers/${tId}/primal?f=json`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load PrimalSpace: ${response.status}`);
  return await response.json();
}

/** POST to PrimalSpaceLayer */
export async function postPrimalMember(colId, featId, tId, jsonData) {
  const url = `${API_BASE}/collections/${colId}/items/${featId}/layers/${tId}/primal`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(jsonData)
  });

  // IMPORTANT: This is what triggers the 'catch' in your UI
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Server Error (${response.status}): ${errorText || 'Not Found'}`);
  }

  return await response.json();
}

/** Single Member: PATCH or DELETE */
export async function managePrimalMember(colId, featId, tId, mId, method, jsonData = null) {
  const url = `${API_BASE}/collections/${colId}/items/${featId}/layers/${tId}/primal/${mId}`;
  const options = { method: method };
  if (jsonData) {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(jsonData);
  }
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${method} failed: ${response.status}`);
  return method === 'DELETE' ? true : await response.json();
}
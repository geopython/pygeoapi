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
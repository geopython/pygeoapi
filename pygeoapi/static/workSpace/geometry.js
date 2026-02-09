/* ---------- Basic Helpers ---------- */
export function safeStr(v){
  return (typeof v==="string") ? v : (typeof v==="number") ? String(v) : "";
}

export function deepFind(obj, predicate, maxDepth=6){
  const out=[], seen=new Set(), stack=[{v:obj,d:0}];
  while(stack.length){
    const {v,d}=stack.pop();
    if(!v || typeof v!=="object") continue;
    if(seen.has(v)) continue;
    seen.add(v);
    if(predicate(v)) out.push(v);
    if(d>=maxDepth) continue;
    if(Array.isArray(v)){
      for(let i=v.length-1;i>=0;i--) stack.push({v:v[i],d:d+1});
    } else {
      for(const k of Object.keys(v)) stack.push({v:v[k],d:d+1});
    }
  }
  return out;
}

/* ---------- IndoorGML Specific Iterators ---------- */
export function iterCellSpaces(obj) {
  const out = [];
  if (!obj || typeof obj !== "object") return out;

  // Standard members
  if (Array.isArray(obj.cellSpaceMember)) out.push(...obj.cellSpaceMember);
  if (Array.isArray(obj?.primalSpace?.cellSpaceMember)) out.push(...obj.primalSpace.cellSpaceMember);

  // Deep layers traversal (Found in PNU-style IndoorJSON)
  const layers = obj.layers || obj.indoorFeatures?.layers || [];
  for (const layer of layers) {
    const primal = layer.primalSpace || layer.primalSpaceLayer || layer.primal || {};
    const members = primal.cellSpaceMember || primal.cellSpaces || [];
    if (Array.isArray(members)) out.push(...members);
  }

  const seen = new Set(), dedup = [];
  for (const cs of out) {
    const id = cs?.id ? String(cs.id) : null;
    if (id && seen.has(id)) continue;
    if (id) seen.add(id);
    dedup.push(cs);
  }
  return dedup;
}

export function iterDualNodes(obj) {
  return deepFind(obj, v => v?.featureType === "Node" && v?.geometry?.type === "Point", 9);
}

export function iterDualEdges(obj) {
  return deepFind(obj, v => v?.featureType === "Edge" && v?.geometry?.type === "LineString", 9);
}

/* ---------- Robust Triangulation (Concave-aware) ---------- */

export function polyhedronToTris(geom3d) {
  const tris = [], coords = geom3d?.coordinates;
  if (!Array.isArray(coords)) return tris;

  // Handle different nesting levels of Polyhedron coordinates
  const polys = (Array.isArray(coords[0][0][0])) ? coords : [coords];

  for (const poly of polys) {
    for (const face of poly) {
      // Extract the outer ring of the face
      let ring = Array.isArray(face[0]) && Array.isArray(face[0][0]) ? face[0] : face;
      if (!Array.isArray(ring) || ring.length < 3) continue;

      const pts = ring.map(p => [p[0], p[1], p[2] ?? 0]);
      tris.push(...triangulateRing(pts));
    }
  }
  return tris;
}

function triangulateRing(pts) {
  if (!Array.isArray(pts) || pts.length < 3) return [];

  // 1. Remove closure point if it's a duplicate of the first point
  const first = pts[0], last = pts[pts.length - 1];
  if (first[0] === last[0] && first[1] === last[1] && (first[2] ?? 0) === (last[2] ?? 0)) {
    pts = pts.slice(0, -1);
  }
  if (pts.length < 3) return [];

  // 2. Find the face normal to create a 2D projection plane
  let n = null, p0 = pts[0];
  for (let i = 0; i < pts.length - 2; i++) {
    const A = pts[i], B = pts[i + 1], C = pts[i + 2];
    const ab = [B[0] - A[0], B[1] - A[1], (B[2] ?? 0) - (A[2] ?? 0)];
    const ac = [C[0] - A[0], C[1] - A[1], (C[2] ?? 0) - (A[2] ?? 0)];
    const cross = [
      ab[1] * ac[2] - ab[2] * ac[1],
      ab[2] * ac[0] - ab[0] * ac[2],
      ab[0] * ac[1] - ab[1] * ac[0]
    ];
    const len = Math.hypot(...cross);
    if (len > 1e-9) {
      n = cross.map(v => v / len);
      p0 = A;
      break;
    }
  }

  // Fallback if normal calculation fails (degenerate face)
  if (!n) {
    const tris = [];
    for (let i = 1; i < pts.length - 1; i++) tris.push([pts[0], pts[i], pts[i + 1]]);
    return tris;
  }

  // 3. Build an orthonormal basis (u, v) on the face plane
  const ref = (Math.abs(n[2]) < 0.9) ? [0, 0, 1] : [0, 1, 0];
  let u = [n[1] * ref[2] - n[2] * ref[1], n[2] * ref[0] - n[0] * ref[2], n[0] * ref[1] - n[1] * ref[0]];
  const ulen = Math.hypot(...u);
  u = u.map(v => v / ulen);
  const v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]];

  // 4. Project to 2D for Earcut
  const coords2d = [];
  for (const P of pts) {
    const px = P[0] - p0[0], py = P[1] - p0[1], pz = (P[2] ?? 0) - (p0[2] ?? 0);
    coords2d.push(px * u[0] + py * u[1] + pz * u[2], px * v[0] + py * v[1] + pz * v[2]);
  }

  // 5. Run Earcut and map back to 3D
  const earcut = window.earcut || (typeof earcut !== 'undefined' ? earcut : null);
  if (!earcut) return []; // Should not happen given your HTML

  const idx = earcut(coords2d, null, 2);
  const tris = [];
  for (let t = 0; t < idx.length; t += 3) {
    tris.push([pts[idx[t]], pts[idx[t + 1]], pts[idx[t + 2]]]);
  }
  return tris;
}

/* ---------- 2D Helpers & Bounding Boxes ---------- */

/**
 * Converts IndoorGML 2D geometry into a set of rings (arrays of points).
 */
export function polygon2dToRings(geom2d) {
  const type = geom2d?.type || geom2d?.Geometry2D?.type;
  const coords = geom2d?.coordinates || geom2d?.Geometry2D?.coordinates;
  if (!coords) return [];
  
  if (type === "Polygon") return [coords[0]];
  if (type === "MultiPolygon") return coords.map(p => p[0]);
  return [];
}

/**
 * This is the magic function that prevents the "overlapping" and "connecting" line mess.
 * It forces Plotly to lift the pen between rings.
 */
export function pushRingPairs(pairs, ring) {
  if (!Array.isArray(ring) || ring.length < 2) return;
  
  const pts = ring.slice();
  const a = pts[0], b = pts[pts.length - 1];
  
  // 1. Close the ring if the data hasn't already
  if (!(a[0] === b[0] && a[1] === b[1])) {
    pts.push(a);
  }

  // 2. Push points to the flat array
  for (const p of pts) {
    pairs.push([p[0], p[1]]);
  }

  // 3. THE FIX: Add a null break so Plotly doesn't connect this room to the next
  pairs.push([null, null]);
}

export function bboxFromPoints(points) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    minX = Math.min(minX, p[0]); minY = Math.min(minY, p[1]);
    maxX = Math.max(maxX, p[0]); maxY = Math.max(maxY, p[1]);
  }
  return Number.isFinite(minX) ? { min: [minX, minY], max: [maxX, maxY] } : null;
}
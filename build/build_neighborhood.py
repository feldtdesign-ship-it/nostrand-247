"""
build_neighborhood.py
Rebuilds the 247 Nostrand Ave neighbourhood model from NYC Open Data.

Run inside Blender (Scripting tab). Blender needs internet access.
Produces: massing, roadbed, sidewalk, median, street-name labels, street trees.

Every number comes from the city. Nothing here is estimated except the height
fallback, which is only used when HEIGHT_ROOF is missing, and the script prints
a list when that happens.

Data sources, all NYC Open Data (Socrata):
  building footprints   5zhs-2jue   polygons, height_roof in US feet
  roadbed               i36f-5ih7   planimetric
  sidewalk              52n9-sdep   planimetric, polygons have holes
  median                ees7-4ufv   planimetric
  street centerline     inkn-q76z   carries stname_label
  street trees 2015     uvpi-gqnh   lat/lon columns, not the_geom
Geocoding: https://geosearch.planninglabs.nyc/v2/search

Dataset ids change when the city republishes. If a pull 404s, look the layer up at
https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&q=<layer>
"""

import bpy, bmesh, json, math, os, tempfile
import urllib.request, urllib.parse
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

# ----------------------------------------------------------------- config
SITE_BBL   = "3017840005"          # 247 Nostrand Ave, confirmed via GeoSearch
SITE_LAT   = 40.690396
SITE_LON   = -73.951350
RADIUS_M   = 400.0                 # half-width of the square pull
FT         = 0.3048
H_FALLBACK = 9.0                   # only when height_roof is missing

DATASETS = {
    "footprints": "5zhs-2jue",
    "roadbed":    "i36f-5ih7",
    "sidewalk":   "52n9-sdep",
    "median":     "ees7-4ufv",
    "centerline": "inkn-q76z",
    "trees":      "uvpi-gqnh",
}

PALETTE = {
    "PJ_INK":     "0C0C0C",
    "PJ_CEMENT":  "9B9B95",
    "PJ_CREAM":   "F3EFE4",
    "PJ_YELLOW":  "F6C500",
    "PJ_OLIVE":   "5F6B3C",
    "PJ_ORANGE":  "F0611F",
}

COLLECTION = "BROOKLYN"
TMP = tempfile.gettempdir()

# ----------------------------------------------------------------- helpers
COSL = math.cos(math.radians(SITE_LAT))

def proj(lon, lat):
    """Local flat projection in metres, centred on the site."""
    return ((lon - SITE_LON) * 111320.0 * COSL,
            (lat - SITE_LAT) * 110540.0)

def bbox():
    dlat = RADIUS_M / 110540.0
    dlon = RADIUS_M / (111320.0 * COSL)
    return (SITE_LAT + dlat, SITE_LON - dlon, SITE_LAT - dlat, SITE_LON + dlon)

def hex_to_linear(h):
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i+2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)

def make_materials():
    for name, hexc in PALETTE.items():
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Base Color"].default_value = hex_to_linear(hexc)
            b.inputs["Roughness"].default_value = 0.95
        m.diffuse_color = hex_to_linear(hexc)   # viewport solid mode reads this

def socrata(ds, geom_col="the_geom", where=None, fmt="geojson", select=None):
    box = bbox()
    if where is None:
        where = "within_box({},{:.6f},{:.6f},{:.6f},{:.6f})".format(geom_col, *box)
    feats, offset = [], 0
    while True:
        q = {"$where": where, "$limit": 5000, "$offset": offset}
        if select:
            q["$select"] = select
        url = "https://data.cityofnewyork.us/resource/{}.{}?{}".format(
            ds, fmt, urllib.parse.urlencode(q))
        req = urllib.request.Request(url, headers={"User-Agent": "nostrand-build/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        chunk = d.get("features", d) if isinstance(d, dict) else d
        feats.extend(chunk)
        if len(chunk) < 5000:
            break
        offset += 5000
    return feats

def rings(geom):
    """Outer ring only, for extruded solids."""
    t = geom.get("type"); c = geom.get("coordinates", [])
    if t == "Polygon":     return [c[0]] if c else []
    if t == "MultiPolygon": return [p[0] for p in c if p]
    return []

def contours(geom):
    """All rings per polygon: [outer, hole, hole...]. Needed for flat layers."""
    t = geom.get("type"); c = geom.get("coordinates", [])
    src = [c] if t == "Polygon" else (c if t == "MultiPolygon" else [])
    for poly in src:
        out = []
        for ring in poly:
            pts = [proj(a, b) for a, b in ring]
            cl = []
            for p in pts:
                if not cl or abs(p[0]-cl[-1][0]) > 1e-7 or abs(p[1]-cl[-1][1]) > 1e-7:
                    cl.append(p)
            if len(cl) > 2 and abs(cl[0][0]-cl[-1][0]) < 1e-7 and abs(cl[0][1]-cl[-1][1]) < 1e-7:
                cl = cl[:-1]
            if len(cl) >= 3:
                out.append(cl)
        if out:
            yield out

def get_collection():
    old = bpy.data.collections.get(COLLECTION)
    if old:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(COLLECTION)
    bpy.context.scene.collection.children.link(col)
    return col

# ----------------------------------------------------------------- massing
def extrude_ring(bm, xy, z0, z1):
    cl = []
    for p in xy:
        if not cl or abs(p[0]-cl[-1][0]) > 1e-6 or abs(p[1]-cl[-1][1]) > 1e-6:
            cl.append(p)
    if len(cl) > 2 and abs(cl[0][0]-cl[-1][0]) < 1e-6 and abs(cl[0][1]-cl[-1][1]) < 1e-6:
        cl = cl[:-1]
    if len(cl) < 3:
        return False
    vs = [bm.verts.new((p[0], p[1], z0)) for p in cl]
    try:
        face = bm.faces.new(vs)
    except ValueError:
        return False
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    bmesh.ops.translate(bm, vec=(0, 0, z1 - z0),
        verts=[v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)])
    return True

def build_massing(col):
    feats = socrata(DATASETS["footprints"])
    json.dump({"type": "FeatureCollection", "features": feats},
              open(os.path.join(TMP, "nostrand_footprints.geojson"), "w"))

    base = None
    for f in feats:
        if f["properties"].get("base_bbl") == SITE_BBL:
            base = float(f["properties"].get("ground_elevation") or 0)
    if base is None:
        print("WARNING: site BBL", SITE_BBL, "not found in footprints. Grade set to 0.")
        base = 0.0

    bm, sbm = bmesh.new(), bmesh.new()
    n_ctx = n_site = 0
    guessed = []

    for f in feats:
        p = f["properties"]
        try:
            h_ft = float(p.get("height_roof") or 0)
        except ValueError:
            h_ft = 0.0
        h = h_ft * FT
        if h <= 0:
            h = H_FALLBACK
            guessed.append(p.get("bin"))
        ge = (float(p.get("ground_elevation") or base) - base) * FT
        target = sbm if p.get("base_bbl") == SITE_BBL else bm
        for ring in rings(f["geometry"]):
            if extrude_ring(target, [proj(a, b) for a, b in ring], ge, ge + h):
                if target is sbm: n_site += 1
                else:             n_ctx += 1

    for b, name, mat in ((bm, "BROOKLYN_MASSING", "PJ_INK"),
                         (sbm, "SITE_247_NOSTRAND", "PJ_YELLOW")):
        bmesh.ops.recalc_face_normals(b, faces=b.faces)
        me = bpy.data.meshes.new(name)
        b.to_mesh(me); b.free()
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        ob.data.materials.append(bpy.data.materials[mat])

    print("massing: {} context, {} site".format(n_ctx, n_site))
    if guessed:
        print("  {} buildings had no height_roof, set to {} m: {}".format(
            len(guessed), H_FALLBACK, guessed[:20]))

# ----------------------------------------------------------------- flat layers
def build_flat(col, key, name, z, mat):
    feats = socrata(DATASETS[key])
    verts, faces, holes = [], [], 0
    for f in feats:
        for cont in contours(f["geometry"]):
            holes += len(cont) - 1
            vecs = [[Vector((x, y, 0.0)) for (x, y) in ring] for ring in cont]
            flat = [v for ring in vecs for v in ring]
            base = len(verts)
            try:
                idx = tessellate_polygon(vecs)   # handles holes, ngons stay clean
            except Exception:
                continue
            verts.extend([(v.x, v.y, z) for v in flat])
            faces.extend([(base+t[0], base+t[1], base+t[2]) for t in idx])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.data.materials.append(bpy.data.materials[mat])
    print("{}: {} tris, {} holes cut".format(name, len(faces), holes))

# ----------------------------------------------------------------- labels
def at_fraction(pts, frac):
    segs = [math.dist(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    total = sum(segs); want = total * frac; run = 0.0
    for i, s in enumerate(segs):
        if run + s >= want:
            t = (want - run) / s if s else 0.0
            a, b = pts[i], pts[i+1]
            return ((a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t),
                    math.atan2(b[1]-a[1], b[0]-a[0]))
        run += s
    return pts[-1], math.atan2(pts[-1][1]-pts[0][1], pts[-1][0]-pts[0][0])

def build_labels(col, size=12.0, min_gap=34.0):
    feats = socrata(DATASETS["centerline"])
    json.dump({"type": "FeatureCollection", "features": feats},
              open(os.path.join(TMP, "nostrand_centerline.geojson"), "w"))

    longest = {}
    for f in feats:
        n = (f["properties"].get("stname_label") or "").strip()
        if not n:
            continue
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for line in parts:
            pts = [proj(a, b) for a, b in line]
            L = sum(math.dist(pts[i], pts[i+1]) for i in range(len(pts)-1))
            if n not in longest or L > longest[n][0]:
                longest[n] = (L, pts)

    placed = []
    for name, (L, pts) in sorted(longest.items(), key=lambda kv: -kv[1][0]):
        if L < 40:
            continue
        spot = None
        for frac in (0.5, 0.3, 0.7, 0.18, 0.82):
            p, ang = at_fraction(pts, frac)
            if all(math.dist(p, q) > min_gap for q in placed):
                spot = (p, ang); break
        if spot is None:
            spot = at_fraction(pts, 0.5)
        p, ang = spot
        if ang >  math.pi/2: ang -= math.pi     # keep type upright
        if ang < -math.pi/2: ang += math.pi
        cu = bpy.data.curves.new("ST_" + name, type='FONT')
        cu.body = name
        cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
        cu.size = size; cu.extrude = 0.04; cu.space_character = 1.15
        ob = bpy.data.objects.new("ST_" + name, cu)
        col.objects.link(ob)
        ob.location = (p[0], p[1], 0.6)
        ob.rotation_euler = (0, 0, ang)
        ob.data.materials.append(bpy.data.materials["PJ_INK"])
        placed.append(p)
    print("labels: {} streets".format(len(placed)))

# ----------------------------------------------------------------- trees
def build_trees(col):
    box = bbox()
    where = ("latitude between {:.6f} and {:.6f} AND "
             "longitude between {:.6f} and {:.6f}").format(box[2], box[0], box[1], box[3])
    rows = socrata(DATASETS["trees"], where=where, fmt="json",
                   select="latitude,longitude,spc_common,tree_dbh,status")
    rows = [r for r in rows if r.get("status") == "Alive"]

    bm = bmesh.new(); n = 0
    for t in rows:
        try:
            x, y = proj(float(t["longitude"]), float(t["latitude"]))
            dbh = float(t.get("tree_dbh") or 6)
        except (TypeError, ValueError, KeyError):
            continue
        r = max(1.4, min(4.2, 1.2 + dbh * 0.12))
        h = max(4.0, min(11.0, 3.5 + dbh * 0.35))
        tb = bmesh.new()
        bmesh.ops.create_icosphere(tb, subdivisions=1, radius=1.0)
        bmesh.ops.scale(tb, vec=(r, r, r * 0.8), verts=tb.verts)
        bmesh.ops.translate(tb, vec=(x, y, h), verts=tb.verts)
        me = bpy.data.meshes.new("t"); tb.to_mesh(me); tb.free()
        bm.from_mesh(me); bpy.data.meshes.remove(me)
        n += 1
    me = bpy.data.meshes.new("TREES"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("TREES", me)
    col.objects.link(ob)
    ob.data.materials.append(bpy.data.materials["PJ_OLIVE"])
    print("trees: {} live".format(n))

# ----------------------------------------------------------------- ground + export
def build_ground(col):
    bpy.ops.mesh.primitive_plane_add(size=2000, location=(0, 0, -0.3))
    g = bpy.context.active_object
    g.name = "GROUND"
    for c in g.users_collection:
        c.objects.unlink(g)
    col.objects.link(g)
    g.data.materials.append(bpy.data.materials["PJ_CREAM"])

def export_glb(path, draco=True):
    for o in bpy.data.objects:
        o.select_set(False)
    names = ["BROOKLYN_MASSING", "SITE_247_NOSTRAND", "ROADBED",
             "SIDEWALK", "MEDIAN", "GROUND", "TREES"]
    names += [o.name for o in bpy.data.objects if o.name.startswith("ST_")]
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            o.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects["BROOKLYN_MASSING"]
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB', use_selection=True,
        export_draco_mesh_compression_enable=draco,
        export_draco_mesh_compression_level=6,
        export_apply=True, export_cameras=False, export_lights=False,
        export_yup=True)          # glTF is Y-up: Blender (x,y,z) -> (x, z, -y)
    print("exported", path, "{:.0f} KB".format(os.path.getsize(path) / 1024))

# ----------------------------------------------------------------- main
def main():
    make_materials()
    col = get_collection()
    build_massing(col)
    build_flat(col, "roadbed",  "ROADBED",  0.02, "PJ_CEMENT")
    build_flat(col, "sidewalk", "SIDEWALK", 0.14, "PJ_CREAM")
    build_flat(col, "median",   "MEDIAN",   0.18, "PJ_OLIVE")
    build_labels(col)
    build_trees(col)
    build_ground(col)
    out = os.path.join(os.path.expanduser("~/Desktop"), "nostrand_neighborhood.glb")
    export_glb(out, draco=True)

main()

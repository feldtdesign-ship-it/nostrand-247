# 247 Nostrand Ave

Single-page site dossier for a Brooklyn storefront. One HTML page, one 3D model,
camera driven by scroll.

Built for Platform's Edge (PJ O'Rourke II). Draft. Not an offer.

## Run it

The model is a `.glb`, so a double-clicked `file://` page will not load it.
Serve the folder:

```
python3 -m http.server 8000
```

Then open <http://localhost:8000/>.

## Deploy

GitHub Pages works with no build step. Settings > Pages > deploy from branch,
root of `main`. `.nojekyll` is already in place so the asset folders are served.

## Structure

```
index.html                          the whole page, ~17 KB
assets/model/                       nostrand_neighborhood.glb, 498 KB Draco
assets/plates/                      rendered stills, also the no-WebGL poster
assets/shop/                        photographs of the storefront, see below
build/build_neighborhood.py         rebuilds the model from scratch in Blender
```

## Shop photographs

Section Seven expects three files:

```
assets/shop/shop-01.jpg     storefront, exterior
assets/shop/shop-02.jpg     interior
assets/shop/shop-03.jpg     the cart
```

Until they exist each frame shows a label card instead of a broken image. No
code change needed, just drop the files in.

## The model

Nothing in it is drawn by hand or estimated, with one exception noted below.
An 800 m square centred on the site, everything from NYC Open Data:

| Layer | Dataset | Notes |
|---|---|---|
| Buildings | `5zhs-2jue` | 1,432 footprints, extruded to `height_roof` in US feet |
| Roadbed | `i36f-5ih7` | surveyed paved area, real intersection corners |
| Sidewalk | `52n9-sdep` | polygons with holes, tessellated |
| Median | `ees7-4ufv` | |
| Street names | `inkn-q76z` | 17 streets, from `stname_label` |
| Trees | `uvpi-gqnh` | 712 live, 2015 census, canopy scaled by trunk diameter |

The site building is matched by **BBL 3017840005**, confirmed through the city
geocoder at `geosearch.planninglabs.nyc`, not by proximity to a coordinate. It is
BIN 3049765, built 1899, roof height 22.5 ft on record.

Ground elevation is applied per building, so the model sits on real grade.

**The one exception:** if a footprint has no `height_roof`, the script falls back
to 9 m and prints the BIN so you know which ones. On the current pull, zero
buildings needed it.

Dataset ids change when the city republishes a layer. `qb5r-6dgf`, widely cited
for building footprints, now returns 404. If a pull fails, look the layer up:

```
https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&q=sidewalk
```

## Rebuilding the model

Open `build/build_neighborhood.py` in Blender's Scripting tab and run it. Blender
needs internet. Change `RADIUS_M` for a wider or tighter pull. It writes the
`.glb` to the Desktop; copy it into `assets/model/`.

## Camera

glTF is Y-up. A Blender `(x, y, z)` becomes `(x, z, -y)` in three.js. The
waypoint array `WP` in `index.html` is already in three.js space. Origin is the
site. One waypoint per section, interpolated on raw scroll position.

The site is a low building hemmed in by taller neighbours, so any waypoint that
needs to show it has to come in steep or from street level on Nostrand. A
three-quarter axon hides it completely.

## Known gaps

- Subway is not on the model. The G at Bedford-Nostrand is the foot-traffic
  argument and it is currently only made in text. MTA entrance data lives on
  `data.ny.gov`, not the NYC portal.
- Shop photographs not supplied.
- Sales figures on the page are gross register data, not a P&L.
- The 43.9 / 56.1 split in the deal documents does not reconcile with the 50 / 50
  shown in the tee walkthrough. Unresolved.

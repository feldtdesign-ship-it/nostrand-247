# 247 Nostrand Avenue, foot traffic

Public data on the block of Nostrand Avenue between Lafayette Avenue and Kosciuszko Street, Bed-Stuy, Brooklyn. Gathered 9 September 2026.

**Live page:** https://feldtdesign-ship-it.github.io/nostrand-247/traffic/

- `traffic/index.html` – the corridor. One hour-scrubber drives everything: an animated avenue with buses arriving at the data's real rates, a hero number whose type widens with the flow, the stacked day, two 168-hour heatmaps, ridership since 2020, weather against traffic, the city's own counts, and the sidewalk at the door.
- `live-wall.html` – the four nearest NYC DOT cameras. None of them see this street, and the page says so.
- `data/` – the raw pulls: MTA subway hourly ridership for Bedford–Nostrand (complex 289), MTA bus stop-level ridership for the five stops within 130 m, DOT vehicle counts, Open-Meteo weather, curb geometry.
- `frames/` – camera frames from the evening of 9 September 2026.
- `build/` – the script and template that turn the data into the page.

## Where the numbers come from

- MTA subway hourly ridership, data.ny.gov, station complex 289
- MTA bus stop-level hourly ridership, data.ny.gov, stops 308706, 303027, 303447, 303446, 303088
- NYC DOT Automated Traffic Volume Counts, Nostrand Ave, Clifton Pl to Greene Ave, December 2024
- NYC Motor Vehicle Collisions
- SBS Bedford-Stuyvesant Commercial District Needs Assessment, 2021
- NYC Planimetric Database curbs, OpenStreetMap, PLUTO: the sidewalk and the lot
- Open-Meteo daily archive
- Citi Bike GBFS

Nobody counts the people passing this door. The page says so where it matters.

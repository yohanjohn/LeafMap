# Modular Food Leaf World Map Plan

## Goal

Build an interactive Jupyter notebook that visualizes where specific edible leaves are commonly used in cuisine at the state/province level. Users should be able to select one or more leaves from a side control and see individual usage regions plus areas of overlap.

The first version will use a small local database seeded from curated LLM-assisted culinary intuition. The database should be easy to inspect, edit, and replace later with stronger sourced data.

## First Leaf Set

Start with these leaves:

- Curry leaves
- Mint
- Parsley
- Basil
- Coriander/cilantro leaves
- Bay leaves
- Kaffir lime leaves
- Banana leaves
- Pandan
- Shiso
- Fenugreek leaves
- Betel leaves

## Recommended Stack

- `pandas`: load, filter, and join local data
- `folium`: render an interactive Leaflet world map inside Jupyter
- `ipywidgets`: side controls for leaf selection and display options
- `geopandas`: optional, for state/province boundary files if choropleths are added
- `branca`: color scales and legends for Folium

Initial version should use `pandas + folium + ipywidgets`. Add `geopandas` only when polygon boundaries are needed.

## Project Shape

Recommended files:

```text
FoodMap/
  FOOD_LEAF_MAP_PLAN.md
  notebooks/
    leaf_world_map.ipynb
  data/
    leaf_usage_regions.csv
    leaf_metadata.csv
  src/
    leafmap/
      __init__.py
      data.py
      map.py
      widgets.py
```

Keep the notebook thin. Put reusable logic in `src/leafmap/` so the map can evolve beyond one notebook.

## Data Model

Use a small local CSV database first. Each row represents one leaf's usage in one state/province/region.

`data/leaf_usage_regions.csv` columns:

| Column | Type | Purpose |
| --- | --- | --- |
| `leaf_id` | string | Stable machine-readable leaf key, such as `curry_leaves` |
| `leaf_name` | string | Display name, such as `Curry leaves` |
| `country` | string | Country name |
| `admin1` | string | State, province, or first-level administrative region |
| `region_label` | string | Human-friendly culinary label, such as `South India` |
| `latitude` | float | Representative point for the region |
| `longitude` | float | Representative point for the region |
| `usage_score` | float | Estimated culinary prevalence from `0.0` to `1.0` |
| `confidence` | string | `low`, `medium`, or `high` |
| `example_dishes` | string | Semicolon-separated examples |
| `notes` | string | Short explanation |
| `source_type` | string | Initially `llm_seeded_curated` |

`data/leaf_metadata.csv` columns:

| Column | Type | Purpose |
| --- | --- | --- |
| `leaf_id` | string | Stable key |
| `leaf_name` | string | Display name |
| `color` | string | Hex color for map styling |
| `category` | string | Herb, wrapper, aromatic leaf, spice leaf, etc. |
| `description` | string | Short tooltip/help text |

## Seed Data Strategy

The initial database can be seeded with LLM-assisted culinary intuition, but every row should be treated as provisional. The notebook should visibly label the data as estimated, not authoritative.

Seed at state/province level where practical:

- Curry leaves: Kerala, Tamil Nadu, Karnataka, Andhra Pradesh, Telangana, Sri Lankan provinces
- Mint: Punjab, Delhi, Uttar Pradesh, Rajasthan, Kashmir, Pakistan provinces, North African regions, Middle Eastern regions
- Parsley: Levant, Turkey, Greece, Italy, France, North Africa
- Basil: Italy, Thailand, Vietnam, Cambodia, Laos, Mediterranean regions
- Coriander/cilantro: India, Pakistan, Mexico, Thailand, Vietnam, China, Middle East
- Bay leaves: Mediterranean Europe, Turkey, North India, Nepal, Caribbean regions
- Kaffir lime leaves: Thailand, Laos, Cambodia, Malaysia, Indonesia
- Banana leaves: South India, Sri Lanka, Indonesia, Malaysia, Philippines, Central America, Caribbean
- Pandan: Indonesia, Malaysia, Singapore, Thailand, Vietnam, Philippines, Sri Lanka
- Shiso: Japan, Korea, parts of China
- Fenugreek leaves: Punjab, Gujarat, Rajasthan, Uttar Pradesh, Pakistan provinces, Afghanistan
- Betel leaves: India, Bangladesh, Myanmar, Thailand, Vietnam, Indonesia, Sri Lanka

For each region, use approximate centroid coordinates. Exact boundaries are not required for v1.

## Usage Score Rules

Use a simple scoring convention:

- `0.9-1.0`: iconic or very common culinary use
- `0.7-0.89`: common and recognizable use
- `0.5-0.69`: present in cuisine, but not defining
- `0.3-0.49`: occasional or regional niche use
- `<0.3`: avoid in v1 unless useful for contrast

Confidence should reflect how comfortable we are with the row:

- `high`: broadly known culinary association
- `medium`: plausible regional association needing review
- `low`: speculative; include only if useful as a placeholder

## Map Behavior

The first version should use point or bubble overlays rather than polygons.

Interactions:

- Sidebar multi-select lists all leaves.
- Selecting one leaf shows all matching regions as bubbles.
- Selecting multiple leaves shows all selected leaves together.
- Regions where multiple selected leaves overlap should be visually emphasized.
- Bubble size should scale with `usage_score`.
- Bubble color should come from `leaf_metadata.csv`.
- Hover/click popup should show leaf, region, country, score, confidence, dishes, and notes.

Overlap behavior for v1:

- Group rows by nearby representative coordinates or by `country + admin1`.
- If a region contains more than one selected leaf, draw an additional highlighted marker or outline.
- Popup should list all selected leaves present in that region.

## Notebook Flow

Recommended notebook sections:

1. Imports and setup
2. Load local CSV files
3. Validate expected columns
4. Display available leaves and data coverage summary
5. Build widgets
6. Render map for selected leaves
7. Show overlap table below the map
8. Optional: edit/add rows and save back to CSV

## Core Functions

Place reusable code in `src/leafmap/`.

`data.py`:

- `load_usage_data(path)`
- `load_leaf_metadata(path)`
- `validate_usage_data(df)`
- `filter_by_leaves(df, leaf_ids)`
- `find_overlaps(df, leaf_ids)`

`map.py`:

- `build_base_map(center=(20, 0), zoom_start=2)`
- `add_leaf_markers(map_obj, usage_df, metadata_df)`
- `add_overlap_markers(map_obj, overlap_df)`
- `render_leaf_map(usage_df, metadata_df, selected_leaf_ids)`

`widgets.py`:

- `build_leaf_selector(metadata_df)`
- `build_map_app(usage_df, metadata_df)`

## Minimal Implementation Sketch

```python
import pandas as pd
import folium
import ipywidgets as widgets
from IPython.display import display, clear_output

usage = pd.read_csv("../data/leaf_usage_regions.csv")
metadata = pd.read_csv("../data/leaf_metadata.csv")

leaf_options = [(row.leaf_name, row.leaf_id) for row in metadata.itertuples()]
selector = widgets.SelectMultiple(options=leaf_options, description="Leaves")
output = widgets.Output()

def render(selected_leaf_ids):
    with output:
        clear_output(wait=True)
        selected = usage[usage["leaf_id"].isin(selected_leaf_ids)]
        m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB positron")
        for row in selected.itertuples():
            color = metadata.loc[metadata["leaf_id"] == row.leaf_id, "color"].iloc[0]
            folium.CircleMarker(
                location=[row.latitude, row.longitude],
                radius=4 + row.usage_score * 10,
                color=color,
                fill=True,
                fill_opacity=0.65,
                popup=f"{row.leaf_name}<br>{row.admin1}, {row.country}<br>Score: {row.usage_score}",
            ).add_to(m)
        display(m)

widgets.interactive_output(render, {"selected_leaf_ids": selector})
display(widgets.HBox([selector, output]))
```

## Upgrade Path

After the first notebook works:

- Add Natural Earth or GADM admin1 boundaries for polygon choropleths.
- Add a manual review workflow for approving or correcting LLM-seeded rows.
- Add source URLs and citations per row.
- Add recipe-frequency-derived scores from public recipe datasets.
- Add dish-level filtering.
- Add export to standalone HTML.
- Add regional comparison mode, such as “show all leaves used in Kerala.”

## Open Decisions

- Whether the first map should use bubbles only or include admin1 polygons immediately.
- Whether to keep the seed database small and high-confidence or broad and exploratory.
- Whether overlap should mean exact same state/province or geographic proximity.
- Whether scores should represent frequency in home cooking, restaurant menus, recipe corpora, or broad culinary salience.

## Recommended First Milestone

Create the local CSV files with 80-150 curated rows, then build a notebook that supports multi-leaf selection, bubble markers, popups, and an overlap table. This gives a useful prototype without getting blocked by boundary data or formal sourcing.

# Streamlit Workflow Plan

## Goal

Create a Streamlit-ready workflow for the Food Leaf Map project without losing the notebook-driven exploration style. The next notebook should act as a bridge: it should load the same data and reusable `leafmap` modules, prove the Streamlit app behavior in small pieces, and make it easy to move the final UI into an `app.py` entry point.

## Current Starting Point

The project already has:

- Reusable data loading and validation in `src/leafmap/data.py`
- Folium map rendering in `src/leafmap/map.py`
- Offline vector map support in `src/leafmap/offline_map.py`
- Notebook-specific widget code in `src/leafmap/widgets.py`
- Local CSV data in `data/`
- Local Natural Earth boundary files in `data/boundaries/`

The Streamlit version should reuse the data and map modules instead of rewriting the map logic.

## Target Project Shape

```text
FoodMap/
  STREAMLIT_WORKFLOW_PLAN.md
  app.py
  notebooks/
    leaf_world_map.ipynb
    leaf_world_map_offline_vector.ipynb
    streamlit_workflow.ipynb
  data/
    leaf_usage_regions.csv
    leaf_metadata.csv
    boundaries/
  src/
    leafmap/
      data.py
      map.py
      offline_map.py
      widgets.py
```

## Workflow Phases

### 1. Prepare Dependencies

Add Streamlit-specific packages:

- `streamlit`
- `streamlit-folium`

Keep existing mapping/data packages:

- `pandas`
- `folium`
- `geopandas`
- `shapely`
- `pyogrio`
- `branca`

Keep `requirements.txt` as the Streamlit Cloud dependency file. Put optional Conda setup files under names Streamlit Cloud will not auto-select, such as `environment-local.yml` and `environment-notebooks.yml`, so deployment uses pip instead of getting stuck in Conda's solver.

### 2. Create a Streamlit Workflow Notebook

Create `notebooks/streamlit_workflow.ipynb` as a development bridge. It should:

1. Resolve `PROJECT_ROOT`
2. Add `src/` to `sys.path`
3. Load usage and metadata CSVs
4. Validate data shape
5. Display available leaves
6. Build the same selected-leaf list that Streamlit will use
7. Render the Folium map using `render_leaf_map`
8. Render overlap tables using `find_overlaps`
9. Sketch the final `app.py` sections in markdown

The notebook should not depend on `ipywidgets` for the core Streamlit path. It can use plain Python variables and dataframe previews to model Streamlit state.

### 3. Define the Streamlit App Surface

The first app version should include:

- Page title: `Food Leaf Map`
- Sidebar leaf multiselect
- Optional sidebar map mode selector
- Main Folium map
- Overlap table below the map
- Data coverage summary
- Short data disclaimer noting that the seed dataset is curated and provisional
- Optional `Explore` / `Edit data` mode selector
- Explore data-source selector for `Canonical CSV` versus `Current draft`

For v1, use the marker map from `render_leaf_map`. Add the offline vector map as a second mode after the simple path works.

### 4. Add Region Data Editing Mode

Add an editing workflow that lets a user review and tweak the leaf usage data by country and region. The first version should use map click or table selection as the reliable interaction, with hover used for visual inspection and tooltips. Folium hover is useful for discovering a region, but Streamlit should treat click/selection as the action that loads a record into an editor.

Editing mode should include:

- A country selector
- A region/admin1 selector filtered by country
- A selected-region summary showing all leaf rows currently attached to that region
- A checklist of known leaves from `leaf_metadata.csv`
- Per-leaf editing fields for rows in the selected region
- A clear distinction between original data and edited draft data

For each region and leaf, expose fields from `data/leaf_usage_regions.csv`:

- `leaf_id`, selected through the known-leaf checklist
- `leaf_name`, filled from metadata when possible
- `country`
- `admin1`
- `region_label`
- `latitude`
- `longitude`
- `usage_score`, using a slider from `0.0` to `1.0`
- `confidence`, using a `low` / `medium` / `high` select box
- `example_dishes`
- `notes`
- `source_type`

Useful editing features:

- Add a leaf to the selected region from a checklist
- Remove a leaf from the selected region with a checkbox or button
- Duplicate an existing region row as a starting point
- Bulk apply `country`, `admin1`, `region_label`, `latitude`, and `longitude` to all edited rows for the selected region
- Show validation warnings before saving
- Prevent duplicate `leaf_id + country + admin1` rows
- Highlight low-confidence rows
- Track unsaved edits in `st.session_state`
- Provide a reset button that discards draft edits and reloads the canonical CSV
- Show a diff table comparing original rows to draft rows
- Let the user download the draft CSV
- Let Explore mode preview the current draft without promoting it to the canonical CSV

Temporary save behavior:

- Never overwrite `data/leaf_usage_regions.csv` automatically
- Save draft edits to `data/leaf_usage_regions.draft.csv`
- Optionally save timestamped snapshots such as `data/drafts/leaf_usage_regions_YYYYMMDD_HHMMSS.csv`
- Add `data/*.draft.csv` and `data/drafts/` to `.gitignore` unless the user explicitly wants to commit drafts
- Add a `Promote draft` workflow later that copies a reviewed draft into `data/leaf_usage_regions.csv`

Notebook coverage for this phase:

1. Load canonical usage data
2. Create a copy named `draft_usage`
3. Pick a test country and admin1 region
4. Simulate checkbox-selected leaves for that region
5. Add, update, and remove rows in `draft_usage`
6. Validate the draft with `validate_usage_data`
7. Write the draft to `data/leaf_usage_regions.draft.csv`
8. Display original-vs-draft differences

Recommended helper functions to add later:

- `get_region_rows(usage_df, country, admin1)`
- `upsert_region_leaf_row(usage_df, row_data)`
- `remove_region_leaf_row(usage_df, leaf_id, country, admin1)`
- `validate_no_duplicate_region_leaves(usage_df)`
- `save_usage_draft(usage_df, path)`
- `diff_usage_data(original_df, draft_df)`

### 5. Add `app.py`

Create a root-level `app.py` that:

1. Imports Streamlit and `streamlit_folium`
2. Resolves project paths from `__file__`
3. Loads data with `st.cache_data`
4. Builds leaf options from metadata
5. Uses `st.sidebar.multiselect`
6. Calls `render_leaf_map`
7. Displays the Folium result with `st_folium`
8. Shows overlap and coverage dataframes
9. Provides an `Edit data` mode that reads and writes a draft CSV only

Keep `app.py` thin. If Streamlit-specific logic grows, move helper functions into a future `src/leafmap/streamlit_app.py`.

### 6. Handle Offline Vector Mode

After the marker map works, add a map mode selector:

- `Markers`
- `Offline polygons`

For offline polygons:

1. Load admin boundary shapefiles from `data/boundaries/`
2. Load country boundaries
3. Cache geospatial loading with `st.cache_data`
4. Call `render_offline_vector_map`

Avoid downloading boundary files during normal Streamlit startup if the local files already exist.

### 7. Verify Locally

Run:

```bash
streamlit run app.py
```

Manual checks:

- App starts without import errors
- Sidebar leaf selection updates the map
- Empty selection does not crash
- Overlap table appears only when overlaps exist
- Map is large enough to use comfortably
- Local boundary mode does not trigger unnecessary downloads
- Edit mode can create a draft without changing the canonical CSV
- Draft validation catches duplicate region-leaf rows
- Reset discards session edits

### 8. Commit the Streamlit Work

Suggested commits:

1. `Add Streamlit workflow plan`
2. `Add Streamlit workflow notebook`
3. `Add Streamlit app entry point`
4. `Add draft data editing workflow`
5. `Document Streamlit launch instructions`

Keep the first Streamlit implementation small and easy to review.

## Open Decisions

- Whether to commit both zipped and extracted boundary files long-term
- Whether `src/leafmap/__init__.py` should stop importing notebook-only `widgets.py`
- Whether the Streamlit app should default to marker mode or polygon mode
- Whether the first public GitHub version should include a `README.md`
- Whether draft CSVs should stay ignored or be saved as review artifacts
- Whether data editing should be restricted to local runs only
- Whether map hover should only preview data or also prime the edit form

## Definition of Done

The Streamlit workflow is ready when:

- `notebooks/streamlit_workflow.ipynb` documents and tests the app logic
- `app.py` launches from the project root
- Dependencies are listed for local setup
- The map and overlap table work with the current CSV data
- Edit mode can save a validated draft CSV without overwriting canonical data
- The repository has a clean commit containing the workflow and app files

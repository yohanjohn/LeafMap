from __future__ import annotations

import html
import re
import urllib.request
import zipfile
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from .data import filter_by_leaves, find_overlaps


NATURAL_EARTH_ADMIN1_URL = (
    "https://naturalearth.s3.amazonaws.com/10m_cultural/"
    "ne_10m_admin_1_states_provinces.zip"
)
NATURAL_EARTH_ADMIN1_STEM = "ne_10m_admin_1_states_provinces"
NATURAL_EARTH_COUNTRIES_URL = (
    "https://naturalearth.s3.amazonaws.com/50m_cultural/"
    "ne_50m_admin_0_countries.zip"
)
NATURAL_EARTH_COUNTRIES_STEM = "ne_50m_admin_0_countries"


def ensure_natural_earth_admin1(boundary_dir: str | Path) -> Path:
    boundary_dir = Path(boundary_dir)
    boundary_dir.mkdir(parents=True, exist_ok=True)
    shp_path = boundary_dir / f"{NATURAL_EARTH_ADMIN1_STEM}.shp"
    if shp_path.exists():
        return shp_path

    zip_path = boundary_dir / f"{NATURAL_EARTH_ADMIN1_STEM}.zip"
    urllib.request.urlretrieve(NATURAL_EARTH_ADMIN1_URL, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(boundary_dir)
    return shp_path


def ensure_natural_earth_countries(boundary_dir: str | Path) -> Path:
    boundary_dir = Path(boundary_dir)
    boundary_dir.mkdir(parents=True, exist_ok=True)
    shp_path = boundary_dir / f"{NATURAL_EARTH_COUNTRIES_STEM}.shp"
    if shp_path.exists():
        return shp_path

    zip_path = boundary_dir / f"{NATURAL_EARTH_COUNTRIES_STEM}.zip"
    urllib.request.urlretrieve(NATURAL_EARTH_COUNTRIES_URL, zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(boundary_dir)
    return shp_path


def load_admin1_boundaries(boundary_path: str | Path) -> gpd.GeoDataFrame:
    boundaries = gpd.read_file(boundary_path).to_crs("EPSG:4326")
    country_col = _first_existing_column(boundaries, ["admin", "adm0_name", "geonunit"])
    admin1_col = _first_existing_column(boundaries, ["name", "name_en", "gn_name"])
    boundaries = boundaries[[country_col, admin1_col, "geometry"]].rename(
        columns={country_col: "boundary_country", admin1_col: "boundary_admin1"}
    )
    boundaries["match_country"] = boundaries["boundary_country"].map(_normalize_name)
    boundaries["match_admin1"] = boundaries["boundary_admin1"].map(_normalize_name)
    return boundaries


def load_country_boundaries(boundary_path: str | Path) -> gpd.GeoDataFrame:
    countries = gpd.read_file(boundary_path).to_crs("EPSG:4326")
    country_col = _first_existing_column(countries, ["ADMIN", "admin", "NAME", "name"])
    countries = countries[[country_col, "geometry"]].rename(columns={country_col: "country"})
    return countries


def attach_boundaries(usage_df: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    usage = usage_df.copy()
    usage["match_country"] = usage["country"].map(_normalize_name)
    usage["match_admin1"] = usage["admin1"].map(_normalize_name)
    merged = usage.merge(
        boundaries[["match_country", "match_admin1", "boundary_country", "boundary_admin1", "geometry"]],
        how="left",
        on=["match_country", "match_admin1"],
    )
    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def boundary_match_summary(usage_with_boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    grouped = (
        usage_with_boundaries.assign(matched=usage_with_boundaries.geometry.notna())
        .groupby(["leaf_id", "leaf_name"], as_index=False)
        .agg(rows=("admin1", "count"), matched_rows=("matched", "sum"))
    )
    grouped["match_rate"] = grouped["matched_rows"] / grouped["rows"]
    return grouped.sort_values(["match_rate", "rows"], ascending=[True, False])


def render_offline_vector_map(
    usage_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    selected_leaf_ids: list[str] | tuple[str, ...],
    boundaries: gpd.GeoDataFrame,
    country_boundaries: gpd.GeoDataFrame | None = None,
) -> folium.Map:
    selected_usage = filter_by_leaves(usage_df, selected_leaf_ids)
    map_obj = folium.Map(location=[20, 20], zoom_start=2, tiles=None, control_scale=True)
    if country_boundaries is not None:
        _add_country_base_layer(map_obj, country_boundaries)
    if selected_usage.empty:
        return map_obj

    colors = metadata_df.set_index("leaf_id")["color"].to_dict()
    selected_with_boundaries = attach_boundaries(selected_usage, boundaries)
    matched = selected_with_boundaries[selected_with_boundaries.geometry.notna()].copy()
    unmatched = selected_with_boundaries[selected_with_boundaries.geometry.isna()].copy()

    if not matched.empty:
        regions = _aggregate_matched_regions(matched, colors)
        for row in regions.itertuples(index=False):
            fill_color = "#ff9800" if row.leaf_count > 1 else row.color
            folium.GeoJson(
                data=mapping(row.geometry),
                style_function=_style_function(fill_color, row.leaf_count),
                tooltip=f"{row.admin1}, {row.country}: {row.leaves}",
                popup=folium.Popup(_polygon_popup_html(row), max_width=380),
            ).add_to(map_obj)

    _add_fallback_markers(map_obj, unmatched, colors)
    _add_overlap_markers(map_obj, find_overlaps(selected_usage, selected_leaf_ids))
    _add_offline_legend(map_obj, metadata_df, selected_leaf_ids)
    folium.LayerControl(collapsed=True).add_to(map_obj)
    _fit_to_selected_data(map_obj, selected_usage)
    return map_obj


def _add_country_base_layer(map_obj: folium.Map, country_boundaries: gpd.GeoDataFrame) -> None:
    folium.GeoJson(
        data=country_boundaries.to_json(),
        name="Local country boundaries",
        style_function=lambda feature: {
            "fillColor": "#f4f1e8",
            "color": "#9e9e9e",
            "weight": 0.6,
            "fillOpacity": 0.55,
        },
        tooltip=folium.GeoJsonTooltip(fields=["country"], aliases=["Country"]),
    ).add_to(map_obj)


def _aggregate_matched_regions(matched: gpd.GeoDataFrame, colors: dict[str, str]) -> gpd.GeoDataFrame:
    rows = []
    for (country, admin1), group in matched.groupby(["country", "admin1"], sort=False):
        leaf_ids = sorted(set(group["leaf_id"]))
        leaf_names = sorted(set(group["leaf_name"]))
        first_leaf = leaf_ids[0]
        rows.append(
            {
                "country": country,
                "admin1": admin1,
                "region_label": "; ".join(sorted(set(group["region_label"]))),
                "leaf_count": len(leaf_ids),
                "leaves": "; ".join(leaf_names),
                "color": colors.get(first_leaf, "#2e7d32"),
                "max_usage_score": group["usage_score"].max(),
                "confidence": "; ".join(sorted(set(group["confidence"]))),
                "example_dishes": "; ".join(group["example_dishes"].dropna().astype(str)),
                "notes": "; ".join(group["notes"].dropna().astype(str)),
                "geometry": group.geometry.iloc[0],
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=matched.crs)


def _add_fallback_markers(map_obj: folium.Map, unmatched: gpd.GeoDataFrame, colors: dict[str, str]) -> None:
    for row in unmatched.itertuples(index=False):
        color = colors.get(row.leaf_id, "#2e7d32")
        popup = f"""
        <strong>{html.escape(row.leaf_name)}</strong><br>
        <strong>Fallback marker:</strong> no local boundary match<br>
        <strong>Region:</strong> {html.escape(row.admin1)}, {html.escape(row.country)}<br>
        <strong>Usage score:</strong> {row.usage_score:.2f}<br>
        <strong>Examples:</strong> {html.escape(row.example_dishes)}
        """
        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=4 + row.usage_score * 8,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.68,
            popup=folium.Popup(popup, max_width=340),
            tooltip=f"Fallback: {row.leaf_name} in {row.admin1}, {row.country}",
        ).add_to(map_obj)


def _add_overlap_markers(map_obj: folium.Map, overlap_df: pd.DataFrame) -> None:
    for row in overlap_df.itertuples(index=False):
        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=8 + row.leaf_count * 3,
            color="#111111",
            weight=3,
            fill=False,
            popup=folium.Popup(
                f"<strong>Overlap:</strong> {html.escape(row.admin1)}, {html.escape(row.country)}<br>"
                f"{html.escape(row.leaves)}",
                max_width=340,
            ),
            tooltip=f"Overlap: {row.leaf_count} selected leaves",
        ).add_to(map_obj)


def _style_function(fill_color: str, leaf_count: int):
    return lambda feature: {
        "fillColor": fill_color,
        "color": "#111111" if leaf_count > 1 else fill_color,
        "weight": 3 if leaf_count > 1 else 1.5,
        "fillOpacity": 0.48 if leaf_count > 1 else 0.38,
    }


def _polygon_popup_html(row: object) -> str:
    return f"""
    <strong>{html.escape(row.admin1)}, {html.escape(row.country)}</strong><br>
    <strong>Leaves:</strong> {html.escape(row.leaves)}<br>
    <strong>Selected leaf count:</strong> {row.leaf_count}<br>
    <strong>Max usage score:</strong> {row.max_usage_score:.2f}<br>
    <strong>Confidence:</strong> {html.escape(row.confidence)}<br>
    <strong>Examples:</strong> {html.escape(row.example_dishes)}<br>
    <strong>Notes:</strong> {html.escape(row.notes)}
    """


def _add_offline_legend(
    map_obj: folium.Map,
    metadata_df: pd.DataFrame,
    selected_leaf_ids: list[str] | tuple[str, ...],
) -> None:
    selected_meta = metadata_df[metadata_df["leaf_id"].isin(selected_leaf_ids)]
    items = "".join(
        f"""
        <div style=\"display:flex; align-items:center; gap:6px; margin:2px 0;\">
          <span style=\"background:{html.escape(row.color)}; width:12px; height:12px; border-radius:50%; display:inline-block;\"></span>
          <span>{html.escape(row.leaf_name)}</span>
        </div>
        """
        for row in selected_meta.itertuples(index=False)
    )
    legend = f"""
    <div style=\"
        position: fixed;
        bottom: 28px;
        left: 28px;
        z-index: 9999;
        background: white;
        padding: 10px 12px;
        border: 1px solid #bbb;
        border-radius: 6px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.2);
        font-size: 13px;
    ">
      <strong>Offline vector map</strong>
      {items}
      <div style=\"margin-top:6px;\"><span style=\"background:#ff9800; width:12px; height:12px; display:inline-block;\"></span> polygon overlap</div>
      <div><span style=\"border:2px solid #111; border-radius:50%; width:12px; height:12px; display:inline-block;\"></span> overlap marker</div>
    </div>
    """
    map_obj.get_root().html.add_child(folium.Element(legend))


def _fit_to_selected_data(map_obj: folium.Map, selected_usage: pd.DataFrame) -> None:
    if selected_usage.empty:
        return
    min_lat = selected_usage["latitude"].min()
    max_lat = selected_usage["latitude"].max()
    min_lon = selected_usage["longitude"].min()
    max_lon = selected_usage["longitude"].max()
    if min_lat == max_lat and min_lon == max_lon:
        map_obj.location = [float(min_lat), float(min_lon)]
        map_obj.options["zoom"] = 4
        return
    map_obj.fit_bounds([[float(min_lat), float(min_lon)], [float(max_lat), float(max_lon)]], padding=(30, 30))


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Expected one of these columns: {candidates}")


def _normalize_name(value: object) -> str:
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

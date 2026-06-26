from __future__ import annotations

import html

import folium
import pandas as pd

from .data import filter_by_leaves, find_overlaps


def build_base_map(center: tuple[float, float] = (20, 20), zoom_start: int = 2) -> folium.Map:
    return folium.Map(location=center, zoom_start=zoom_start, tiles="CartoDB positron")


def render_leaf_map(
    usage_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    selected_leaf_ids: list[str] | tuple[str, ...],
) -> folium.Map:
    selected = filter_by_leaves(usage_df, selected_leaf_ids)
    map_obj = build_base_map()

    if selected.empty:
        return map_obj

    colors = metadata_df.set_index("leaf_id")["color"].to_dict()

    for row in selected.itertuples(index=False):
        color = colors.get(row.leaf_id, "#2e7d32")
        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=4 + (row.usage_score * 9),
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.58,
            popup=folium.Popup(_popup_html(row), max_width=340),
            tooltip=f"{row.leaf_name}: {row.admin1}, {row.country}",
        ).add_to(map_obj)

    add_overlap_markers(map_obj, find_overlaps(usage_df, selected_leaf_ids))
    _add_legend(map_obj, metadata_df, selected_leaf_ids)
    return map_obj


def add_overlap_markers(map_obj: folium.Map, overlap_df: pd.DataFrame) -> None:
    for row in overlap_df.itertuples(index=False):
        popup = (
            f"<strong>Overlap: {html.escape(row.admin1)}, {html.escape(row.country)}</strong><br>"
            f"Leaves: {html.escape(row.leaves)}<br>"
            f"Selected leaf count: {row.leaf_count}"
        )
        folium.CircleMarker(
            location=[row.latitude, row.longitude],
            radius=8 + row.leaf_count * 3,
            color="#111111",
            weight=3,
            fill=False,
            popup=folium.Popup(popup, max_width=340),
            tooltip=f"Overlap: {row.leaf_count} selected leaves",
        ).add_to(map_obj)


def _popup_html(row: object) -> str:
    return f"""
    <strong>{html.escape(row.leaf_name)}</strong><br>
    <strong>Region:</strong> {html.escape(row.admin1)}, {html.escape(row.country)}<br>
    <strong>Culinary area:</strong> {html.escape(row.region_label)}<br>
    <strong>Usage score:</strong> {row.usage_score:.2f}<br>
    <strong>Confidence:</strong> {html.escape(row.confidence)}<br>
    <strong>Examples:</strong> {html.escape(row.example_dishes)}<br>
    <strong>Notes:</strong> {html.escape(row.notes)}<br>
    <strong>Source:</strong> {html.escape(row.source_type)}
    """


def _add_legend(
    map_obj: folium.Map,
    metadata_df: pd.DataFrame,
    selected_leaf_ids: list[str] | tuple[str, ...],
) -> None:
    selected_meta = metadata_df[metadata_df["leaf_id"].isin(selected_leaf_ids)]
    if selected_meta.empty:
        return

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
      <strong>Selected leaves</strong>
      {items}
      <div style=\"margin-top:6px;\"><span style=\"border:2px solid #111; border-radius:50%; width:12px; height:12px; display:inline-block;\"></span> overlap</div>
    </div>
    """
    map_obj.get_root().html.add_child(folium.Element(legend))

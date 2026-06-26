from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


PROJECT_ROOT = Path(__file__).resolve().parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leafmap.data import find_overlaps, load_leaf_metadata, load_usage_data
from leafmap.editing import (
    diff_usage_data,
    get_region_rows,
    remove_region_leaf_row,
    save_usage_draft,
    upsert_region_leaf_row,
    validate_usage_draft,
)
from leafmap.map import render_leaf_map


USAGE_PATH = PROJECT_ROOT / "data" / "leaf_usage_regions.csv"
METADATA_PATH = PROJECT_ROOT / "data" / "leaf_metadata.csv"
DRAFT_USAGE_PATH = PROJECT_ROOT / "data" / "leaf_usage_regions.draft.csv"
DEFAULT_LEAF_IDS = ["cilantro", "parsley", "mint"]


st.set_page_config(page_title="Leafmap", layout="wide")


@st.cache_data
def load_canonical_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_usage_data(USAGE_PATH), load_leaf_metadata(METADATA_PATH)


def initialize_draft_usage(usage_df: pd.DataFrame) -> None:
    if "draft_usage" not in st.session_state:
        if DRAFT_USAGE_PATH.exists():
            st.session_state.draft_usage = load_usage_data(DRAFT_USAGE_PATH)
        else:
            st.session_state.draft_usage = usage_df.copy()


def build_leaf_options(metadata_df: pd.DataFrame) -> dict[str, str]:
    sorted_metadata = metadata_df.sort_values("leaf_name")
    return {row.leaf_name: row.leaf_id for row in sorted_metadata.itertuples(index=False)}


def render_explore_mode(
    canonical_usage_df: pd.DataFrame,
    draft_usage_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> None:
    data_source = st.sidebar.radio(
        "Data source",
        ["Canonical CSV", "Current draft"],
        help="Use Current draft to preview edits applied in Edit data mode before promoting them.",
    )
    usage_df = draft_usage_df if data_source == "Current draft" else canonical_usage_df
    if data_source == "Current draft":
        st.info("Explore is previewing the current draft data.")

    leaf_options = build_leaf_options(metadata_df)
    leaf_names_by_id = {leaf_id: leaf_name for leaf_name, leaf_id in leaf_options.items()}
    default_names = [leaf_names_by_id[leaf_id] for leaf_id in DEFAULT_LEAF_IDS if leaf_id in leaf_names_by_id]
    selected_names = st.sidebar.multiselect("Leaves", leaf_options.keys(), default=default_names)
    selected_leaf_ids = [leaf_options[name] for name in selected_names]

    map_obj = render_leaf_map(usage_df, metadata_df, selected_leaf_ids)
    st_folium(map_obj, height=720, use_container_width=True)

    overlaps = find_overlaps(usage_df, selected_leaf_ids)
    if not overlaps.empty:
        st.subheader("Overlapping Regions")
        st.dataframe(
            overlaps[["country", "admin1", "leaf_count", "leaves", "max_usage_score"]],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Data coverage"):
        coverage = (
            usage_df.groupby(["leaf_id", "leaf_name"])
            .agg(rows=("admin1", "count"), countries=("country", "nunique"), avg_score=("usage_score", "mean"))
            .reset_index()
            .sort_values(["rows", "avg_score"], ascending=[False, False])
        )
        st.dataframe(coverage, use_container_width=True, hide_index=True)


def render_edit_mode(original_usage: pd.DataFrame, metadata_df: pd.DataFrame) -> None:
    initialize_draft_usage(original_usage)
    draft_usage = st.session_state.draft_usage

    st.info(
        "Edits are stored in a draft copy first. Saving here writes "
        "`data/leaf_usage_regions.draft.csv` and does not overwrite the canonical CSV."
    )

    country = st.sidebar.selectbox("Country", sorted(draft_usage["country"].unique()))
    country_rows = draft_usage[draft_usage["country"] == country]
    admin1 = st.sidebar.selectbox("Region", sorted(country_rows["admin1"].unique()))

    selected_region = get_region_rows(draft_usage, country, admin1)
    region_defaults = _region_defaults(selected_region, country, admin1)

    st.subheader(f"{admin1}, {country}")
    st.dataframe(selected_region.sort_values("leaf_name"), use_container_width=True, hide_index=True)

    metadata_by_id = metadata_df.set_index("leaf_id")
    leaf_labels = dict(zip(metadata_df["leaf_name"], metadata_df["leaf_id"], strict=False))
    region_leaf_ids = set(selected_region["leaf_id"])

    with st.form("region_editor"):
        left, right = st.columns([1, 1])
        with left:
            region_label = st.text_input("Region label", value=str(region_defaults["region_label"]))
            latitude = st.number_input("Latitude", value=float(region_defaults["latitude"]), format="%.6f")
            longitude = st.number_input("Longitude", value=float(region_defaults["longitude"]), format="%.6f")
        with right:
            source_type = st.text_input("Source type", value=str(region_defaults["source_type"]))
            apply_region_fields = st.checkbox(
                "Apply region fields to all checked leaves",
                value=True,
                help="Uses the country, region, coordinates, region label, and source type above for every checked leaf.",
            )

        selected_leaf_names = st.multiselect(
            "Leaves present in this region",
            options=sorted(leaf_labels),
            default=sorted(metadata_df.loc[metadata_df["leaf_id"].isin(region_leaf_ids), "leaf_name"]),
        )

        edited_rows = []
        selected_leaf_ids = [leaf_labels[name] for name in selected_leaf_names]
        for leaf_id in selected_leaf_ids:
            existing = selected_region[selected_region["leaf_id"] == leaf_id]
            metadata_row = metadata_by_id.loc[leaf_id]
            row_defaults = _leaf_defaults(existing, metadata_row, region_defaults)
            key_prefix = _widget_key(country, admin1, leaf_id)

            with st.expander(str(metadata_row["leaf_name"]), expanded=leaf_id in region_leaf_ids):
                score_col, confidence_col = st.columns([1, 1])
                with score_col:
                    usage_score = st.slider(
                        "Usage score",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(row_defaults["usage_score"]),
                        step=0.01,
                        key=f"{key_prefix}_usage_score",
                    )
                with confidence_col:
                    confidence = st.selectbox(
                        "Confidence",
                        options=["low", "medium", "high"],
                        index=["low", "medium", "high"].index(str(row_defaults["confidence"])),
                        key=f"{key_prefix}_confidence",
                    )
                example_dishes = st.text_area(
                    "Example dishes",
                    value=str(row_defaults["example_dishes"]),
                    key=f"{key_prefix}_example_dishes",
                )
                notes = st.text_area("Notes", value=str(row_defaults["notes"]), key=f"{key_prefix}_notes")

            row_country = country
            row_admin1 = admin1
            row_region_label = region_label if apply_region_fields else row_defaults["region_label"]
            row_latitude = latitude if apply_region_fields else row_defaults["latitude"]
            row_longitude = longitude if apply_region_fields else row_defaults["longitude"]
            row_source_type = source_type if apply_region_fields else row_defaults["source_type"]

            edited_rows.append(
                {
                    "leaf_id": leaf_id,
                    "leaf_name": metadata_row["leaf_name"],
                    "country": row_country,
                    "admin1": row_admin1,
                    "region_label": row_region_label,
                    "latitude": row_latitude,
                    "longitude": row_longitude,
                    "usage_score": usage_score,
                    "confidence": confidence,
                    "example_dishes": example_dishes,
                    "notes": notes,
                    "source_type": row_source_type,
                }
            )

        submitted = st.form_submit_button("Apply edits to draft")

    if submitted:
        updated = draft_usage.copy()
        for leaf_id in region_leaf_ids - set(selected_leaf_ids):
            updated = remove_region_leaf_row(updated, leaf_id, country, admin1)
        for row_data in edited_rows:
            updated = upsert_region_leaf_row(updated, row_data)

        try:
            validate_usage_draft(updated)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.draft_usage = updated
            st.success("Draft updated in memory. Use Save draft CSV when you are ready to write it.")
            st.rerun()

    diff_df = diff_usage_data(original_usage, st.session_state.draft_usage)
    st.subheader("Draft changes")
    if diff_df.empty:
        st.caption("No draft changes yet.")
    else:
        st.dataframe(diff_df, use_container_width=True, hide_index=True)

    action_col, reset_col, download_col = st.columns([1, 1, 1])
    with action_col:
        if st.button("Save draft CSV", type="primary"):
            try:
                saved_path = save_usage_draft(st.session_state.draft_usage, DRAFT_USAGE_PATH)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success(f"Saved draft to {saved_path.relative_to(PROJECT_ROOT)}")
    with reset_col:
        if st.button("Reset draft"):
            st.session_state.draft_usage = original_usage.copy()
            st.rerun()
    with download_col:
        st.download_button(
            "Download draft CSV",
            data=st.session_state.draft_usage.to_csv(index=False),
            file_name="leaf_usage_regions.draft.csv",
            mime="text/csv",
        )


def _region_defaults(region_rows: pd.DataFrame, country: str, admin1: str) -> dict[str, object]:
    if region_rows.empty:
        return {
            "country": country,
            "admin1": admin1,
            "region_label": "",
            "latitude": 0.0,
            "longitude": 0.0,
            "source_type": "user_draft",
        }
    first_row = region_rows.iloc[0]
    return {
        "country": first_row["country"],
        "admin1": first_row["admin1"],
        "region_label": first_row["region_label"],
        "latitude": first_row["latitude"],
        "longitude": first_row["longitude"],
        "source_type": first_row["source_type"],
    }


def _leaf_defaults(
    existing: pd.DataFrame,
    metadata_row: pd.Series,
    region_defaults: dict[str, object],
) -> dict[str, object]:
    if not existing.empty:
        return existing.iloc[0].to_dict()

    return {
        "leaf_id": metadata_row.name,
        "leaf_name": metadata_row["leaf_name"],
        "country": region_defaults["country"],
        "admin1": region_defaults["admin1"],
        "region_label": region_defaults["region_label"],
        "latitude": region_defaults["latitude"],
        "longitude": region_defaults["longitude"],
        "usage_score": 0.5,
        "confidence": "medium",
        "example_dishes": "",
        "notes": "",
        "source_type": region_defaults["source_type"],
    }


def _widget_key(*parts: object) -> str:
    return "_".join(str(part).lower().replace(" ", "_").replace("/", "_") for part in parts)


def main() -> None:
    usage_df, metadata_df = load_canonical_data()
    initialize_draft_usage(usage_df)

    st.title("Leafmap")
    st.caption(
        "Explore where different leaves are used in cooking, compare regional overlaps, "
        "and draft improvements to the underlying data."
    )

    mode = st.sidebar.radio("Mode", ["Explore", "Edit data"])
    if mode == "Explore":
        render_explore_mode(usage_df, st.session_state.draft_usage, metadata_df)
    else:
        render_edit_mode(usage_df, metadata_df)


if __name__ == "__main__":
    main()

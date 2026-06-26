from __future__ import annotations

from pathlib import Path

import pandas as pd


USAGE_COLUMNS = {
    "leaf_id",
    "leaf_name",
    "country",
    "admin1",
    "region_label",
    "latitude",
    "longitude",
    "usage_score",
    "confidence",
    "example_dishes",
    "notes",
    "source_type",
}

METADATA_COLUMNS = {"leaf_id", "leaf_name", "color", "category", "description"}


def load_usage_data(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    validate_usage_data(df)
    return df


def load_leaf_metadata(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = METADATA_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Leaf metadata is missing columns: {sorted(missing)}")
    if df["leaf_id"].duplicated().any():
        duplicates = sorted(df.loc[df["leaf_id"].duplicated(), "leaf_id"].unique())
        raise ValueError(f"Leaf metadata has duplicate leaf_id values: {duplicates}")
    return df


def validate_usage_data(df: pd.DataFrame) -> None:
    missing = USAGE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Usage data is missing columns: {sorted(missing)}")

    if not df["usage_score"].between(0, 1).all():
        raise ValueError("usage_score values must be between 0.0 and 1.0")

    invalid_confidence = set(df["confidence"].dropna()) - {"low", "medium", "high"}
    if invalid_confidence:
        raise ValueError(f"Invalid confidence values: {sorted(invalid_confidence)}")

    if df[["leaf_id", "country", "admin1"]].duplicated().any():
        raise ValueError("Usage data contains duplicate leaf_id/country/admin1 rows")


def filter_by_leaves(df: pd.DataFrame, leaf_ids: list[str] | tuple[str, ...]) -> pd.DataFrame:
    if not leaf_ids:
        return df.iloc[0:0].copy()
    return df[df["leaf_id"].isin(leaf_ids)].copy()


def find_overlaps(df: pd.DataFrame, leaf_ids: list[str] | tuple[str, ...]) -> pd.DataFrame:
    selected = filter_by_leaves(df, leaf_ids)
    if selected.empty:
        return selected

    grouped = (
        selected.groupby(["country", "admin1", "region_label"], as_index=False)
        .agg(
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            leaf_count=("leaf_id", "nunique"),
            leaves=("leaf_name", lambda values: "; ".join(sorted(set(values)))),
            max_usage_score=("usage_score", "max"),
            example_dishes=("example_dishes", lambda values: "; ".join(values.dropna().astype(str))),
        )
    )
    return grouped[grouped["leaf_count"] > 1].sort_values(
        ["leaf_count", "max_usage_score"], ascending=[False, False]
    )

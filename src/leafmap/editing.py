from __future__ import annotations

from pathlib import Path

import pandas as pd

from .data import USAGE_COLUMNS, validate_usage_data


ROW_KEY_COLUMNS = ["leaf_id", "country", "admin1"]


def get_region_rows(usage_df: pd.DataFrame, country: str, admin1: str) -> pd.DataFrame:
    mask = (usage_df["country"] == country) & (usage_df["admin1"] == admin1)
    return usage_df.loc[mask].copy()


def validate_no_duplicate_region_leaves(usage_df: pd.DataFrame) -> None:
    duplicates = usage_df[usage_df.duplicated(ROW_KEY_COLUMNS, keep=False)]
    if duplicates.empty:
        return

    duplicate_keys = (
        duplicates[ROW_KEY_COLUMNS]
        .drop_duplicates()
        .sort_values(ROW_KEY_COLUMNS)
        .to_dict(orient="records")
    )
    raise ValueError(f"Duplicate leaf/region rows found: {duplicate_keys}")


def validate_usage_draft(usage_df: pd.DataFrame) -> None:
    validate_usage_data(usage_df)
    validate_no_duplicate_region_leaves(usage_df)


def upsert_region_leaf_row(usage_df: pd.DataFrame, row_data: dict[str, object]) -> pd.DataFrame:
    missing = USAGE_COLUMNS - set(row_data)
    if missing:
        raise ValueError(f"Row data is missing columns: {sorted(missing)}")

    updated = usage_df.copy()
    mask = (
        (updated["leaf_id"] == row_data["leaf_id"])
        & (updated["country"] == row_data["country"])
        & (updated["admin1"] == row_data["admin1"])
    )
    row = pd.DataFrame([{column: row_data[column] for column in usage_df.columns}])

    if mask.any():
        updated = updated.loc[~mask]

    updated = pd.concat([updated, row], ignore_index=True)
    return _sort_usage_rows(updated)


def remove_region_leaf_row(
    usage_df: pd.DataFrame,
    leaf_id: str,
    country: str,
    admin1: str,
) -> pd.DataFrame:
    mask = (
        (usage_df["leaf_id"] == leaf_id)
        & (usage_df["country"] == country)
        & (usage_df["admin1"] == admin1)
    )
    return _sort_usage_rows(usage_df.loc[~mask].copy())


def save_usage_draft(usage_df: pd.DataFrame, path: str | Path) -> Path:
    validate_usage_draft(usage_df)
    draft_path = Path(path)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    usage_df.to_csv(draft_path, index=False)
    return draft_path


def diff_usage_data(original_df: pd.DataFrame, draft_df: pd.DataFrame) -> pd.DataFrame:
    original = original_df.copy()
    draft = draft_df.copy()
    original["_state"] = "original"
    draft["_state"] = "draft"

    combined = pd.concat([original, draft], ignore_index=True)
    compare_columns = [column for column in original_df.columns if column not in ROW_KEY_COLUMNS]
    changed_mask = combined.duplicated(original_df.columns.tolist(), keep=False)
    changed = combined.loc[~changed_mask].copy()
    if changed.empty:
        return pd.DataFrame(columns=["change_type", *original_df.columns])

    original_keys = set(map(tuple, original_df[ROW_KEY_COLUMNS].to_numpy()))
    draft_keys = set(map(tuple, draft_df[ROW_KEY_COLUMNS].to_numpy()))

    rows = []
    for key in sorted(original_keys | draft_keys):
        original_match = _match_key(original_df, key)
        draft_match = _match_key(draft_df, key)

        if original_match.empty and not draft_match.empty:
            rows.append({"change_type": "added", **draft_match.iloc[0].to_dict()})
        elif draft_match.empty and not original_match.empty:
            rows.append({"change_type": "removed", **original_match.iloc[0].to_dict()})
        elif not original_match.empty and not draft_match.empty:
            original_row = original_match.iloc[0]
            draft_row = draft_match.iloc[0]
            if any(original_row[column] != draft_row[column] for column in compare_columns):
                rows.append({"change_type": "updated", **draft_row.to_dict()})

    return pd.DataFrame(rows, columns=["change_type", *original_df.columns])


def _match_key(df: pd.DataFrame, key: tuple[object, object, object]) -> pd.DataFrame:
    leaf_id, country, admin1 = key
    mask = (df["leaf_id"] == leaf_id) & (df["country"] == country) & (df["admin1"] == admin1)
    return df.loc[mask]


def _sort_usage_rows(usage_df: pd.DataFrame) -> pd.DataFrame:
    return usage_df.sort_values(["country", "admin1", "leaf_name"]).reset_index(drop=True)

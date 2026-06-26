from __future__ import annotations

import pandas as pd

from IPython.display import clear_output, display
import ipywidgets as widgets

from .data import find_overlaps
from .map import render_leaf_map


def build_leaf_selector(metadata_df: pd.DataFrame) -> widgets.SelectMultiple:
    options = [(row.leaf_name, row.leaf_id) for row in metadata_df.sort_values("leaf_name").itertuples()]
    return widgets.SelectMultiple(
        options=options,
        value=tuple(value for _, value in options[:3]),
        description="Leaves",
        rows=min(12, len(options)),
        layout=widgets.Layout(width="260px"),
    )


def build_map_app(usage_df: pd.DataFrame, metadata_df: pd.DataFrame) -> widgets.HBox:
    selector = build_leaf_selector(metadata_df)
    output = widgets.Output(layout=widgets.Layout(width="100%"))

    def update(change: object | None = None) -> None:
        with output:
            clear_output(wait=True)
            selected = list(selector.value)
            display(render_leaf_map(usage_df, metadata_df, selected))
            overlaps = find_overlaps(usage_df, selected)
            if not overlaps.empty:
                display(overlaps[["country", "admin1", "leaf_count", "leaves", "max_usage_score"]])

    selector.observe(update, names="value")
    update()
    return widgets.HBox([selector, output])

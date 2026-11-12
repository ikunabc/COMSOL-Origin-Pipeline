import logging
from copy import deepcopy

import numpy as np
import pandas as pd

from ..exceptions import ConfigError, DataProcessingError
from ..models import Dataset

log = logging.getLogger("pipeline")


def validate_columns(dataset, config):
    df = dataset.data
    g = config["plot"]
    columns = [g["x_column"]] + g["y_columns"]
    for col in columns:
        if col not in df.columns:
            raise ConfigError(
                f"Configuration error: [plot] column {col!r} does not exist. "
                f"Available: {list(df.columns)}"
            )
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise DataProcessingError(f"Plot column {col!r} contains non-numeric values.")
    for axis, cols in [("x", [g["x_column"]]), ("y", g["y_columns"])]:
        if g["axis"][axis]["scale"] == "log10":
            finite = df[cols].to_numpy(dtype=float)
            if np.any(finite[np.isfinite(finite)] <= 0):
                raise DataProcessingError(f"log10 {axis} axis requires strictly positive data.")


def process(dataset, config):
    validate_columns(dataset, config)
    p, g = config["processing"], config["plot"]
    x, ys = g["x_column"], g["y_columns"]
    selected = [x] + ys
    df = dataset.data.copy(deep=True)
    history = []
    try:
        bad = ~np.isfinite(df[selected].to_numpy(dtype=float)).all(axis=1)
        if bad.any():
            if p["drop_nan"]:
                df = df.loc[~bad].copy()
                history.append(f"dropped {int(bad.sum())} rows with NaN/Inf in plotting columns")
            else:
                raise DataProcessingError(
                    "NaN/Inf in plotting columns; enable [processing].drop_nan or fix the source."
                )
        if df.empty:
            raise DataProcessingError("No finite data remain.")
        if p["sort"]:
            df = df.sort_values(x, kind="stable")
            history.append(f"stable sort by {x}")
        method = p["smoothing_method"] if p["enable_smoothing"] else "none"
        if method != "none":
            if p["window_length"] > len(df):
                raise DataProcessingError("window_length exceeds the number of retained data rows.")
            if not df[x].is_monotonic_increasing or df[x].duplicated().any():
                raise DataProcessingError(
                    "Smoothing requires strictly increasing, unique X; enable sort and "
                    "resolve duplicate sweeps."
                )
            if method == "savgol" and len(df) > 2:
                delta = np.diff(df[x].to_numpy(dtype=float))
                if not np.allclose(
                    delta, delta[0], rtol=1e-4, atol=max(abs(delta[0]) * 1e-8, 1e-15)
                ):
                    raise DataProcessingError(
                        "Savitzky-Golay requires uniformly spaced X. Resample before input "
                        "or use another smoothing method."
                    )
            log.info("Applying %s filter...", method)
            for col in ys:
                if method == "savgol":
                    from scipy.signal import savgol_filter

                    df[col] = savgol_filter(
                        df[col].to_numpy(dtype=float), p["window_length"], p["polyorder"]
                    )
                elif method == "moving_average":
                    df[col] = df[col].rolling(p["window_length"], center=True, min_periods=1).mean()
                else:
                    from scipy.ndimage import median_filter

                    df[col] = median_filter(
                        df[col].to_numpy(dtype=float), size=p["window_length"], mode="nearest"
                    )
            history.append(f"{method}: window={p['window_length']}, polyorder={p['polyorder']}")
        method = p["interpolation_method"] if p["enable_interpolation"] else "none"
        if method != "none":
            from scipy.interpolate import PchipInterpolator, interp1d

            values = df[x].to_numpy(dtype=float)
            if len(values) < (4 if method == "cubic" else 2) or np.any(np.diff(values) <= 0):
                raise DataProcessingError(
                    "Interpolation requires sorted unique X and at least 4 points for cubic, "
                    "2 otherwise."
                )
            grid = np.linspace(values[0], values[-1], p["interpolation_points"])
            interpolated = {x: grid}
            for col in ys:
                f = (
                    PchipInterpolator(values, df[col])
                    if method == "pchip"
                    else interp1d(values, df[col], kind=method, bounds_error=True)
                )
                interpolated[col] = f(grid)
            # Nonselected columns cannot be carried to a different grid honestly.
            df = pd.DataFrame(interpolated)
            history.append(
                f"{method} interpolation: {len(grid)} points; nonselected columns omitted"
            )
        if not np.isfinite(df[selected].to_numpy(dtype=float)).all():
            raise DataProcessingError("Processing generated NaN/Inf.")
    except DataProcessingError:
        raise
    except Exception as exc:
        raise DataProcessingError(f"Data processing failed: {exc}") from exc
    metadata = deepcopy(dataset.metadata)
    metadata["processing"] = history
    result = Dataset(
        df.reset_index(drop=True),
        dataset.name,
        dataset.source,
        list(df.columns),
        {col: dataset.units.get(col, "") for col in df.columns},
        metadata,
    )
    validate_columns(result, config)
    return result

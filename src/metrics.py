from __future__ import annotations

from typing import Iterable

import numpy as np


def _to_numpy(values: Iterable[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def wape(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    y_true_arr = _to_numpy(y_true)
    y_pred_arr = _to_numpy(y_pred)
    denominator = float(np.sum(y_true_arr))
    if denominator <= 0:
        raise ValueError("WAPE is undefined when sum(y_true) <= 0.")
    return float(np.sum(np.abs(y_pred_arr - y_true_arr)) / denominator)


def relative_bias(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    y_true_arr = _to_numpy(y_true)
    y_pred_arr = _to_numpy(y_pred)
    denominator = float(np.sum(y_true_arr))
    if denominator <= 0:
        raise ValueError("Relative Bias is undefined when sum(y_true) <= 0.")
    return float(abs(float(np.sum(y_pred_arr)) / denominator - 1.0))


def competition_score(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    return wape(y_true, y_pred) + relative_bias(y_true, y_pred)

"""Time-based and burst anomaly detection for comments."""

from datetime import datetime
from typing import Any

import numpy as np


def compute_temporal_features(
    timestamps: list[datetime],
    time_window_minutes: int = 1,
    zscore_threshold: float = 3.0,
) -> dict[str, Any]:
    """Analyze temporal comment distribution, comments per minute, and burst anomalies.

    Techniques:
    - Binned arrival rate (comments per minute)
    - Z-score spike detection: Z = (x - mean) / std
    - Interquartile Range (IQR) detection: IQR = Q3 - Q1, upper_bound = Q3 + 1.5 * IQR

    Args:
        timestamps: List of datetime objects for comments.
        time_window_minutes: Binning interval for comments-per-minute.
        zscore_threshold: Statistical Z-score cutoff for anomaly flag.

    Returns:
        Dict containing:
        - duration_minutes: Span between first and last comment in minutes
        - average_comments_per_minute: Mean comments per minute over active span
        - max_comments_per_minute: Maximum comments observed in a single window
        - zscore_max: Maximum Z-score observed across intervals
        - z_score: Rounded max Z-score (alias)
        - zscore_burst_detected: 1.0 if zscore_max >= zscore_threshold, else 0.0
        - iqr_burst_detected: 1.0 if any interval exceeds Q3 + 1.5*IQR, else 0.0
        - iqr_anomaly_info: Dict of Q25, Q75, IQR, upper bound, and outlier count
        - temporal_anomaly_score: Continuous anomaly indicator in [0.0, 1.0]
        - temporal_burst_score: Alias for temporal_anomaly_score
    """
    valid_times = sorted([ts for ts in timestamps if isinstance(ts, datetime)])
    n = len(valid_times)

    if n < 3:
        iqr_info = {
            "q25": 0.0,
            "q75": 0.0,
            "iqr": 0.0,
            "upper_bound": 0.0,
            "outlier_count": 0,
            "iqr_burst_detected": False,
        }
        return {
            "duration_minutes": 0.0,
            "average_comments_per_minute": float(n),
            "max_comments_per_minute": float(n),
            "zscore_max": 0.0,
            "z_score": 0.0,
            "zscore_burst_detected": 0.0,
            "iqr_burst_detected": 0.0,
            "iqr_anomaly_info": iqr_info,
            "temporal_anomaly_score": 0.0,
            "temporal_burst_score": 0.0,
        }

    first_time = valid_times[0]
    last_time = valid_times[-1]
    total_seconds = max(1.0, (last_time - first_time).total_seconds())
    duration_minutes = total_seconds / 60.0

    # Bucket comments into 1-minute time windows
    window_sec = time_window_minutes * 60.0
    num_bins = max(1, int(np.ceil(total_seconds / window_sec)))

    # If span is under 1 minute but has multiple comments
    if num_bins == 1:
        cpm = (n / total_seconds) * 60.0
        is_burst = 1.0 if (n >= 10 and duration_minutes < 1.0) else 0.0
        z_val = round(3.5 if is_burst else 0.0, 2)
        anom = round(min(1.0, cpm / 60.0), 4) if is_burst else 0.0
        iqr_info = {
            "q25": float(n),
            "q75": float(n),
            "iqr": 0.0,
            "upper_bound": float(n),
            "outlier_count": 1 if is_burst else 0,
            "iqr_burst_detected": bool(is_burst),
        }
        return {
            "duration_minutes": round(duration_minutes, 2),
            "average_comments_per_minute": round(cpm, 2),
            "max_comments_per_minute": round(float(n), 2),
            "zscore_max": z_val,
            "z_score": z_val,
            "zscore_burst_detected": is_burst,
            "iqr_burst_detected": is_burst,
            "iqr_anomaly_info": iqr_info,
            "temporal_anomaly_score": anom,
            "temporal_burst_score": anom,
        }

    # Bin counts across timeline
    offsets = np.array([(t - first_time).total_seconds() for t in valid_times])
    bin_indices = np.minimum(np.floor(offsets / window_sec).astype(int), num_bins - 1)
    bin_counts = np.bincount(bin_indices, minlength=num_bins).astype(float)

    mean_count = float(np.mean(bin_counts))
    std_count = float(np.std(bin_counts))
    max_count = float(np.max(bin_counts))

    # Z-Score Calculation
    zscore_max = 0.0
    if std_count > 1e-6:
        zscores = (bin_counts - mean_count) / std_count
        zscore_max = float(np.max(zscores))
    zscore_burst = 1.0 if zscore_max >= zscore_threshold else 0.0

    # IQR (Interquartile Range) Anomaly Calculation
    q75, q25 = np.percentile(bin_counts, [75, 25])
    iqr = float(q75 - q25)
    iqr_upper_bound = float(q75 + (1.5 * iqr))
    outlier_count = int(np.sum(bin_counts > iqr_upper_bound)) if iqr > 0 else 0
    iqr_burst = 1.0 if outlier_count > 0 else 0.0

    # Continuous temporal anomaly index (0.0 to 1.0)
    norm_z = max(0.0, min(1.0, (zscore_max - 2.0) / 4.0)) if zscore_max > 2.0 else 0.0
    anomaly_score = round(max(norm_z, 0.6 if iqr_burst else 0.0), 4)

    iqr_info = {
        "q25": round(float(q25), 2),
        "q75": round(float(q75), 2),
        "iqr": round(float(iqr), 2),
        "upper_bound": round(float(iqr_upper_bound), 2),
        "outlier_count": outlier_count,
        "iqr_burst_detected": bool(iqr_burst),
    }

    return {
        "duration_minutes": round(duration_minutes, 2),
        "average_comments_per_minute": round(mean_count / time_window_minutes, 2),
        "max_comments_per_minute": round(max_count / time_window_minutes, 2),
        "zscore_max": round(zscore_max, 2),
        "z_score": round(zscore_max, 2),
        "zscore_burst_detected": zscore_burst,
        "iqr_burst_detected": iqr_burst,
        "iqr_anomaly_info": iqr_info,
        "temporal_anomaly_score": anomaly_score,
        "temporal_burst_score": anomaly_score,
    }


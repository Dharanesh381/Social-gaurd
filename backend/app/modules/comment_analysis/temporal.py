"""Time-based and burst anomaly detection for comments."""

from datetime import datetime

import numpy as np


def compute_temporal_features(
    timestamps: list[datetime],
    time_window_minutes: int = 1,
    zscore_threshold: float = 3.0,
) -> dict[str, float]:
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
        - zscore_burst_detected: 1.0 if zscore_max >= zscore_threshold, else 0.0
        - iqr_burst_detected: 1.0 if any interval exceeds Q3 + 1.5*IQR, else 0.0
        - temporal_anomaly_score: Continuous anomaly indicator in [0.0, 1.0]
    """
    valid_times = sorted([ts for ts in timestamps if ts is not None])
    n = len(valid_times)

    if n < 3:
        return {
            "duration_minutes": 0.0,
            "average_comments_per_minute": float(n),
            "max_comments_per_minute": float(n),
            "zscore_max": 0.0,
            "zscore_burst_detected": 0.0,
            "iqr_burst_detected": 0.0,
            "temporal_anomaly_score": 0.0,
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
        # Single bucket: comments per minute = total comments / duration
        cpm = (n / total_seconds) * 60.0
        # High burst if > 30 comments in under 1 minute
        is_burst = 1.0 if (n >= 10 and duration_minutes < 1.0) else 0.0
        return {
            "duration_minutes": round(duration_minutes, 2),
            "average_comments_per_minute": round(cpm, 2),
            "max_comments_per_minute": round(float(n), 2),
            "zscore_max": round(is_burst * 3.5, 2),
            "zscore_burst_detected": is_burst,
            "iqr_burst_detected": is_burst,
            "temporal_anomaly_score": round(min(1.0, cpm / 60.0), 4) if is_burst else 0.0,
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
    iqr = q75 - q25
    iqr_upper_bound = q75 + (1.5 * iqr)
    iqr_burst = 1.0 if (iqr > 0 and max_count > iqr_upper_bound) else 0.0

    # Continuous temporal anomaly index (0.0 to 1.0)
    # Scaled by zscore magnitude above 2.0 and IQR burst presence
    norm_z = max(0.0, min(1.0, (zscore_max - 2.0) / 4.0)) if zscore_max > 2.0 else 0.0
    anomaly_score = round(max(norm_z, 0.6 if iqr_burst else 0.0), 4)

    return {
        "duration_minutes": round(duration_minutes, 2),
        "average_comments_per_minute": round(mean_count / time_window_minutes, 2),
        "max_comments_per_minute": round(max_count / time_window_minutes, 2),
        "zscore_max": round(zscore_max, 2),
        "zscore_burst_detected": zscore_burst,
        "iqr_burst_detected": iqr_burst,
        "temporal_anomaly_score": anomaly_score,
    }

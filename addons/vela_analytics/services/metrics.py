"""Windows, baselines and alert rules for local metrics (plan §9). Pure functions.

Windows are 5-minute tumbling windows aligned on UTC clock time, like Spark's output.
"""
from datetime import timedelta
from statistics import fmean, pstdev

WINDOW = timedelta(minutes=5)
BASELINE_WINDOWS = 12  # one hour of history
RECOMPUTE_WINDOWS = 3  # late events: each cron run recomputes the last 3 closed windows
STALE_AFTER = timedelta(minutes=15)

# Defaults; overridable in Settings (ir.config_parameter "vela_analytics.<name>")
THRESHOLDS = {
    "checkout_error_factor": 2.0,
    "checkout_error_min_errors": 5,
    "checkout_error_min_starts": 20,
    "demand_sigma": 3.0,
    "demand_min_adds": 10,
    "zero_search_factor": 3.0,
    "zero_search_min": 10,
}


def floor_window(dt):
    return dt.replace(minute=dt.minute - dt.minute % 5, second=0, microsecond=0)


def windows_between(start, end):
    """Closed windows whose start lies in [floor(start), end - WINDOW]."""
    ws = floor_window(start)
    out = []
    while ws + WINDOW <= end:
        out.append(ws)
        ws += WINDOW
    return out


def ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def checkout_error_rule(errors, starts, baseline_ratios, t):
    """Error ratio at least `factor` × its mean over the previous hour, with enough volume.

    Needs at least 3 baseline windows with checkout traffic: no history, no claim.
    """
    if errors < t["checkout_error_min_errors"] or starts < t["checkout_error_min_starts"]:
        return None
    if len(baseline_ratios) < 3:
        return None
    measured, baseline = ratio(errors, starts), fmean(baseline_ratios)
    threshold = t["checkout_error_factor"] * baseline
    if measured < threshold or measured <= baseline:
        return None
    return {
        "measured": measured, "baseline": baseline, "threshold": threshold,
        "severity": "high" if measured >= 2 * threshold else "medium",
        "rule": (f"error ratio ≥ {t['checkout_error_factor']} × mean of previous "
                 f"{BASELINE_WINDOWS} windows, ≥ {t['checkout_error_min_errors']} errors, "
                 f"≥ {t['checkout_error_min_starts']} checkout starts"),
    }


def demand_rule(adds, baseline_counts, t):
    """Add-to-cart count at least mean + sigma × σ of the previous hour (missing windows = 0)."""
    if adds < t["demand_min_adds"]:
        return None
    values = list(baseline_counts) + [0] * (BASELINE_WINDOWS - len(baseline_counts))
    mean, sd = fmean(values), pstdev(values)
    threshold = mean + t["demand_sigma"] * sd
    if adds < threshold or adds <= mean:
        return None
    return {
        "measured": float(adds), "baseline": mean, "threshold": threshold,
        "severity": "high" if adds >= 2 * max(threshold, t["demand_min_adds"]) else "medium",
        "rule": (f"add_to_cart ≥ mean + {t['demand_sigma']}σ of previous {BASELINE_WINDOWS} "
                 f"windows and ≥ {t['demand_min_adds']}"),
    }


def zero_search_rule(count, baseline_counts, t):
    if count < t["zero_search_min"]:
        return None
    values = list(baseline_counts) + [0] * (BASELINE_WINDOWS - len(baseline_counts))
    baseline = fmean(values)
    threshold = t["zero_search_factor"] * baseline
    if count < threshold:
        return None
    return {
        "measured": float(count), "baseline": baseline, "threshold": threshold,
        "severity": "high" if count >= 2 * max(threshold, t["zero_search_min"]) else "medium",
        "rule": (f"zero-result searches ≥ {t['zero_search_factor']} × mean of previous "
                 f"{BASELINE_WINDOWS} windows and ≥ {t['zero_search_min']}"),
    }

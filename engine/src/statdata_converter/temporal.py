from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .models import Dataset, TemporalColumnProfile
from .report import ConversionReport


_PRECISION_ORDER = {
    "day": 0,
    "second": 1,
    "millisecond": 2,
    "microsecond": 3,
    "nanosecond": 4,
}


class TemporalCompatibilityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TemporalDecision:
    destination_kind: str
    destination_precision: str
    destination_timezone: str | None
    outcome: str
    code: str
    message: str


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, (bool, np.bool_)) else False


def _kind(value: Any) -> str | None:
    if isinstance(value, (pd.Timedelta, timedelta)):
        return "duration"
    if isinstance(value, (pd.Timestamp, datetime)):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, time):
        return "time"
    return None


def _value_precision(value: Any, kind: str) -> str:
    if kind == "date":
        return "day"
    if kind == "duration":
        nanoseconds = int(pd.Timedelta(value).value)
        remainder = abs(nanoseconds)
        if remainder % 1_000:
            return "nanosecond"
        if remainder % 1_000_000:
            return "microsecond"
        if remainder % 1_000_000_000:
            return "millisecond"
        return "second"
    if isinstance(value, pd.Timestamp) and value.nanosecond:
        return "nanosecond"
    microsecond = int(getattr(value, "microsecond", 0))
    if microsecond % 1_000:
        return "microsecond"
    if microsecond:
        return "millisecond"
    return "second"


def _timezone(value: Any) -> str | None:
    timezone = getattr(value, "tzinfo", None)
    if timezone is None:
        return None
    name = getattr(timezone, "key", None) or str(timezone)
    return name if name and name != "None" else None


def _series_profile(
    column: Any,
    series: pd.Series,
    native_format: str | None,
) -> TemporalColumnProfile | None:
    if isinstance(series.dtype, pd.DatetimeTZDtype):
        kind = "datetime"
        timezone = str(series.dtype.tz)
    elif pd.api.types.is_datetime64_any_dtype(series.dtype):
        kind = "datetime"
        timezone = None
    elif pd.api.types.is_timedelta64_dtype(series.dtype):
        kind = "duration"
        timezone = None
    else:
        values = [value for value in series.tolist() if not _is_missing(value)]
        if not values:
            return None
        kinds = {_kind(value) for value in values}
        if None in kinds:
            return None
        if kinds == {"date", "datetime"}:
            kind = "datetime"
        elif len(kinds) == 1:
            kind = kinds.pop()
            if kind is None:
                return None
        else:
            return None
        timezones = {_timezone(value) for value in values if _kind(value) == "datetime"}
        timezone = (
            next(iter(timezones))
            if len(timezones) == 1
            else "mixed" if timezones else None
        )

    values = [value for value in series.tolist() if not _is_missing(value)]
    precisions = [_value_precision(value, kind) for value in values]
    precision = max(
        precisions or ["day" if kind == "date" else "second"],
        key=_PRECISION_ORDER.__getitem__,
    )
    return TemporalColumnProfile(
        column=str(column),
        kind=kind,
        precision=precision,
        timezone=timezone,
        missing_count=int(series.isna().sum()),
        storage_dtype=str(series.dtype),
        native_format=native_format,
    )


def profile_temporal_columns(dataset: Dataset) -> dict[str, TemporalColumnProfile]:
    profiles: dict[str, TemporalColumnProfile] = {}
    for column in dataset.frame.columns:
        profile = _series_profile(
            column,
            dataset.frame[column],
            dataset.metadata.formats.get(str(column)),
        )
        if profile is not None:
            profiles[str(column)] = profile
    dataset.temporal = profiles
    return profiles


def _decision(
    profile: TemporalColumnProfile,
    destination_format: str,
    options: dict[str, Any],
) -> TemporalDecision:
    kind = profile.kind
    precision = profile.precision
    timezone = profile.timezone

    if destination_format == "csv":
        return TemporalDecision(
            "text",
            precision,
            timezone,
            "lossy",
            "temporal.type_to_text",
            "Delimited text preserves the displayed value but does not embed "
            "its temporal type.",
        )

    if destination_format == "excel_xlsx":
        if timezone:
            return TemporalDecision(
                kind,
                precision,
                None,
                "unsupported",
                "temporal.timezone_unsupported",
                "Excel cannot write timezone-aware datetimes.",
            )
        if kind == "datetime" and _PRECISION_ORDER[precision] > _PRECISION_ORDER[
            "millisecond"
        ]:
            return TemporalDecision(
                kind,
                "millisecond",
                None,
                "lossy",
                "temporal.precision_reduced",
                "Excel output reduces datetime precision to milliseconds.",
            )
        if kind == "time":
            return TemporalDecision(
                "text",
                precision,
                None,
                "lossy",
                "temporal.type_to_text",
                "Time-only values are written as text by the Excel adapter.",
            )
        if kind == "duration":
            return TemporalDecision(
                "number",
                precision,
                None,
                "lossy",
                "temporal.duration_to_number",
                "Durations are written as Excel day-fraction numbers.",
            )
        return TemporalDecision(
            kind,
            precision,
            None,
            "exact",
            "temporal.exact",
            "The temporal representation is supported by Excel output.",
        )

    if destination_format in {"stata", "spss_data", "sas_xport"}:
        if kind == "duration":
            return TemporalDecision(
                "text",
                precision,
                None,
                "lossy",
                "temporal.duration_to_text",
                "The destination writer converts durations to text.",
            )
        if kind == "datetime" and (
            timezone
            or _PRECISION_ORDER[precision] > _PRECISION_ORDER["second"]
        ):
            details = []
            if _PRECISION_ORDER[precision] > _PRECISION_ORDER["second"]:
                details.append("fractional-second precision")
            if timezone:
                details.append("timezone information")
            return TemporalDecision(
                kind,
                "second",
                None,
                "lossy",
                "temporal.datetime_reduced",
                "The destination writer removes " + " and ".join(details) + ".",
            )
        return TemporalDecision(
            kind,
            precision,
            timezone,
            "exact",
            "temporal.exact",
            "The temporal representation is supported by this writer.",
        )

    if destination_format == "r_data":
        if kind == "time" or timezone == "mixed":
            return TemporalDecision(
                kind,
                precision,
                timezone,
                "unsupported",
                "temporal.r_writer_unsupported",
                "R output cannot safely serialize this temporal column.",
            )
        if kind == "datetime" and not timezone:
            return TemporalDecision(
                kind,
                min(precision, "microsecond", key=_PRECISION_ORDER.__getitem__),
                "UTC",
                "lossy",
                "temporal.timezone_assumed",
                "Timezone-naive datetimes are written as UTC POSIXct values.",
            )
        if kind == "datetime" and timezone != "UTC":
            return TemporalDecision(
                kind,
                min(precision, "microsecond", key=_PRECISION_ORDER.__getitem__),
                timezone,
                "unverified",
                "temporal.timezone_unverified",
                "This non-UTC POSIXct timezone has not passed the native R "
                "fixture matrix.",
            )
        if _PRECISION_ORDER[precision] > _PRECISION_ORDER["microsecond"]:
            return TemporalDecision(
                kind,
                "microsecond",
                timezone,
                "lossy",
                "temporal.precision_reduced",
                "R output reduces temporal precision to microseconds.",
            )
        return TemporalDecision(
            kind,
            precision,
            timezone,
            "exact",
            "temporal.exact",
            "The value is represented with a base R temporal class.",
        )

    if destination_format == "jsonstat":
        if str(options.get("value_column", "")) == profile.column:
            return TemporalDecision(
                kind,
                precision,
                timezone,
                "unsupported",
                "temporal.jsonstat_value_unsupported",
                "The JSON-stat value column must be numeric.",
            )
        return TemporalDecision(
            "category",
            precision,
            timezone,
            "lossy",
            "temporal.type_to_category",
            "JSON-stat represents this temporal dimension as category text.",
        )

    if destination_format == "eviews_wf2":
        if kind == "datetime":
            return TemporalDecision(
                "text",
                precision,
                timezone,
                "lossy",
                "temporal.type_to_text",
                "EViews WF2 stores this datetime series as alpha text.",
            )
        return TemporalDecision(
            kind,
            precision,
            timezone,
            "unsupported",
            "temporal.eviews_writer_unsupported",
            "The EViews WF2 writer cannot safely serialize this temporal type.",
        )

    return TemporalDecision(
        kind,
        precision,
        timezone,
        "unverified",
        "temporal.destination_unverified",
        "Temporal fidelity has not been verified for this destination.",
    )


def preflight_temporal_conversion(
    dataset: Dataset,
    destination_format: str,
    options: dict[str, Any],
    report: ConversionReport,
) -> None:
    policy = str(options.get("temporal_policy", "compatible")).lower()
    if policy not in {"compatible", "safe"}:
        raise TemporalCompatibilityError(
            "temporal_policy must be 'compatible' or 'safe'."
        )

    profiles = profile_temporal_columns(dataset)
    blocked: list[str] = []
    for profile in profiles.values():
        decision = _decision(profile, destination_format, options)
        report.add_temporal(
            column=profile.column,
            source_kind=profile.kind,
            source_precision=profile.precision,
            source_timezone=profile.timezone,
            destination_kind=decision.destination_kind,
            destination_precision=decision.destination_precision,
            destination_timezone=decision.destination_timezone,
            outcome=decision.outcome,
            code=decision.code,
            message=decision.message,
        )
        if decision.outcome != "exact":
            severity = "error" if decision.outcome == "unsupported" else "warning"
            report.add(
                severity,
                decision.code,
                decision.message,
                [profile.column],
            )
        if decision.outcome == "unsupported" or (
            policy == "safe" and decision.outcome != "exact"
        ):
            blocked.append(profile.column)

    if blocked:
        unique_columns = ", ".join(dict.fromkeys(blocked))
        if policy == "safe":
            reason = "Safe temporal policy rejected a non-exact conversion"
        else:
            reason = "The destination cannot safely represent temporal columns"
        raise TemporalCompatibilityError(f"{reason}: {unique_columns}.")

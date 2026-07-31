from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd
import rdata
from rdata.conversion import DEFAULT_CLASS_MAP as READ_CLASS_MAP
from rdata.conversion.to_r import (
    DEFAULT_CLASS_MAP as WRITE_CLASS_MAP,
    build_r_object,
    convert_pd_array_to_np_array,
)
from rdata.missing import R_INT_NA
from rdata.parser import RObject, RObjectType

from ..models import Dataset, DatasetMetadata, TemporalColumnProfile
from ..report import ConversionReport
from ..temporal import profile_temporal_columns
from .base import Adapter, AdapterError, FormatCapability


def _r_date_constructor(obj: Any, attrs: Any) -> Any:
    del attrs
    values = [
        (
            None
            if np.isnan(value)
            else date(1970, 1, 1) + timedelta(days=float(value))
        )
        for value in np.asarray(obj, dtype=float)
    ]
    return pd.Series(values, dtype=object).array


def _r_posixct_constructor(obj: Any, attrs: Any) -> Any:
    raw = np.asarray(obj, dtype=float)
    missing = np.isnan(raw)
    microseconds = np.zeros(raw.shape, dtype=np.int64)
    microseconds[~missing] = np.rint(raw[~missing] * 1_000_000).astype(np.int64)
    result = pd.to_datetime(microseconds, unit="us", origin="unix", utc=True)
    result = result.where(~missing)
    timezone_values = attrs.get("tzone")
    timezone = (
        str(timezone_values[0])
        if timezone_values is not None
        and len(timezone_values)
        and str(timezone_values[0])
        else None
    )
    if timezone and timezone != "UTC":
        result = result.tz_convert(timezone)
    if not timezone:
        result = result.tz_localize(None)
    return result.array


def _r_difftime_constructor(obj: Any, attrs: Any) -> Any:
    unit = str((attrs.get("units") or ["secs"])[0])
    unit_map = {
        "secs": "s",
        "mins": "m",
        "hours": "h",
        "days": "D",
        "weeks": "W",
    }
    return pd.to_timedelta(
        np.asarray(obj, dtype=float),
        unit=unit_map.get(unit, "s"),
    ).round("us").array


_READ_CONSTRUCTORS = MappingProxyType(
    {
        **dict(READ_CLASS_MAP),
        "Date": _r_date_constructor,
        "POSIXct": _r_posixct_constructor,
        "difftime": _r_difftime_constructor,
    }
)


@dataclass(frozen=True, slots=True)
class _RTemporalVector:
    values: np.ndarray[Any, np.dtype[np.float64]]
    classes: tuple[str, ...]
    timezone: str | None = None
    units: str | None = None


def _r_temporal_vector_constructor(
    data: _RTemporalVector,
    converter: Any,
) -> RObject:
    attributes: dict[str, Any] = {
        "class": np.array(data.classes, dtype=np.dtype("U")),
    }
    if data.timezone is not None:
        attributes["tzone"] = np.array([data.timezone], dtype=np.dtype("U"))
    if data.units is not None:
        attributes["units"] = np.array([data.units], dtype=np.dtype("U"))
    return build_r_object(
        RObjectType.REAL,
        value=data.values,
        is_object=True,
        attributes=converter.convert_to_r_attributes(attributes),
    )


def _numeric_temporal_vector(
    series: pd.Series,
    profile: TemporalColumnProfile,
) -> _RTemporalVector:
    values: list[float] = []
    if profile.kind == "date":
        origin = date(1970, 1, 1)
        for value in series.tolist():
            values.append(
                np.nan
                if pd.isna(value)
                else float((pd.Timestamp(value).date() - origin).days)
            )
        return _RTemporalVector(np.asarray(values), ("Date",))

    if profile.kind == "datetime":
        origin = pd.Timestamp("1970-01-01")
        for value in series.tolist():
            if pd.isna(value):
                values.append(np.nan)
                continue
            timestamp = pd.Timestamp(value)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert("UTC").tz_localize(None)
            seconds = (timestamp - origin).total_seconds()
            values.append(round(seconds * 1_000_000) / 1_000_000)
        return _RTemporalVector(
            np.asarray(values),
            ("POSIXct", "POSIXt"),
            timezone=profile.timezone or "UTC",
        )

    if profile.kind == "duration":
        for value in series.tolist():
            values.append(
                np.nan
                if pd.isna(value)
                else round(pd.Timedelta(value).total_seconds() * 1_000_000)
                / 1_000_000
            )
        return _RTemporalVector(
            np.asarray(values),
            ("difftime",),
            units="secs",
        )

    raise AdapterError(
        f"R output does not safely support temporal column {profile.column!r}."
    )


def _r_dataframe_constructor(
    data: pd.DataFrame,
    converter: Any,
    profiles: dict[str, TemporalColumnProfile],
) -> RObject:
    column_names: list[str] = []
    r_value: list[RObject] = []
    for column, series in data.items():
        if not isinstance(column, str):
            raise AdapterError("R data-frame column names must be strings.")
        column_names.append(column)
        profile = profiles.get(column)
        if profile is not None:
            r_series = converter.convert_to_r_object(
                _numeric_temporal_vector(series, profile)
            )
        else:
            pd_array = series.array
            array = (
                pd_array
                if isinstance(pd_array, pd.Categorical)
                else convert_pd_array_to_np_array(pd_array)
            )
            r_series = converter.convert_to_r_object(array)
        r_value.append(r_series)

    index = data.index
    if isinstance(index, pd.RangeIndex):
        row_names: Any = np.ma.array(
            data=[R_INT_NA, -data.shape[0]],
            mask=[True, False],
            fill_value=R_INT_NA,
        )
    elif isinstance(index, pd.Index) and (
        index.dtype == "object"
        or np.issubdtype(str(index.dtype), np.integer)
    ):
        row_names = index.to_numpy()
    else:
        raise AdapterError(f"R output cannot represent index type {type(index)}.")

    attributes = converter.convert_to_r_attributes(
        {
            "names": np.array(column_names, dtype=np.dtype("U")),
            "class": "data.frame",
            "row.names": row_names,
        }
    )
    return build_r_object(
        RObjectType.VEC,
        value=r_value,
        is_object=True,
        attributes=attributes,
    )


def _data_frame(value: Any, object_name: str) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    raise AdapterError(
        f"The selected R object {object_name!r} is not a data frame."
    )


class RDataAdapter(Adapter):
    capability = FormatCapability(
        id="r_data",
        family="R",
        label="R data object / workspace",
        extensions=(".rds", ".rdata", ".rda"),
        can_read=True,
        can_write=True,
        trust="experimental",
        availability="available",
        detail=(
            "Bundled, local RDS and R workspace reader/writer; no R "
            "installation is required."
        ),
        requires=("rdata",),
    )
    metadata_features = frozenset({"table_name", "value_labels"})

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        requested = str(options.get("object_name", "")).strip()
        try:
            if path.suffix.lower() == ".rds":
                object_name = requested or path.stem
                frame = _data_frame(
                    rdata.read_rds(path, constructor_dict=_READ_CONSTRUCTORS),
                    object_name,
                )
                available_objects = [object_name]
            else:
                workspace = rdata.read_rda(
                    path,
                    constructor_dict=_READ_CONSTRUCTORS,
                )
                available_objects = [
                    name
                    for name, value in workspace.items()
                    if isinstance(value, pd.DataFrame)
                ]
                if requested:
                    if requested not in available_objects:
                        raise AdapterError(
                            "R data-frame object not found: "
                            f"{requested}. Available data frames: "
                            f"{', '.join(available_objects) or 'none'}."
                        )
                    object_name = requested
                else:
                    if not available_objects:
                        raise AdapterError(
                            "The R workspace contains no data-frame object."
                        )
                    object_name = available_objects[0]
                frame = _data_frame(workspace[object_name], object_name)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"Unable to read R data: {exc}") from exc

        value_labels: dict[str, dict[Any, str]] = {}
        categorical_columns: list[str] = []
        frame = frame.copy()
        for column in frame.columns:
            series = frame[column]
            if isinstance(series.dtype, pd.CategoricalDtype):
                categorical_columns.append(str(column))
                value_labels[str(column)] = {
                    index + 1: str(category)
                    for index, category in enumerate(series.cat.categories)
                }
                codes = series.cat.codes
                frame[column] = (
                    codes.where(codes >= 0).add(1).astype("Int64")
                )

        if len(available_objects) > 1 and not requested:
            report.add(
                "warning",
                "r.workspace_object_selected",
                f"The workspace contains {len(available_objects)} data frames; "
                f"{object_name!r} was selected. Set object_name to choose another.",
            )
        if categorical_columns:
            report.add(
                "info",
                "r.factor_levels_preserved",
                "R factors were represented as one-based codes with value labels.",
                categorical_columns,
            )
        result = Dataset(
            frame=frame,
            metadata=DatasetMetadata(
                table_name=object_name,
                value_labels=value_labels,
                extra={
                    "native_format": "r_data",
                    "r_workspace_objects": available_objects,
                },
            ),
        )
        temporal_columns = list(profile_temporal_columns(result))
        if temporal_columns:
            report.add(
                "info",
                "r.temporal_classes_restored",
                "Base R Date, POSIXct, and difftime classes were restored as "
                "typed temporal columns.",
                temporal_columns,
            )
        report.add(
            "warning",
            "r.attributes_not_preserved",
            "Custom R classes and arbitrary object attributes are not represented "
            "by the tabular conversion model.",
        )
        return result

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        object_name = str(
            options.get(
                "object_name",
                dataset.metadata.table_name or "dataset",
            )
        )
        if not object_name.isidentifier():
            object_name = "dataset"
            report.add(
                "warning",
                "r.object_name_normalized",
                "The R workspace object name was normalized to 'dataset'.",
            )

        frame = dataset.frame.copy()
        profiles = profile_temporal_columns(dataset)
        unsupported_time = [
            profile.column
            for profile in profiles.values()
            if profile.kind == "time"
        ]
        if unsupported_time:
            raise AdapterError(
                "R output cannot safely serialize time-only columns: "
                + ", ".join(unsupported_time)
                + "."
            )
        categorical_columns: list[str] = []
        categorical_with_missing: list[str] = []
        for column, labels in dataset.metadata.value_labels.items():
            if column not in frame or not labels:
                continue
            mapped = frame[column].map(labels)
            if mapped.notna().sum() == frame[column].notna().sum():
                if frame[column].isna().any():
                    categorical_with_missing.append(column)
                    continue
                frame[column] = pd.Categorical(
                    mapped,
                    categories=list(dict.fromkeys(labels.values())),
                )
                categorical_columns.append(column)

        constructors = {
            _RTemporalVector: _r_temporal_vector_constructor,
            **dict(WRITE_CLASS_MAP),
            pd.DataFrame: lambda data, converter: _r_dataframe_constructor(
                data,
                converter,
                profiles,
            ),
        }
        try:
            if path.suffix.lower() == ".rds":
                rdata.write_rds(
                    path,
                    frame,
                    constructor_dict=MappingProxyType(constructors),
                )
            else:
                rdata.write_rda(
                    path,
                    {object_name: frame},
                    constructor_dict=MappingProxyType(constructors),
                )
        except Exception as exc:
            raise AdapterError(f"Unable to write R data: {exc}") from exc

        if categorical_columns:
            report.add(
                "info",
                "r.value_labels_to_factors",
                "Representable value labels were written as R factors.",
                categorical_columns,
            )
        if profiles:
            report.add(
                "info",
                "r.temporal_classes_written",
                "Temporal columns were written with base R Date, POSIXct, or "
                "difftime classes.",
                list(profiles),
            )
        if categorical_with_missing:
            report.add(
                "warning",
                "r.factor_with_missing_not_synthesized",
                "Value-labelled columns containing missing values were kept as "
                "codes because the bundled R writer cannot yet serialize factor "
                "missingness safely.",
                categorical_with_missing,
            )
        report.add(
            "warning",
            "r.storage_classes_inferred",
            "R storage classes were inferred from the tabular column types; "
            "custom classes and arbitrary attributes were not synthesized.",
        )

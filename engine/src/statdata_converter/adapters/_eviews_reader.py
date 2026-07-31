"""Local EViews WF1/WF2 table reader.

The WF1 layout and compression logic are adapted from MathWorks'
MATLAB-Reader-for-EViews-Workfile under its BSD 3-Clause license.
"""

from __future__ import annotations

import gzip
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

from .base import AdapterError


WF1_NA = 1e-37
SERIES_TYPE = 44
STANDARD_STORAGE = 11
COMPRESSED_STORAGE = 60
RECORD_SIZE = 70


@dataclass(slots=True)
class EViewsTable:
    frame: pd.DataFrame
    version: str
    page_name: str
    frequency: int
    start_year: int
    start_period: int
    descriptions: dict[str, str]
    failed_series: list[str]
    omitted_objects: list[str]
    page_count: int = 1


def _unpack(stream: BinaryIO, offset: int, code: str) -> int:
    size = struct.calcsize(code)
    stream.seek(offset)
    value = stream.read(size)
    if len(value) != size:
        raise AdapterError("The EViews workfile is truncated.")
    return int(struct.unpack("<" + code, value)[0])


def _obs_labels(
    start_year: int,
    start_period: int,
    frequency: int,
    count: int,
) -> list[str]:
    if frequency <= 0 or (
        frequency == 1 and not 1800 <= start_year <= 2200
    ):
        return [str(index) for index in range(1, count + 1)]
    labels: list[str] = []
    for index in range(count):
        total_period = max(start_period - 1, 0) + index
        year = start_year + total_period // frequency
        period = total_period % frequency + 1
        if frequency == 1:
            labels.append(str(year))
        elif frequency == 4:
            labels.append(f"{year}Q{period}")
        elif frequency == 12:
            labels.append(f"{year}M{period:02d}")
        else:
            labels.append(str(index + 1))
    return labels


def _fit(values: list[float], count: int) -> list[float]:
    if len(values) >= count:
        return values[:count]
    return values + [math.nan] * (count - len(values))


def _read_standard(
    stream: BinaryIO,
    pointer: int,
    expected: int,
    file_size: int,
) -> list[float]:
    count = _unpack(stream, pointer, "i")
    if count < 0 or count > 100_000_000:
        raise AdapterError("Invalid EViews series observation count.")
    data_offset = pointer + 22
    readable = max(0, min(count, (file_size - data_offset) // 8))
    stream.seek(data_offset)
    payload = stream.read(readable * 8)
    values = list(struct.unpack(f"<{readable}d", payload)) if readable else []
    return _fit(
        [
            math.nan if abs(value - WF1_NA) < 1e-40 else value
            for value in values
        ],
        expected,
    )


def _bit_values(payload: bytes) -> list[int]:
    return [
        (byte >> bit) & 1
        for byte in payload
        for bit in range(8)
    ]


def _bits_to_int(bits: list[int], start: int, width: int) -> int | None:
    if start + width > len(bits):
        return None
    return sum(bits[start + offset] << offset for offset in range(width))


def _read_compressed(
    stream: BinaryIO,
    pointer: int,
    expected: int,
    file_size: int,
) -> list[float]:
    count = _unpack(stream, pointer, "i")
    mode = _unpack(stream, pointer + 22, "h")
    flags = _unpack(stream, pointer + 24, "H")
    base = _unpack(stream, pointer + 26, "I")
    if count < 0 or count > 100_000_000:
        raise AdapterError("Invalid compressed EViews series observation count.")

    has_lookup = bool(flags & 0x4000)
    has_rle = bool(flags & 0x0080)
    has_na = bool(flags & 0x8000)
    if has_rle or has_lookup:
        width = flags & 0x003F
    elif has_na:
        lower = flags & 0x00FF
        width = flags & 0x003F if lower & 0x00C0 else lower
    else:
        width = flags & 0x3FFF

    scale = 10 ** abs(mode) if mode < 0 else 1
    if width == 0 or flags == 0x8000:
        return _fit([base / scale] * count, expected)
    if width > 32:
        width = flags & 0x003F
        if width == 0 or width > 32:
            return [math.nan] * expected

    data_bytes = math.ceil(count * width / 8)
    if has_rle:
        data_bytes *= 2
    data_offset = pointer + 30
    stream.seek(data_offset)
    payload = stream.read(min(data_bytes + 16, max(0, file_size - data_offset)))
    bits = _bit_values(payload)
    values: list[float] = []

    if has_lookup:
        indices = [
            _bits_to_int(bits, index * width, width)
            for index in range(count)
        ]
        valid_indices = [index for index in indices if index is not None]
        unique_count = max(valid_indices, default=-1) + 1
        lookup: list[float] = []
        search_start = data_offset + data_bytes
        for candidate in range(search_start, min(search_start + 17, file_size)):
            if candidate + unique_count * 8 > file_size:
                continue
            stream.seek(candidate)
            test = list(
                struct.unpack(
                    f"<{unique_count}d",
                    stream.read(unique_count * 8),
                )
            )
            nonzero = [value for value in test if value != 0]
            if all(math.isfinite(value) for value in test) and all(
                1e-300 <= abs(value) < 1e15 for value in nonzero
            ):
                lookup = test
                break
        values = [
            lookup[index]
            if index is not None and index < len(lookup)
            else math.nan
            for index in indices
        ]
    elif has_rle:
        maximum = (1 << width) - 1
        bit_position = 0
        previous = base / scale
        while len(values) < count:
            delta = _bits_to_int(bits, bit_position, width)
            if delta is None:
                break
            bit_position += width
            if delta == maximum:
                repeat = _bits_to_int(bits, bit_position, 6)
                if repeat is None:
                    break
                bit_position += 6
                values.extend([previous] * min(repeat, count - len(values)))
            else:
                previous = (base + delta) / scale
                values.append(previous)
    else:
        maximum = (1 << width) - 1
        for index in range(count):
            delta = _bits_to_int(bits, index * width, width)
            if delta is None:
                break
            values.append(
                math.nan
                if has_na and delta == maximum
                else (base + delta) / scale
            )

    return _fit(
        [
            math.nan if abs(value - WF1_NA) < 1e-40 else value
            for value in values
        ],
        expected,
    )


def _history(stream: BinaryIO, pointer: int, file_size: int) -> str:
    if pointer <= 0 or pointer + 14 > file_size:
        return ""
    length = _unpack(stream, pointer + 2, "i")
    text_pointer = _unpack(stream, pointer + 10, "I")
    if length <= 0 or length > 10_000 or text_pointer + length > file_size:
        return ""
    stream.seek(text_pointer)
    return stream.read(length).decode("utf-8", errors="replace").strip()


def read_wf1(path: Path) -> EViewsTable:
    file_size = path.stat().st_size
    if file_size < 150:
        raise AdapterError("The file is too small to be an EViews WF1 workfile.")
    with path.open("rb") as stream:
        signature = stream.read(21)
        if signature.startswith(b"New MicroTSP Workfile"):
            version = "MicroTSP/EViews 1-6"
        elif signature.startswith(b"EViews File V01"):
            version = "EViews 7+"
        else:
            raise AdapterError("The file is not a recognized EViews WF1 workfile.")

        header_size = _unpack(stream, 80, "I")
        variable_count = _unpack(stream, 114, "i")
        frequency = _unpack(stream, 124, "h")
        start_year = _unpack(stream, 128, "i")
        start_period = _unpack(stream, 132, "h")
        observation_count = _unpack(stream, 140, "i")
        if (
            header_size < 100
            or header_size > min(file_size, 10_485_760)
            or variable_count <= 0
            or observation_count <= 0
            or variable_count > 1_000_000
            or observation_count > 100_000_000
        ):
            raise AdapterError("The EViews WF1 header is invalid.")

        record_start = header_size + 26
        if record_start + variable_count * RECORD_SIZE > file_size:
            raise AdapterError("The EViews WF1 variable directory is truncated.")

        columns: dict[str, list[float]] = {}
        descriptions: dict[str, str] = {}
        failed: list[str] = []
        omitted: list[str] = []
        for index in range(variable_count):
            offset = record_start + index * RECORD_SIZE
            storage = _unpack(stream, offset + 4, "h")
            data_pointer = _unpack(stream, offset + 14, "I")
            stream.seek(offset + 22)
            raw_name = stream.read(32).split(b"\0", 1)[0]
            name = raw_name.decode("latin-1", errors="replace").strip()
            history_pointer = _unpack(stream, offset + 54, "I")
            object_type = _unpack(stream, offset + 62, "h")
            if not name or name.upper() == "RESID":
                continue
            if object_type != SERIES_TYPE:
                omitted.append(name)
                continue
            try:
                if data_pointer <= 0 or data_pointer >= file_size:
                    raise AdapterError("Invalid series data pointer.")
                if storage == STANDARD_STORAGE:
                    values = _read_standard(
                        stream, data_pointer, observation_count, file_size
                    )
                elif storage == COMPRESSED_STORAGE:
                    values = _read_compressed(
                        stream, data_pointer, observation_count, file_size
                    )
                else:
                    omitted.append(name)
                    continue
                unique_name = name
                suffix = 2
                while unique_name in columns or unique_name == "obs":
                    unique_name = f"{name}_{suffix}"
                    suffix += 1
                columns[unique_name] = values
                description = _history(stream, history_pointer, file_size)
                if description:
                    descriptions[unique_name] = description
            except Exception:
                failed.append(name)

    if not columns:
        raise AdapterError("No readable numeric series were found in the WF1 file.")
    frame = pd.DataFrame(
        {
            "obs": _obs_labels(
                start_year, start_period, frequency, observation_count
            ),
            **columns,
        }
    )
    return EViewsTable(
        frame=frame,
        version=version,
        page_name=path.stem,
        frequency=frequency,
        start_year=start_year,
        start_period=start_period,
        descriptions=descriptions,
        failed_series=failed,
        omitted_objects=omitted,
    )


def _get(value: dict[str, Any], first: str, second: str, default: Any = None) -> Any:
    return value.get(first, value.get(second, default))


def _select_page(pages: list[dict[str, Any]], requested: Any) -> dict[str, Any]:
    if requested in (None, ""):
        return pages[0]
    if isinstance(requested, int) or str(requested).isdigit():
        index = int(requested)
        if index < 0 or index >= len(pages):
            raise AdapterError(f"EViews page index {index} is out of range.")
        return pages[index]
    for page in pages:
        if str(_get(page, "x_name", "_name", "")) == str(requested):
            return page
    raise AdapterError(f"EViews page not found: {requested}.")


def _clean_wf2_values(values: list[Any]) -> list[Any]:
    numeric = True
    cleaned: list[Any] = []
    for value in values:
        if value is None or (
            isinstance(value, str) and value.strip().lower() in {"na", "nan"}
        ):
            cleaned.append(math.nan)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            cleaned.append(value)
        else:
            numeric = False
            cleaned.append(value)
    if not numeric:
        return [None if isinstance(value, float) and math.isnan(value) else value for value in cleaned]
    return cleaned


def read_wf2(path: Path, requested_page: Any = None) -> EViewsTable:
    try:
        with path.open("rb") as stream:
            compressed = stream.read(2) == b"\x1f\x8b"
        opener = gzip.open if compressed else open
        with opener(path, "rt", encoding="utf-8") as stream:
            data = json.load(stream)
    except Exception as exc:
        raise AdapterError(f"Unable to parse EViews WF2 JSON: {exc}") from exc

    raw_pages = _get(data, "x_pages", "_pages")
    if isinstance(raw_pages, dict):
        pages = [raw_pages]
    elif isinstance(raw_pages, list):
        pages = raw_pages
    else:
        raise AdapterError("The file does not contain EViews WF2 pages.")
    if not pages:
        raise AdapterError("The EViews WF2 workfile contains no pages.")
    page = _select_page(pages, requested_page)
    page_name = str(_get(page, "x_name", "_name", "Page1"))
    try:
        count = int(page["range"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AdapterError("The EViews WF2 page has no valid range.") from exc
    frequency_info = page.get("frequency", {})
    frequency_code = str(frequency_info.get("value", "U")).upper()
    frequency = {"A": 1, "Y": 1, "Q": 4, "M": 12}.get(frequency_code, 0)
    start = frequency_info.get("start", 1)
    start_year = 1
    start_period = 1
    if isinstance(start, (int, float)):
        start_year = int(start)
    elif isinstance(start, str):
        parts = start.split("-", 2)
        if parts and parts[0].isdigit():
            start_year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            start_period = (
                math.ceil(month / 3)
                if frequency == 4
                else month if frequency == 12 else 1
            )

    raw_objects = _get(page, "x_objects", "_objects", [])
    if isinstance(raw_objects, dict):
        objects = [raw_objects]
    else:
        objects = raw_objects or []
    columns: dict[str, list[Any]] = {}
    descriptions: dict[str, str] = {}
    omitted: list[str] = []
    failed: list[str] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        name = str(_get(obj, "x_name", "_name", "")).strip()
        if not name or name.startswith("@") or name.upper() == "RESID":
            continue
        base_type = str(_get(obj, "x_basetype", "_basetype", "")).lower()
        object_type = str(_get(obj, "x_type", "_type", "")).lower()
        is_series = base_type == "series" or "series_" in object_type
        values = obj.get("data")
        if not is_series or not isinstance(values, list):
            omitted.append(name)
            continue
        if len(values) != count:
            failed.append(name)
            continue
        unique_name = name
        suffix = 2
        while unique_name in columns or unique_name == "obs":
            unique_name = f"{name}_{suffix}"
            suffix += 1
        columns[unique_name] = _clean_wf2_values(values)
        labels = _get(obj, "x_labels", "_labels", {})
        if isinstance(labels, dict) and labels.get("description"):
            descriptions[unique_name] = str(labels["description"])

    if not columns:
        raise AdapterError("No readable series were found in the WF2 page.")
    frame = pd.DataFrame(
        {
            "obs": _obs_labels(start_year, start_period, frequency, count),
            **columns,
        }
    )
    return EViewsTable(
        frame=frame,
        version="WF2",
        page_name=page_name,
        frequency=frequency,
        start_year=start_year,
        start_period=start_period,
        descriptions=descriptions,
        failed_series=failed,
        omitted_objects=omitted,
        page_count=len(pages),
    )


def read_eviews(path: Path, requested_page: Any = None) -> EViewsTable:
    with path.open("rb") as stream:
        header = stream.read(32)
    if path.suffix.lower() == ".wf2" or header.startswith((b"{", b"\x1f\x8b")):
        return read_wf2(path, requested_page)
    return read_wf1(path)

"""Independent reader for native JMP data tables.

This module is a Python adaptation of JMPReader.jl 0.2.2:
https://github.com/jaakkor2/JMPReader.jl

JMPReader.jl is Copyright (C) 2024 Jaakko Ruohio and distributed under
the MIT License. See licenses/JMPReader-MIT.txt in the project root.
"""

from __future__ import annotations

import gzip
import io
import math
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


MAGIC_JMP = bytes(
    [
        0xFF,
        0xFF,
        0x00,
        0x00,
        0x07,
        0x00,
        0x00,
        0x00,
        0x04,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x02,
        0x00,
    ]
)
GZIP_SECTION_START = b"\xef\xbe\xfe\xca"
JMP_EPOCH = pd.Timestamp("1904-01-01")
ROW_STATE_MARKERS = (
    "•",
    "+",
    "X",
    "□",
    "◊",
    "△",
    "Y",
    "Z",
    "◯",
    "▭",
    "▯",
    "*",
    "⚫",
    "▬",
    "▮",
    "■",
    "⧫",
    "▽",
    "◁",
    "▷",
    "▲",
    "▼",
    "◀",
    "▶",
    "∧",
    "∨",
    "<",
    ">",
    "∣",
    "─",
    "/",
    "\\",
)


@dataclass(slots=True)
class JmpInfo:
    version: str
    build_string: str
    saved_at: datetime | None
    rows: int
    columns: int
    column_names: list[str]
    column_offsets: list[int]


@dataclass(slots=True)
class JmpReadResult:
    frame: pd.DataFrame
    info: JmpInfo
    formats: dict[str, str] = field(default_factory=dict)
    warnings: list[tuple[str, str, list[str]]] = field(default_factory=list)


class JmpReadError(ValueError):
    pass


def _unpack(stream: io.BytesIO, format_code: str) -> Any:
    size = struct.calcsize(format_code)
    value = stream.read(size)
    if len(value) != size:
        raise JmpReadError("The JMP file ended unexpectedly.")
    return struct.unpack(format_code, value)[0]


def _read_string(stream: io.BytesIO, width: int) -> str:
    formats = {1: "<b", 2: "<h", 4: "<i"}
    if width not in formats:
        raise JmpReadError(f"Unsupported JMP string-length width: {width}.")
    length = int(_unpack(stream, formats[width]))
    if length < 0:
        raise JmpReadError("The JMP file contains a negative string length.")
    value = stream.read(length)
    if len(value) != length:
        raise JmpReadError("The JMP file ended inside a text value.")
    return value.decode("utf-8", errors="replace")


def _read_array(
    stream: io.BytesIO,
    dtype: str | np.dtype[Any],
    length: int,
) -> np.ndarray[Any, Any]:
    resolved = np.dtype(dtype)
    value = stream.read(resolved.itemsize * length)
    if len(value) != resolved.itemsize * length:
        raise JmpReadError("The JMP file ended inside a numeric array.")
    return np.frombuffer(value, dtype=resolved).copy()


def _read_until(stream: io.BytesIO, marker: bytes) -> None:
    data = stream.getbuffer()
    position = bytes(data).find(marker, stream.tell())
    if position < 0:
        raise JmpReadError("A required JMP data section was not found.")
    stream.seek(position + len(marker))


def _peek(stream: io.BytesIO) -> bytes:
    value = stream.read(1)
    stream.seek(-len(value), io.SEEK_CUR)
    return value


def _seek_to_column_offsets(
    stream: io.BytesIO,
    column_count: int,
) -> tuple[int, int]:
    stream.seek(2)
    while True:
        _read_until(stream, b"\xff\xff")
        while _peek(stream) == b"\xff":
            stream.seek(1, io.SEEK_CUR)
        if stream.tell() >= len(stream.getbuffer()):
            raise JmpReadError("Could not find JMP column offset data.")
        stream.seek(10, io.SEEK_CUR)
        visible = int(_unpack(stream, "<I"))
        hidden = int(_unpack(stream, "<I"))
        stream.seek(8, io.SEEK_CUR)
        if visible + hidden == column_count:
            return visible, hidden
        stream.seek(-18, io.SEEK_CUR)


def _column_info(
    stream: io.BytesIO,
    column_count: int,
) -> tuple[list[str], list[int]]:
    negative_markers = {
        b"\xfc\xff",
        b"\xfd\xff",
        b"\xfe\xff",
        b"\xff\xff",
    }
    while True:
        marker = stream.read(2)
        if marker in negative_markers:
            count = int(_unpack(stream, "<q"))
            stream.seek(count, io.SEEK_CUR)
        else:
            stream.seek(-2, io.SEEK_CUR)
            break

    repeated_count = int(_unpack(stream, "<i"))
    if repeated_count != column_count:
        raise JmpReadError(
            "JMP column metadata is inconsistent "
            f"({column_count} columns versus {repeated_count})."
        )
    offsets = [int(value) for value in _read_array(stream, "<i8", column_count)]
    names: list[str] = []
    for offset in offsets:
        stream.seek(offset)
        names.append(_read_string(stream, 2))
    return names, offsets


def _seconds_to_timestamps(
    values: list[int | float | None],
) -> list[pd.Timestamp | None]:
    result: list[pd.Timestamp | None] = []
    for value in values:
        if value is None:
            result.append(None)
            continue
        try:
            result.append(JMP_EPOCH + pd.to_timedelta(float(value), unit="s"))
        except (OverflowError, pd.errors.OutOfBoundsDatetime):
            result.append(None)
    return result


def _numeric_values(raw: bytes, width: int) -> list[int | float | None]:
    dtypes = {1: "<i1", 2: "<i2", 4: "<i4", 8: "<f8"}
    if width not in dtypes:
        raise JmpReadError(f"Unsupported JMP numeric width: {width}.")
    dtype = np.dtype(dtypes[width])
    values = np.frombuffer(raw, dtype=dtype)
    result: list[int | float | None] = []
    if width == 8:
        for value in values:
            number = float(value)
            result.append(None if math.isnan(number) else number)
        return result
    sentinel = np.iinfo(dtype).min + 1
    for value in values:
        number = int(value)
        result.append(None if number == sentinel else number)
    return result


def _fixed_strings(raw: bytes, row_count: int, width: int) -> list[str]:
    values: list[str] = []
    for index in range(row_count):
        value = raw[index * width : (index + 1) * width]
        values.append(
            value.split(b"\0", 1)[0].decode("utf-8", errors="replace")
        )
    return values


def _variable_strings(
    data: bytes,
    row_count: int,
) -> list[str]:
    if len(data) >= 8 and struct.unpack("<q", data[:8])[0] == len(data):
        stream = io.BytesIO(data)
        _unpack(stream, "<q")
        stream.seek(9, io.SEEK_CUR)
        _unpack(stream, "<q")
        index_width = int(_unpack(stream, "<b"))
        index_formats = {1: "<B", 2: "<H", 4: "<I"}
        if index_width not in index_formats:
            raise JmpReadError(
                f"Unsupported JMP string-pool index width: {index_width}."
            )
        indexes = [
            int(_unpack(stream, index_formats[index_width]))
            for _ in range(row_count)
        ]
        pool_count = max(indexes, default=0)
        length_width = int(_unpack(stream, "<b"))
        length_formats = {1: "<b", 2: "<h"}
        if length_width not in length_formats:
            raise JmpReadError(
                f"Unsupported JMP string-pool length width: {length_width}."
            )
        pool: list[str] = []
        for _ in range(pool_count):
            length = int(_unpack(stream, length_formats[length_width]))
            value = stream.read(length)
            pool.append(value.decode("utf-8", errors="replace"))
        return ["" if index == 0 else pool[index - 1] for index in indexes]

    if len(data) < 13:
        raise JmpReadError("The JMP variable-width string section is incomplete.")
    width_bytes = data[8]
    if width_bytes == 1:
        widths = np.frombuffer(data[13 : 13 + row_count], dtype="<i1")
        value_data = data[13 + row_count :]
    elif width_bytes == 2:
        widths = np.frombuffer(
            data[13 : 13 + 2 * row_count],
            dtype="<i2",
        )
        value_data = data[13 + 2 * row_count :]
    else:
        raise JmpReadError(
            f"Unsupported JMP variable-string width: {width_bytes}."
        )
    return _strings_from_widths(value_data, widths)


def _strings_from_widths(
    data: bytes,
    widths: np.ndarray[Any, Any],
) -> list[str]:
    values: list[str] = []
    position = 0
    for raw_width in widths:
        width = int(raw_width)
        if width < 0:
            raise JmpReadError("The JMP file contains a negative text width.")
        value = data[position : position + width]
        if len(value) != width:
            raise JmpReadError("The JMP file ended inside a text column.")
        values.append(value.decode("utf-8", errors="replace"))
        position += width
    return values


def _uncompressed_variable_strings(
    stream: io.BytesIO,
    column_end: int,
    row_count: int,
) -> list[str]:
    stream.seek(6, io.SEEK_CUR)
    first_length = int(_unpack(stream, "<q"))
    stream.seek(first_length + 2, io.SEEK_CUR)
    second_length = int(_unpack(stream, "<I"))
    stream.seek(second_length + 8, io.SEEK_CUR)
    width_bytes = int(_unpack(stream, "<B"))
    _unpack(stream, "<I")
    formats = {1: "<i1", 2: "<i2", 4: "<i4"}
    if width_bytes not in formats:
        raise JmpReadError(
            f"Unsupported JMP variable-string width: {width_bytes}."
        )
    widths = _read_array(stream, formats[width_bytes], row_count)
    total = int(widths.sum())
    stream.seek(column_end - total)
    return _strings_from_widths(stream.read(total), widths)


def _row_state_markers(
    data: bytes,
    row_count: int,
    width: int,
) -> list[str]:
    values: list[str] = []
    for row in range(row_count):
        offset = width * row
        marker_index = (data[offset + 6] << 8) | data[offset + 5]
        if marker_index < len(ROW_STATE_MARKERS):
            values.append(ROW_STATE_MARKERS[marker_index])
        else:
            values.append(chr(marker_index))
    return values


DATE_CODES = {
    0x65,
    0x66,
    0x67,
    0x6E,
    0x6F,
    0x70,
    0x71,
    0x72,
    0x75,
    0x76,
    0x7A,
    0x7F,
    0x88,
    0x8B,
}
DATE_PAIRS = {
    (0x67, 0x65),
    (0x6F, 0x65),
    (0x72, 0x65),
    (0x72, 0x6F),
    (0x72, 0x7F),
    (0x72, 0x80),
    (0x7F, 0x72),
    (0x88, 0x65),
    (0x88, 0x7A),
}
DATETIME_FOUR_CODES = {
    0x69,
    0x6A,
    0x6C,
    0x6D,
    0x73,
    0x74,
    0x77,
    0x78,
    0x79,
    0x7B,
    0x7C,
    0x7D,
    0x7E,
    0x80,
    0x81,
    0x82,
    0x86,
    0x87,
    0x89,
    0x8A,
}
DATETIME_FIVE_CODES = {0x69, 0x6A, 0x73, 0x74, 0x77, 0x78, 0x7E, 0x81}
DATETIME_PAIRS = {(0x77, 0x80), (0x77, 0x7F), (0x89, 0x65)}
DURATION_CODES = {0x0C, 0x6B, 0x6C, 0x6D, 0x83, 0x84, 0x85}


def _column_data(
    stream: io.BytesIO,
    info: JmpInfo,
    column_index: int,
) -> tuple[list[Any], str | None, list[tuple[str, str]]]:
    offset = info.column_offsets[column_index]
    stream.seek(offset)
    column_name = _read_string(stream, 2)
    codes = tuple(stream.read(6))
    if len(codes) != 6:
        raise JmpReadError("The JMP column header is incomplete.")
    dt1, dt2, dt3, dt4, dt5, dt6 = codes
    marked_position = stream.tell()
    column_end = (
        len(stream.getbuffer())
        if column_index == info.columns - 1
        else info.column_offsets[column_index + 1]
    )

    compressed = dt1 in {0x09, 0x0A}
    if compressed:
        _read_until(stream, GZIP_SECTION_START)
        gzip_length = int(_unpack(stream, "<Q"))
        expected_length = int(_unpack(stream, "<Q"))
        compressed_data = stream.read(gzip_length)
        try:
            data = gzip.decompress(compressed_data)
        except (EOFError, OSError) as exc:
            raise JmpReadError(
                f"Could not decompress JMP column {column_name!r}."
            ) from exc
        if expected_length and len(data) != expected_length:
            raise JmpReadError(
                f"JMP column {column_name!r} decompressed to an unexpected size."
            )
    else:
        stream.seek(offset)
        data = stream.read(column_end - offset)
        stream.seek(marked_position)

    warnings: list[tuple[str, str]] = []

    if dt1 in {0x01, 0x0A}:
        width = dt6 if dt6 in {1, 2, 4} else 8
        raw = data[-width * info.rows :]
        values = _numeric_values(raw, width)
        pair = (dt4, dt5)
        numeric_codes = {0x00, 0x03, 0x42, 0x43, 0x44, 0x59, 0x60, 0x63}
        if (
            (dt4 == dt5 and dt4 in numeric_codes)
            or dt5 in {0x5E, 0x63}
            or (dt4 == dt5 and dt4 in {0x5F, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56})
        ):
            return values, None, warnings

        timestamps = _seconds_to_timestamps(values)
        if (dt4 == dt5 and dt4 in DATE_CODES) or pair in DATE_PAIRS:
            return (
                [None if value is None else value.normalize() for value in timestamps],
                "JMP date",
                warnings,
            )
        if (
            (dt5 in DATETIME_FIVE_CODES and dt4 in DATETIME_FOUR_CODES)
            or (dt4 == dt5 and dt4 in {0x79, 0x7D})
            or pair in DATETIME_PAIRS
        ):
            return timestamps, "JMP datetime", warnings
        if dt4 == dt5 == 0x82:
            return (
                [
                    None
                    if value is None
                    else value.strftime("%H:%M:%S.%f").rstrip("0").rstrip(".")
                    for value in timestamps
                ],
                "JMP time converted to text",
                [
                    (
                        "jmp.time_values_as_text",
                        "JMP time-of-day values were converted to ISO-like text.",
                    )
                ],
            )
        if (
            (dt4 == dt5 and dt4 in DURATION_CODES)
            or pair == (0x84, 0x79)
        ):
            return (
                values,
                "JMP duration in seconds",
                [
                    (
                        "jmp.duration_values_as_seconds",
                        "JMP duration values were represented as numeric seconds.",
                    )
                ],
            )

    if dt1 in {0xFF, 0xFE, 0xFC}:
        width = dt5 if dt5 in {1, 2, 4} else 8
        return _numeric_values(data[-width * info.rows :], width), None, warnings

    if dt1 == 0x09 and dt2 == 0x03:
        values = _row_state_markers(data, info.rows, dt5)
        return (
            values,
            "JMP row-state marker",
            [
                (
                    "jmp.row_state_color_not_extracted",
                    "JMP row-state markers were read, but row-state colors were not retained.",
                )
            ],
        )

    if dt1 == 0x03 and dt2 == 0x03:
        width = dt5
        values = np.frombuffer(data[-width * info.rows :], dtype="<i8")
        return [int(value) for value in values], None, warnings

    if dt1 in {0x02, 0x09} and dt2 in {0x01, 0x02}:
        if (dt3 == 0 and dt4 == 0 and dt5 > 0) or (
            1 <= dt3 <= 7 and dt4 == 0
        ):
            width = dt5
            return (
                _fixed_strings(data[-info.rows * width :], info.rows, width),
                None,
                warnings,
            )
        if dt3 == dt4 == dt5 == 0:
            if compressed:
                return _variable_strings(data, info.rows), None, warnings
            return (
                _uncompressed_variable_strings(stream, column_end, info.rows),
                None,
                warnings,
            )

    return (
        [None] * info.rows,
        None,
        [
            (
                "jmp.unsupported_column_encoding",
                (
                    "The native reader does not yet understand the JMP encoding "
                    f"{codes!r} used by column {column_name!r}; its values are missing."
                ),
            )
        ],
    )


def _metadata(stream: io.BytesIO) -> JmpInfo:
    stream.seek(0)
    _read_until(stream, b"\x07\x00\x08\x00\x00\x00")
    stream.seek(-38, io.SEEK_CUR)
    rows = int(_unpack(stream, "<q"))
    columns = int(_unpack(stream, "<i"))
    _read_array(stream, "<i2", 5)
    _read_string(stream, 4).rstrip("\0")
    _read_array(stream, "<u2", 3)
    saved_seconds = float(_unpack(stream, "<d"))
    saved_values = _seconds_to_timestamps([saved_seconds])
    saved_at = (
        None
        if saved_values[0] is None
        else saved_values[0].to_pydatetime()
    )
    _unpack(stream, "<H")
    build_string = _read_string(stream, 4)
    match = re.search(r"Version (.*)$", build_string)
    if not match:
        raise JmpReadError("Could not determine the JMP file version.")
    version = match.group(1)

    visible, hidden = _seek_to_column_offsets(stream, columns)
    _read_array(stream, "<u4", visible)
    _read_array(stream, "<u4", hidden)
    _read_array(stream, "<u2", columns)
    _read_array(stream, "<u4", 7)
    names, offsets = _column_info(stream, columns)
    if visible + hidden != columns:
        raise JmpReadError("JMP visible and hidden column counts are inconsistent.")
    return JmpInfo(
        version=version,
        build_string=build_string,
        saved_at=saved_at,
        rows=rows,
        columns=columns,
        column_names=names,
        column_offsets=offsets,
    )


def read_jmp(path: str | Path) -> JmpReadResult:
    """Read a native JMP data table without JMP software."""

    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise JmpReadError(f"Could not open JMP file: {source}") from exc
    if not raw.startswith(MAGIC_JMP):
        raise JmpReadError(
            "The file does not have the expected native JMP data-table signature."
        )
    stream = io.BytesIO(raw)
    info = _metadata(stream)
    values: dict[str, list[Any]] = {}
    formats: dict[str, str] = {}
    warnings: list[tuple[str, str, list[str]]] = []
    for index, column_name in enumerate(info.column_names):
        column_values, display_format, column_warnings = _column_data(
            stream,
            info,
            index,
        )
        values[column_name] = column_values
        if display_format:
            formats[column_name] = display_format
        warnings.extend(
            (code, message, [column_name])
            for code, message in column_warnings
        )
    return JmpReadResult(
        frame=pd.DataFrame(values),
        info=info,
        formats=formats,
        warnings=warnings,
    )

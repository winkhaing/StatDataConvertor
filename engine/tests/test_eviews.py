import json
import struct

import pandas as pd

from statdata_converter.service import ConversionService


def _write_simple_wf1(path) -> None:
    payload = bytearray(400)
    payload[:21] = b"New MicroTSP Workfile"
    struct.pack_into("<I", payload, 80, 180)
    struct.pack_into("<i", payload, 114, 1)
    struct.pack_into("<h", payload, 124, 1)
    struct.pack_into("<i", payload, 128, 2000)
    struct.pack_into("<h", payload, 132, 1)
    struct.pack_into("<i", payload, 140, 3)

    record = 206
    data_pointer = 300
    struct.pack_into("<h", payload, record + 4, 11)
    struct.pack_into("<I", payload, record + 14, data_pointer)
    payload[record + 22 : record + 23] = b"X"
    struct.pack_into("<h", payload, record + 62, 44)

    struct.pack_into("<i", payload, data_pointer, 3)
    struct.pack_into(
        "<3d",
        payload,
        data_pointer + 22,
        1.25,
        2.5,
        5.0,
    )
    path.write_bytes(payload)


def test_reads_wf1_without_eviews(tmp_path) -> None:
    source = tmp_path / "sample.wf1"
    destination = tmp_path / "sample.csv"
    _write_simple_wf1(source)

    result = ConversionService().convert(source, destination)
    frame = pd.read_csv(destination)

    assert frame.to_dict(orient="list") == {
        "obs": [2000, 2001, 2002],
        "X": [1.25, 2.5, 5.0],
    }
    assert result["report"]["input_format"] == "eviews_wf1"


def test_wf2_json_read_write_and_gzip(tmp_path) -> None:
    source = tmp_path / "source.csv"
    workfile = tmp_path / "sample.wf2"
    destination = tmp_path / "roundtrip.csv"
    expected = pd.DataFrame(
        {
            "gdp": [100.0, 105.5, 109.0],
            "region": ["North", "South", None],
        }
    )
    expected.to_csv(source, index=False)
    service = ConversionService()

    write_result = service.convert(
        source,
        workfile,
        output_options={"gzip": True},
    )
    service.convert(workfile, destination)
    actual = pd.read_csv(destination)

    pd.testing.assert_frame_equal(
        actual.drop(columns=["obs"]),
        expected,
        check_dtype=False,
    )
    assert workfile.read_bytes()[:2] == b"\x1f\x8b"
    assert any(
        change["code"] == "eviews.wf2_minimal_profile"
        for change in write_result["report"]["changes"]
    )


def test_reads_multi_page_wf2_by_name(tmp_path) -> None:
    source = tmp_path / "pages.wf2"
    destination = tmp_path / "selected.csv"
    source.write_text(
        json.dumps(
            {
                "_pages": [
                    {
                        "_name": "First",
                        "range": 2,
                        "frequency": {"value": "U", "start": 1},
                        "_objects": [
                            {
                                "_name": "x",
                                "_basetype": "series",
                                "_type": "series_double",
                                "data": [1, 2],
                            }
                        ],
                    },
                    {
                        "_name": "Second",
                        "range": 2,
                        "frequency": {"value": "U", "start": 1},
                        "_objects": [
                            {
                                "_name": "y",
                                "_basetype": "series",
                                "_type": "series_double",
                                "data": [3, 4],
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    ConversionService().convert(
        source,
        destination,
        input_options={"page": "Second"},
    )

    assert pd.read_csv(destination).to_dict(orient="list") == {
        "obs": [1, 2],
        "y": [3, 4],
    }

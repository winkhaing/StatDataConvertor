from statdata_converter.service import ConversionService


def test_capabilities_are_explicit_and_local() -> None:
    result = ConversionService().capabilities()
    formats = {item["id"]: item for item in result["formats"]}

    assert result["privacy"] == {
        "local_only": True,
        "network_access": False,
    }
    assert formats["csv"]["can_read"] is True
    assert formats["csv"]["can_write"] is True
    assert formats["jsonstat"]["can_write"] is True
    assert formats["jmp"]["availability"] == "available"
    assert formats["jmp"]["can_read"] is True
    assert formats["jmp"]["can_write"] is False
    assert formats["sas_data"]["can_write"] is False
    assert formats["r_data"]["availability"] == "available"
    assert formats["r_data"]["can_read"] is True
    assert formats["r_data"]["can_write"] is True
    assert "Rscript" not in formats["r_data"]["requires"]
    assert formats["eviews_wf1"]["availability"] == "available"
    assert formats["eviews_wf1"]["can_read"] is True
    assert formats["eviews_wf1"]["can_write"] is False
    assert formats["eviews_wf2"]["can_read"] is True
    assert formats["eviews_wf2"]["can_write"] is True

import json
import pytest
from mev_share_listener.parser import parse_event_payload, parse_sse_line
from mev_share_listener.models import MevEvent


SAMPLE_TX_HINT = {
    "hash": "0x5a18a91a92e16f3febe47a83d3e8e2c071d0e515d97f5ef24dfa8b846e4922e2",
    "logs": [
        {
            "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x0000000000000000000000006b175474e89094c44da98b954eedeac495271d0f",
                "0x0000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488d"
            ],
            "data": "0x0000000000000000000000000000000000000000000000056bc75e2d63100000"
        }
    ],
    "txs": [
        {
            "to": "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",
            "functionSelector": "0x38ed1739",
            "callData": "0x38ed17390000000000000000000000000000000000000000000000000000000000000001"
        }
    ]
}

SAMPLE_BUNDLE_HINT = {
    "hash": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "txs": [
        {"to": "0x1111111254eeb25477b68fb85ed929f73a960582", "functionSelector": "0x12aa3caf"},
        {"to": "0xdef1c0ded9bec7f1a1670819833240f027b25eff", "callData": "0x5f57552911"}
    ]
}


def test_parse_full_tx_event():
    raw = json.dumps(SAMPLE_TX_HINT)
    event = parse_event_payload(raw)

    # print(f"parsed: {event}")
    assert isinstance(event, MevEvent)
    assert event.tx_hash == SAMPLE_TX_HINT["hash"].lower()
    assert len(event.logs) == 1
    assert event.logs[0].address == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
    assert len(event.logs[0].topics) == 3
    assert event.logs[0].topics[0].startswith("0xddf252ad")
    assert len(event.txs) == 1
    assert event.txs[0].to_address == "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"
    assert event.txs[0].selector == "0x38ed1739"


def test_parse_bundle_with_multiple_txs():
    event = parse_event_payload(SAMPLE_BUNDLE_HINT)
    assert len(event.txs) == 2
    # second tx had no explicit functionSelector, parser should derive it from callData
    assert event.txs[1].selector == "0x5f575529"
    assert event.txs[1].to_address == "0xdef1c0ded9bec7f1a1670819833240f027b25eff"


def test_parse_hash_only_hint():
    payload = {"hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"}
    event = parse_event_payload(payload)
    assert event.tx_hash == payload["hash"]
    assert event.logs == []
    assert event.txs == []


def test_parse_short_calldata_does_not_crash():
    # tx hints can contain plain ether transfers where callData is just '0x' or shorter than 4 bytes
    payload = {
        "hash": "0x" + "a" * 64,
        "txs": [{"to": "0x" + "1" * 40, "callData": "0x12"}]
    }
    event = parse_event_payload(payload)
    assert len(event.txs) == 1
    assert event.txs[0].selector is None
    assert event.txs[0].call_data == "0x12"


def test_parse_empty_call_data():
    payload = {
        "hash": "0x" + "b" * 64,
        "txs": [{"to": "0x" + "2" * 40, "callData": "0x"}]
    }
    event = parse_event_payload(payload)
    assert event.txs[0].selector is None
    assert event.txs[0].call_data == "0x"


def test_parse_sse_line_comments_and_pings():
    assert parse_sse_line(":keepalive") is None
    assert parse_sse_line("") is None
    assert parse_sse_line(": ping - 1234") is None


def test_parse_sse_line_data():
    line = 'data: {"hash":"0x"' + 'c'*64 + '}'
    data = parse_sse_line(line)
    assert data is not None
    assert "hash" in data


def test_parse_invalid_json():
    with pytest.raises(ValueError, match="invalid json"):
        parse_event_payload("not a json string at all")

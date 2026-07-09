import json
from typing import Any, Dict, List, Optional
from mev_share_listener.models import MevEvent, TxHint, LogHint


def parse_sse_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("data:"):
        payload = line[5:].strip()
        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None
    return None


def _clean_hex(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    val = val.strip().lower()
    if not val.startswith("0x"):
        val = "0x" + val
    return val


def parse_event_payload(data: Dict[str, Any]) -> MevEvent:
    """Extract transaction and log hints from flashbots mev-share event payload."""
    tx_hash = data.get("hash") or ""
    logs_raw = data.get("logs") or []
    txs_raw = data.get("txs") or []

    parsed_logs: List[LogHint] = []
    for log_item in logs_raw:
        if not isinstance(log_item, dict):
            continue
        address = _clean_hex(log_item.get("address")) or ""
        topics = [_clean_hex(t) for t in log_item.get("topics", []) if isinstance(t, str)]
        topics = [t for t in topics if t is not None]
        data_field = log_item.get("data") or "0x"
        parsed_logs.append(LogHint(address=address, topics=topics, data=data_field))

    parsed_txs: List[TxHint] = []
    for tx in txs_raw:
        if not isinstance(tx, dict):
            continue
        to_addr = _clean_hex(tx.get("to"))
        
        # flashbots has been seen returning both callData and calldata
        raw_calldata = tx.get("callData") or tx.get("calldata") or ""
        selector = _clean_hex(tx.get("functionSelector"))
        if not selector and raw_calldata and len(raw_calldata) >= 10:
            selector = raw_calldata[:10].lower()
            
        parsed_txs.append(TxHint(to=to_addr, selector=selector, calldata=raw_calldata))

    # Builder payload edge case: top-level single hint without txs list
    if not parsed_txs and (data.get("to") or data.get("functionSelector") or data.get("callData") or data.get("calldata")):
        to_addr = _clean_hex(data.get("to"))
        raw_calldata = data.get("callData") or data.get("calldata") or ""
        selector = _clean_hex(data.get("functionSelector"))
        if not selector and raw_calldata and len(raw_calldata) >= 10:
            selector = raw_calldata[:10].lower()
        parsed_txs.append(TxHint(to=to_addr, selector=selector, calldata=raw_calldata))

    return MevEvent(
        hash=tx_hash,
        logs=parsed_logs,
        txs=parsed_txs,
        raw=data,
    )

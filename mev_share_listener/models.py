from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import time

@dataclass(slots=True)
class HintLog:
    address: str
    topics: List[str] = field(default_factory=list)
    data: Optional[str] = None

@dataclass(slots=True)
class TxHint:
    to: Optional[str] = None
    call_data: Optional[str] = None
    function_selector: Optional[str] = None
    gas_used: Optional[int] = None
    mev_gas_price: Optional[int] = None

@dataclass(slots=True)
class MevShareEvent:
    hash: str
    logs: List[HintLog] = field(default_factory=list)
    txs: List[TxHint] = field(default_factory=list)
    gas_used: Optional[int] = None
    mev_gas_price: Optional[int] = None
    raw_payload: Optional[Dict[str, Any]] = None
    received_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        # don't duplicate raw payload when serializing down to sinks
        d.pop("raw_payload", None)
        return d

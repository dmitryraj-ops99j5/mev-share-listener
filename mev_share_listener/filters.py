from typing import List, Optional, Set
from mev_share_listener.models import MevEvent


class FilterRuleSet:
    def __init__(
        self,
        addresses: Optional[List[str]] = None,
        selectors: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        require_calldata: bool = False,
    ):
        self.addresses: Set[str] = {
            self._normalize_hex(a, 42) for a in (addresses or []) if a
        }
        self.selectors: Set[str] = {
            self._normalize_selector(s) for s in (selectors or []) if s
        }
        self.topics: Set[str] = {
            self._normalize_hex(t, 66) for t in (topics or []) if t
        }
        self.require_calldata = require_calldata

    @staticmethod
    def _normalize_hex(val: str, expected_len: Optional[int] = None) -> str:
        val = val.strip().lower()
        if not val.startswith("0x"):
            val = "0x" + val
        if expected_len and len(val) > expected_len:
            return val[:expected_len]
        return val

    @staticmethod
    def _normalize_selector(sel: str) -> str:
        sel = sel.strip().lower()
        if not sel.startswith("0x"):
            sel = "0x" + sel
        return sel[:10]

    def is_empty(self) -> bool:
        return not self.addresses and not self.selectors and not self.topics and not self.require_calldata

    def check_tx_matches(self, event: MevEvent) -> bool:
        # Legacy name from first draft, keeps compatibility with early cli calls
        return self.matches(event)

    def matches(self, event: MevEvent) -> bool:
        if self.is_empty():
            return True

        # 1. Check tx-level hints
        for tx in event.txs:
            if self.require_calldata and (not tx.calldata or tx.calldata == "0x"):
                continue

            addr_match = True
            if self.addresses:
                addr_match = bool(tx.to and tx.to.lower() in self.addresses)

            selector_match = True
            if self.selectors:
                if tx.selector:
                    selector_match = tx.selector.lower() in self.selectors
                elif tx.calldata and len(tx.calldata) >= 10:
                    selector_match = tx.calldata[:10].lower() in self.selectors
                else:
                    selector_match = False

            # If both criteria specified, must both match on same tx
            if (self.addresses or self.selectors) and addr_match and selector_match:
                return True

        # 2. Check logs (addresses & topic0/topics)
        for log in event.logs:
            log_addr_match = True
            if self.addresses:
                log_addr_match = bool(log.address and log.address.lower() in self.addresses)

            topic_match = True
            if self.topics:
                # Check if any configured topic appears in the event log's topics
                topic_match = any(t in self.topics for t in log.topics)

            if (self.addresses and self.topics):
                if log_addr_match and topic_match:
                    return True
            elif self.topics and topic_match:
                return True
            elif self.addresses and not self.selectors and log_addr_match:
                return True

        return False

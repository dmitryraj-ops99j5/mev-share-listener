# mev-share-listener

Small daemon I use to ingest the Flashbots MEV-Share SSE stream, unpack hint payloads,
and filter transactions before piping them downstream.

It handles reconnects with exponential backoff and can dump raw or decoded events
to stdout, rotating JSONL files, or an existing Unix domain socket (IPC with local searchers).

## Install

```bash
pip install .
```

For development:
```bash
pip install -e ".[dev]"
pytest
```

## Usage

```bash
# dump Uniswap V2 router hints to stdout as formatted json
mev-share-listener \
  --address 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D

# filter multiple selectors and send matches over unix socket
mev-share-listener \
  --selector 0x38ed1739 \
  --selector 0x7ff36ab5 \
  --socket /tmp/mev-events.sock

# append to json lines file
mev-share-listener \
  --address 0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45 \
  --output /data/mev/v3_hints.jsonl
```

## CLI options

- `--stream-url`: MEV-share endpoint (defaults to `https://mev-share.flashbots.net`)
- `--address`: Contract address to match (can be repeated, case-insensitive)
- `--selector`: 4-byte selector hex string (can be repeated)
- `--output`: File path to append JSONL records
- `--socket`: Unix domain socket path to stream JSON events to
- `--stats-interval`: Seconds between printing throughput metrics (0 to disable)
- `--raw`: Forward raw SSE json payload without unpacking nested fields

<!-- updated: 2026-09-09 -->

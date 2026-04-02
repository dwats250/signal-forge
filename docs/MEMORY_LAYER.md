# Memory Layer (OpenWolf)

## What it is

OpenWolf is an optional memory/context layer that maintains a `.wolf/` directory
containing learned preferences (`cerebrum.md`), a file index (`anatomy.md`), and
token-usage tracking (`token-ledger.json`).

## Setup (one-time)

`external/` is gitignored — run this after cloning:

```bash
git clone https://github.com/cytostack/openwolf external/openwolf
cd external/openwolf && npm install && npm run build
```

Requires Node.js 20+ and pnpm (`npm install -g pnpm`).

## How to enable

1. Set `USE_OPENWOLF = True` in `signal_forge/config.py`.
2. Initialize the wolf directory from the project root:
   ```
   node external/openwolf/dist/bin/openwolf.js init
   ```

## Adapter location

`signal_forge/memory/openwolf_adapter.py`

Exposes:
- `store_context(text: str)` — appends text to cerebrum memory
- `retrieve_context(query: str) -> str` — returns matching lines from cerebrum

## Notes

- Feature is **OFF by default** (`USE_OPENWOLF = False`).
- Non-critical: disabling it has no effect on the core pipeline.
- OpenWolf binary lives at `external/openwolf/dist/bin/openwolf.js` (Node.js 20+).

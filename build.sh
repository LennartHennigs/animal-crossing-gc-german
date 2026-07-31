#!/bin/sh
# Rebuild the German ISO from scratch: isos/ + extracted/ -> output/.
# See CLAUDE.md for the pipeline details and the expected sha1.
set -e
cd "$(dirname "$0")"

python3 p8_final_rebuild.py    # main dialog bank + tag maps
python3 p10_extract_banks.py   # per-bank sources into build/banks/
python3 p11_rebuild_banks.py   # 10 secondary banks
python3 p14_patch_rel.py       # German menu labels into foresta.rel
python3 p15_patch_rel_items.py # German item names into foresta.rel
python3 p13_compact_pack.py    # compact arcs + rel + ISO

echo
shasum "$(python3 -c 'import config; print(config.OUT_ISO)')"

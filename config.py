"""Shared paths for the build pipeline.

Single place to edit if your ISO filenames differ. Imported by the Python
scripts; `build.sh` reads these values via `python3 -c "import config; ..."`.
"""
import os

ISO_DIR = "isos"
OUTPUT_DIR = "output"

# Source discs (you supply these — see README).
US_ISO = os.path.join(ISO_DIR, "Animal Crossing (USA).iso")
EU_ISO = os.path.join(ISO_DIR, "Animal Crossing (Europe) (En,Fr,De,Es,It).nkit.iso")

# Final rebuilt German ISO.
OUT_ISO = os.path.join(OUTPUT_DIR, "Animal Crossing (USA) [German].iso")

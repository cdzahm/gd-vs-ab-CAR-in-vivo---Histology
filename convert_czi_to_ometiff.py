"""
convert_czi_to_ometiff.py

Batch converts all .czi files in a source directory to pyramidal OME-TIFF format,
which is required for compatibility with the arm64 (Apple Silicon) build of QuPath.

Conversion uses a two-step pipeline:
  Step 1: bioformats2raw   CZI --> intermediate OME-Zarr
  Step 2: raw2ometiff      OME-Zarr --> pyramidal OME-TIFF

Files are processed sequentially (one at a time) to keep memory usage manageable.
Intermediate Zarr files are written to a temporary directory and deleted after each
successful conversion. A timestamped log file is written to the output directory.

Usage:
    python convert_czi_to_ometiff.py

See README.md for installation instructions for bioformats2raw and raw2ometiff.
"""

import os
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
from datetime import datetime


# -- CONFIGURE THESE PATHS BEFORE RUNNING ------------------------------------

# Folder containing all .czi files (all stains, all animals)
CZI_DIR = (
    "/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/"
    "2025-07-12 In vivo - ab vs gd w Aspc1/Histology/"
    "Chris Zahm 5-7-2026 COMPLETE"
)

# Where to save the converted OME-TIFF files
OUTPUT_DIR = (
    "/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/"
    "2025-07-12 In vivo - ab vs gd w Aspc1/Histology/"
    "OME-TIFF"
)

# Path to bioformats2raw executable.
# If installed via conda and on your PATH, "bioformats2raw" is enough.
# If using a standalone install, provide the full path, e.g.:
#   "/Users/cdz/tools/bioformats2raw-0.9.4/bin/bioformats2raw"
BIOFORMATS2RAW = "bioformats2raw"

# Path to raw2ometiff executable. Same rules as above.
RAW2OMETIFF = "raw2ometiff"

# -- TEST MODE ----------------------------------------------------------------
# Set to True to convert only the first file as a sanity check.
# Set to False to run the full batch.
TEST_MODE = True
# -----------------------------------------------------------------------------


def setup_logging(output_dir: str) -> str:
    """
    Configure logging to print to the terminal and write to a timestamped
    log file in the output directory. Returns the log file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(output_dir, f"conversion_log_{timestamp}.txt")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[
            logging.StreamHandler(),        # live output in terminal
            logging.FileHandler(log_path),  # persistent log file
        ],
    )
    return log_path


def find_czi_files(czi_dir: str) -> list:
    """
    Return a sorted list of all .czi files directly inside czi_dir.
    Non-recursive: all CZI files are expected to live in this one folder.
    """
    return sorted(Path(czi_dir).glob("*.czi"))


def convert_one_file(czi_path: Path, output_dir: str, temp_dir: str) -> bool:
    """
    Convert a single .czi file to a pyramidal OME-TIFF.

    Returns True on success, False if either step fails.

    The intermediate OME-Zarr is written to temp_dir and deleted after a
    successful conversion. If step 2 fails the zarr is also cleaned up so
    partial files do not accumulate.
    """
    stem = czi_path.stem                                        # filename without .czi
    zarr_path = os.path.join(temp_dir,   stem + ".zarr")       # intermediate
    tiff_path = os.path.join(output_dir, stem + ".ome.tiff")   # final output

    # Skip files that were already converted in a previous run
    if os.path.exists(tiff_path):
        logging.info(f"SKIP (already exists): {czi_path.name}")
        return True

    logging.info(f"Converting: {czi_path.name}")

    # -- Step 1: CZI -> OME-Zarr ---------------------------------------------
    logging.info(f"  [1/2] bioformats2raw -> {zarr_path}")
    result = subprocess.run(
        [BIOFORMATS2RAW, str(czi_path), zarr_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logging.error(f"  bioformats2raw FAILED for {czi_path.name}")
        logging.error(f"  stderr: {result.stderr[-800:]}")
        shutil.rmtree(zarr_path, ignore_errors=True)
        return False

    # -- Step 2: OME-Zarr -> pyramidal OME-TIFF ------------------------------
    logging.info(f"  [2/2] raw2ometiff -> {tiff_path}")
    result = subprocess.run(
        [RAW2OMETIFF, zarr_path, tiff_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logging.error(f"  raw2ometiff FAILED for {czi_path.name}")
        logging.error(f"  stderr: {result.stderr[-800:]}")
        shutil.rmtree(zarr_path, ignore_errors=True)
        return False

    # -- Cleanup: remove intermediate zarr to free disk space ----------------
    shutil.rmtree(zarr_path, ignore_errors=True)
    logging.info(f"  Done -> {czi_path.stem}.ome.tiff")
    return True


def main():
    log_path = setup_logging(OUTPUT_DIR)
    logging.info("CZI -> OME-TIFF batch conversion")
    logging.info(f"Source : {CZI_DIR}")
    logging.info(f"Output : {OUTPUT_DIR}")
    logging.info(f"Log    : {log_path}")

    czi_files = find_czi_files(CZI_DIR)
    if not czi_files:
        logging.error(f"No .czi files found in: {CZI_DIR}")
        return

    # In TEST_MODE, only process the first file
    if TEST_MODE:
        logging.info("TEST MODE: processing first file only")
        czi_files = czi_files[:1]
    else:
        logging.info(f"Found {len(czi_files)} .czi files")

    # tempfile.TemporaryDirectory() creates a temp folder and automatically
    # deletes it when the 'with' block exits, even if the script crashes.
    with tempfile.TemporaryDirectory() as temp_dir:
        logging.info(f"Temp dir (zarr intermediates): {temp_dir}")

        succeeded = []
        failed = []

        for i, czi_path in enumerate(czi_files, start=1):
            logging.info(f"\n[{i}/{len(czi_files)}] {'─' * 50}")
            success = convert_one_file(czi_path, OUTPUT_DIR, temp_dir)
            (succeeded if success else failed).append(czi_path.name)

    # -- Summary -------------------------------------------------------------
    logging.info(f"\n{'=' * 55}")
    logging.info("Conversion complete.")
    logging.info(f"  Succeeded : {len(succeeded)}")
    logging.info(f"  Failed    : {len(failed)}")
    if failed:
        logging.info("Failed files:")
        for name in failed:
            logging.info(f"    - {name}")


if __name__ == "__main__":
    main()

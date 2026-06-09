"""
convert_czi_to_ometiff_msi.py

MSI (Minnesota Supercomputing Institute) version of the CZI -> OME-TIFF
batch conversion script. Paths and tool locations are configured for MSI.

Run via SLURM using submit_conversion_msi.sh -- do not run directly on
the login node.

Conversion pipeline:
  Step 1: bioformats2raw   CZI --> intermediate OME-Zarr (on scratch)
  Step 2: raw2ometiff      OME-Zarr --> pyramidal OME-TIFF

Files are processed sequentially. Intermediate Zarr files are written to
a temp directory on scratch and deleted after each successful conversion.
"""

import os
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime


# -- PATHS --------------------------------------------------------------------

# Folder containing all .czi files
CZI_DIR = "/scratch.global/zahm0007/gdCAR Histology/Histology/Chris Zahm 5-7-2026 COMPLETE"

# Where to save the converted OME-TIFF files
OUTPUT_DIR = "/scratch.global/zahm0007/gdCAR Histology/Histology/OME-TIFF"

# Temp directory for intermediate OME-Zarr files.
# Using scratch rather than /tmp since zarr intermediates can be large.
TEMP_DIR = "/scratch.global/zahm0007/gdCAR Histology/zarr_tmp"

# Full paths to bioformats2raw and raw2ometiff executables
BIOFORMATS2RAW = "/home/zahm0007/tools/bioformats2raw-0.9.4/bin/bioformats2raw"
RAW2OMETIFF    = "/home/zahm0007/tools/raw2ometiff-0.7.1/bin/raw2ometiff"

# -- TEST MODE ----------------------------------------------------------------
# Set to True to convert only the first file as a sanity check.
# Set to False to run the full batch.
TEST_MODE = False
# -----------------------------------------------------------------------------


def setup_logging(output_dir: str) -> str:
    """
    Configure logging to print to stdout (captured by SLURM) and write to
    a timestamped log file in the output directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(output_dir, f"conversion_log_{timestamp}.txt")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path),
        ],
    )
    return log_path


def find_czi_files(czi_dir: str) -> list:
    """Return a sorted list of all .czi files directly inside czi_dir."""
    return sorted(Path(czi_dir).glob("*.czi"))


def convert_one_file(czi_path: Path, output_dir: str, temp_dir: str) -> bool:
    """
    Convert a single .czi file to a pyramidal OME-TIFF.
    Returns True on success, False if either step fails.
    """
    stem      = czi_path.stem
    zarr_path = os.path.join(temp_dir,   stem + ".zarr")
    tiff_path = os.path.join(output_dir, stem + ".ome.tiff")

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

    shutil.rmtree(zarr_path, ignore_errors=True)
    logging.info(f"  Done -> {stem}.ome.tiff")
    return True


def main():
    log_path = setup_logging(OUTPUT_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)

    logging.info("CZI -> OME-TIFF batch conversion (MSI)")
    logging.info(f"Source  : {CZI_DIR}")
    logging.info(f"Output  : {OUTPUT_DIR}")
    logging.info(f"Temp    : {TEMP_DIR}")
    logging.info(f"Log     : {log_path}")

    czi_files = find_czi_files(CZI_DIR)
    if not czi_files:
        logging.error(f"No .czi files found in: {CZI_DIR}")
        return

    if TEST_MODE:
        logging.info("TEST MODE: processing first file only")
        czi_files = czi_files[:1]
    else:
        logging.info(f"Found {len(czi_files)} .czi files")

    succeeded = []
    failed    = []

    for i, czi_path in enumerate(czi_files, start=1):
        logging.info(f"\n[{i}/{len(czi_files)}] {'─' * 50}")
        success = convert_one_file(czi_path, OUTPUT_DIR, TEMP_DIR)
        (succeeded if success else failed).append(czi_path.name)

    # Cleanup temp dir when done
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

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

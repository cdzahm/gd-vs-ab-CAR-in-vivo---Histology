# γδ vs αβ CAR T — In Vivo Histology Analysis

QuPath-based histological analysis of an orthotopic pancreatic tumor model comparing αβ and γδ CAR T cell treatment groups.

## Experimental System

- **Model**: Orthotopic AsPC-1 cells with human CAF grafted into NSG pancreas
- **Groups**: No cell control (25-256-1 to 4), αβ CAR (25-256-5 to 9), γδ CAR (25-256-10 to 14)
- **Stains**: H&E, CD3 (Hu), Cleaved Caspase-3, Pan-cytokeratin (WSCK)
- **Image format**: Zeiss CZI → converted to pyramidal OME-TIFF for QuPath arm64
- **QuPath version**: 0.7.0 (arm64 native, M3 Pro Mac)

## Repository Structure

```
scripts/
  convert_czi_to_ometiff.py   # Batch convert all CZI files to pyramidal OME-TIFF
```

## Setup

### 1. Install bioformats2raw and raw2ometiff

These are Java-based tools from the OME consortium for converting proprietary microscopy formats to open OME-TIFF.

**Option A — Conda (simplest):**
```bash
conda install -c ome bioformats2raw raw2ometiff
```

**Option B — Standalone (if conda packages unavailable):**
1. Download `bioformats2raw-x.x.x-standalone.zip` from https://github.com/glencoesoftware/bioformats2raw/releases
2. Download `raw2ometiff-x.x.x-standalone.zip` from https://github.com/glencoesoftware/raw2ometiff/releases
3. Extract both archives
4. Update `BIOFORMATS2RAW` and `RAW2OMETIFF` paths at the top of the conversion script to point to the `bin/bioformats2raw` and `bin/raw2ometiff` executables inside each extracted folder

Java is required by both tools. On an M3 Mac, use the arm64 JDK (e.g. from https://adoptium.net).

### 2. Run the conversion

Edit the paths at the top of the script, then run from terminal:
```bash
python "/path/to/scripts/convert_czi_to_ometiff.py"
```

Files are processed one at a time. A timestamped log file is written to the output directory.

### 3. Re-link images in QuPath

After conversion, open the QuPath project and use **Edit → Re-link images** to point each entry at its new `.ome.tiff` file.

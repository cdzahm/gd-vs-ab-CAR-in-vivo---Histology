"""
CAR-T Histology Project — Annotation Registration Pipeline
===========================================================
Registers annotations from WSCK slides to matched CD3, Caspase-3, and H&E slides.
Uses mosaic stitching to handle tiled .czi whole slide images.

Requirements:
    pip install SimpleITK shapely geojson aicspylibczi numpy scipy

Usage:
    /opt/anaconda3/bin/python register_annotations.py
"""

import json
import re
import copy
import numpy as np
from pathlib import Path
from aicspylibczi import CziFile
import SimpleITK as sitk
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

HISTOLOGY_DIR = Path("/Users/cdz/PPP Lab Files/Experiments/gdCAR T cells/"
                     "2025-07-12 In vivo - ab vs gd w Aspc1/Histology")

CZI_DIR     = HISTOLOGY_DIR / "Chris Zahm 5-7-2026 COMPLETE"
PROJECT_DIR = HISTOLOGY_DIR / "Qpath Project"
GEOJSON_DIR = PROJECT_DIR / "geojson_export"
OUTPUT_DIR  = PROJECT_DIR / "geojson_registered"

# Scale factor for mosaic thumbnail
# 0.01 = ~1% of full resolution, gives ~500-1300px thumbnails — good for registration
# Increase to 0.02 for better accuracy (slower), decrease to 0.005 if too slow
MOSAIC_SCALE = 0.01

# Target stains — maps GeoJSON filename suffix to actual .czi stain name
STAIN_MAP = {
    "CD3 _Hu_":  "CD3 (Hu)",
    "Caspase-3": "Caspase-3",
    "H_E":       "H&E",
}

# =============================================================================
# CZI LOADING
# =============================================================================

def load_thumbnail(czi_path: Path, scale: float = 0.01) -> np.ndarray:
    """
    Load a stitched mosaic thumbnail from a .czi whole slide image.

    CZI files from Zeiss tile scanners store tiles separately.
    read_mosaic() stitches them into a single image at the requested scale.

    Returns numpy array of shape (H, W, 3) uint8.
    """
    czi = CziFile(str(czi_path))

    if not czi.is_mosaic():
        # Fallback for non-mosaic files
        arr, _ = czi.read_image()
        arr = np.squeeze(arr)
        if arr.ndim == 3 and arr.shape[0] == 3:
            arr = np.transpose(arr, (1, 2, 0))
    else:
        # Read stitched mosaic at reduced scale
        # Returns shape (S, H, W, C) or (H, W, C)
        arr = czi.read_mosaic(C=0, scale_factor=scale)
        arr = np.squeeze(arr)

    # Ensure (H, W, 3)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=2)
    elif arr.ndim == 3 and arr.shape[0] == 3:
        arr = np.transpose(arr, (1, 2, 0))

    # Ensure uint8
    if arr.dtype != np.uint8:
        if arr.max() > 255:
            arr = (arr / arr.max() * 255).astype(np.uint8)
        else:
            arr = arr.astype(np.uint8)

    h, w = arr.shape[:2]
    print(f"      Thumbnail: {w}x{h} px")

    if w < 100 or h < 100:
        raise ValueError(f"Thumbnail too small ({w}x{h})")

    return arr


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """RGB to grayscale."""
    return (0.299*img[:,:,0] + 0.587*img[:,:,1] + 0.114*img[:,:,2]).astype(np.uint8)


# =============================================================================
# IMAGE REGISTRATION
# =============================================================================

def register_images(fixed_gray: np.ndarray,
                    moving_gray: np.ndarray) -> sitk.Transform:
    """
    Register moving image to fixed image using mutual information.
    Two-stage: translation then affine.
    Works across different IHC stains (H-DAB).
    """
    fixed  = sitk.GetImageFromArray(fixed_gray.astype(np.float32))
    moving = sitk.GetImageFromArray(moving_gray.astype(np.float32))

    def make_registration(n_iter, lr, shrink, smooth):
        reg = sitk.ImageRegistrationMethod()
        reg.SetMetricAsMattesMutualInformation(numberOfHistogramBins=32)
        reg.SetMetricSamplingStrategy(reg.RANDOM)
        reg.SetMetricSamplingPercentage(0.15)
        reg.SetInterpolator(sitk.sitkLinear)
        reg.SetOptimizerAsGradientDescent(
            learningRate=lr, numberOfIterations=n_iter,
            convergenceMinimumValue=1e-5, convergenceWindowSize=10)
        reg.SetOptimizerScalesFromPhysicalShift()
        reg.SetShrinkFactorsPerLevel(shrinkFactors=shrink)
        reg.SetSmoothingSigmasPerLevel(smoothingSigmas=smooth)
        reg.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
        return reg

    # Stage 1 — Translation
    reg1 = make_registration(150, 2.0, [4, 2, 1], [2, 1, 0])
    t_init = sitk.TranslationTransform(2)
    # Initialize by aligning centers
    fc = [s/2.0 for s in fixed.GetSize()]
    mc = [s/2.0 for s in moving.GetSize()]
    t_init.SetOffset([mc[i] - fc[i] for i in range(2)])
    reg1.SetInitialTransform(t_init, inPlace=False)
    print(f"      Stage 1 (translation)...", end=" ", flush=True)
    t1 = reg1.Execute(fixed, moving)
    metric = reg1.GetMetricValue()
    print(f"metric={metric:.4f}")

    # Quality check — if metric is poor, registration likely failed
    # Threshold: -0.4 works well for H-DAB slides (more negative = better)
    # If registration is poor, return None to trigger fallback
    if metric > -0.35:
        print(f"      WARNING: Poor registration quality (metric={metric:.4f}) — will use original annotations")
        return None

    return t1


# =============================================================================
# COORDINATE TRANSFORMATION
# =============================================================================

def get_scale_factors(wsck_czi: Path, target_czi: Path,
                      scale: float) -> tuple:
    """
    Compute the scale factors between full-resolution coordinates
    and the thumbnail used for registration.

    QuPath annotations are in full-resolution pixels of the WSCK slide.
    The registration was computed on thumbnails.
    We need to know: for each full-res pixel in WSCK, what thumbnail pixel is it?

    Returns (wsck_scale_x, wsck_scale_y, target_scale_x, target_scale_y)
    where wsck_scale = thumbnail_size / fullres_size
    """
    # Read full-res dimensions from CZI metadata
    def get_fullres_dims(czi_path):
        czi = CziFile(str(czi_path))
        shape = czi.get_dims_shape()[0]
        # Shape dict has X and Y keys
        w = shape.get('X', (0, 1600))[1]
        h = shape.get('Y', (0, 1200))[1]
        # For mosaic, total size is M*tile_size — use read_mosaic at scale=1 dims
        # Instead read at our scale and compute ratio
        thumb = czi.read_mosaic(C=0, scale_factor=scale)
        thumb = np.squeeze(thumb)
        if thumb.ndim == 3 and thumb.shape[0] == 3:
            thumb = np.transpose(thumb, (1, 2, 0))
        th, tw = thumb.shape[:2]
        return tw, th  # thumbnail width, height

    wsck_tw, wsck_th = get_fullres_dims(wsck_czi)
    tgt_tw,  tgt_th  = get_fullres_dims(target_czi)

    return wsck_tw, wsck_th, tgt_tw, tgt_th


def transform_annotations(features: list,
                           transform: sitk.Transform,
                           wsck_fullres_w: int, wsck_fullres_h: int,
                           wsck_thumb_w: int,   wsck_thumb_h: int,
                           tgt_thumb_w: int,    tgt_thumb_h: int,
                           tgt_fullres_w: int,  tgt_fullres_h: int) -> list:
    """
    Transform annotation coordinates from WSCK full-res space
    to target slide full-res space.

    Steps for each point:
    1. Scale from WSCK full-res -> WSCK thumbnail (divide by scale factor)
    2. Apply registration transform (maps WSCK thumb -> target thumb)
    3. Scale from target thumbnail -> target full-res (multiply by scale factor)
    """
    # Scale factors
    sx_wsck = wsck_thumb_w / wsck_fullres_w  # WSCK full-res -> thumbnail
    sy_wsck = wsck_thumb_h / wsck_fullres_h
    sx_tgt  = tgt_fullres_w / tgt_thumb_w   # target thumbnail -> full-res
    sy_tgt  = tgt_fullres_h / tgt_thumb_h

    def transform_point(x, y):
        # Step 1: to WSCK thumbnail space
        xt = x * sx_wsck
        yt = y * sy_wsck
        # Step 2: apply registration
        # The registration found T such that T(CD3 point) = WSCK point
        # Forward transform maps WSCK coords to CD3 coords
        try:
            xt2, yt2 = transform.TransformPoint((xt, yt))
        except Exception:
            params = transform.GetParameters()
            xt2 = xt + params[0]
            yt2 = yt + params[1]
        # Step 3: to target full-res space
        xf = xt2 * sx_tgt
        yf = yt2 * sy_tgt
        return [xf, yf]

    def transform_ring(ring):
        return [transform_point(p[0], p[1]) for p in ring]

    result = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        f = copy.deepcopy(feature)
        geom = f.get("geometry", {})
        gtype = geom.get("type", "")

        if gtype == "Polygon":
            geom["coordinates"] = [transform_ring(r)
                                    for r in geom["coordinates"]]
        elif gtype == "MultiPolygon":
            geom["coordinates"] = [[transform_ring(r) for r in poly]
                                    for poly in geom["coordinates"]]
        else:
            print(f"      WARNING: Skipping geometry type: {gtype}")
            continue
        result.append(f)
    return result


# =============================================================================
# FILE UTILITIES
# =============================================================================

def parse_geojson_name(filename: str):
    """Parse (animal_id, stain_key, scan_region) from GeoJSON filename."""
    name = filename.replace('.geojson', '')
    m = re.match(r'(\d+-\d+-\d+)\s+(.*?)\.czi\s+-\s+(ScanRegion\d+)', name)
    return (m.group(1), m.group(2), m.group(3)) if m else None


def find_czi(animal_id: str, stain_name: str) -> Path:
    """Find .czi file handling non-standard suffixes."""
    p = CZI_DIR / f"{animal_id} {stain_name}.czi"
    if p.exists():
        return p
    matches = list(CZI_DIR.glob(f"{animal_id} {stain_name}*.czi"))
    return matches[0] if matches else None


def get_mosaic_dims(czi_path: Path, scale: float):
    """Return (full_w, full_h, thumb_w, thumb_h) for a mosaic CZI."""
    czi = CziFile(str(czi_path))
    thumb = np.squeeze(czi.read_mosaic(C=0, scale_factor=scale))
    if thumb.ndim == 3 and thumb.shape[0] == 3:
        thumb = np.transpose(thumb, (1, 2, 0))
    th, tw = thumb.shape[:2]

    # Estimate full-res size from scale
    full_w = round(tw / scale)
    full_h = round(th / scale)
    return full_w, full_h, tw, th


# =============================================================================
# MAIN
# =============================================================================

def process_pair(wsck_geojson: Path, wsck_czi: Path,
                 target_geojson: Path, target_czi: Path,
                 output_path: Path) -> bool:
    """Register one slide pair and save transformed annotations."""

    print(f"\n    Target: {target_geojson.name}")

    # Load thumbnails
    try:
        print(f"      Loading WSCK thumbnail...", end=" ", flush=True)
        wsck_img = load_thumbnail(wsck_czi, MOSAIC_SCALE)
        print(f"      Loading target thumbnail...", end=" ", flush=True)
        tgt_img  = load_thumbnail(target_czi, MOSAIC_SCALE)
    except Exception as e:
        print(f"      ERROR loading images: {e}")
        return False

    # Get dimensions for coordinate scaling
    # Get actual full-res dimensions from QuPath server.json files
    # These are the authoritative pixel dimensions QuPath uses
    def get_fullres_from_project(czi_path):
        import json as _json
        czi_name = czi_path.name  # e.g. "25-256-4 WSCK.czi"
        # Search project data folders for matching server.json
        project_data = PROJECT_DIR / "data"
        for folder in project_data.iterdir():
            srv = folder / "server.json"
            if srv.exists():
                try:
                    data = _json.loads(srv.read_text())
                    uri = data.get("uri", "")
                    # Check if this server.json refers to our CZI file
                    if czi_path.stem.replace(" ", "%20") in uri or czi_path.stem in uri:
                        meta = data.get("metadata", {})
                        w = meta.get("width", 0)
                        h = meta.get("height", 0)
                        if w > 0 and h > 0:
                            return w, h
                except Exception:
                    continue
        # Fallback: estimate from thumbnail
        return round(wsck_tw / MOSAIC_SCALE), round(wsck_th / MOSAIC_SCALE)

    wsck_full_w, wsck_full_h = get_fullres_from_project(wsck_czi)
    tgt_full_w,  tgt_full_h  = get_fullres_from_project(target_czi)
    print(f"      WSCK fullres: {wsck_full_w}x{wsck_full_h}, Target fullres: {tgt_full_w}x{tgt_full_h}")

    wsck_tw, wsck_th = wsck_img.shape[1], wsck_img.shape[0]
    tgt_tw,  tgt_th  = tgt_img.shape[1],  tgt_img.shape[0]

    # Register
    wsck_gray = to_grayscale(wsck_img)
    tgt_gray  = to_grayscale(tgt_img)

    try:
        transform = register_images(wsck_gray, tgt_gray)
    except Exception as e:
        print(f"      ERROR in registration: {e}")
        transform = None

    # Load WSCK annotations
    with open(wsck_geojson) as f:
        wsck_annotations = json.load(f)

    if transform is None:
        # Fallback: use original unregistered annotations
        print(f"      Using original annotations (no registration)")
        transformed = [f for f in wsck_annotations if isinstance(f, dict)]
    else:
        transformed = transform_annotations(
            wsck_annotations, transform,
            wsck_full_w, wsck_full_h,
            wsck_tw,     wsck_th,
            tgt_tw,      tgt_th,
            tgt_full_w,  tgt_full_h
        )
    
    # Safety check — if transformed is empty, fall back to original
    if not transformed:
        print(f"      WARNING: Transform produced empty result — using original annotations")
        transformed = [f for f in wsck_annotations if isinstance(f, dict)]

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(transformed, f, indent=2)

    print(f"      Saved: {output_path.name}")
    return True


def main():
    print("=" * 60)
    print("CAR-T Histology Registration Pipeline")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    wsck_files = sorted(GEOJSON_DIR.glob("*WSCK*.geojson"))
    print(f"\nFound {len(wsck_files)} WSCK annotation files\n")

    success = fail = skip = 0

    for wsck_path in wsck_files:
        parsed = parse_geojson_name(wsck_path.name)
        if not parsed:
            print(f"WARNING: Could not parse {wsck_path.name}")
            continue

        animal_id, wsck_stain_key, scan_region = parsed
        print(f"\n{'='*40}")
        print(f"Animal: {animal_id} | {scan_region}")

        # Find WSCK .czi
        wsck_czi = find_czi(animal_id, "WSCK")
        if wsck_czi is None:
            wsck_czi = CZI_DIR / f"{animal_id} {wsck_stain_key}.czi"
        if not wsck_czi or not wsck_czi.exists():
            print(f"  ERROR: WSCK .czi not found for {animal_id}")
            fail += 1
            continue

        print(f"  WSCK: {wsck_czi.name}")

        for target_key, target_stain in STAIN_MAP.items():
            # Find target GeoJSON
            target_geojson_name = (f"{animal_id} {target_key}.czi"
                                   f" - {scan_region}.geojson")
            target_geojson = GEOJSON_DIR / target_geojson_name

            if not target_geojson.exists():
                matches = list(GEOJSON_DIR.glob(
                    f"{animal_id}*{target_key}*.czi - {scan_region}.geojson"))
                if matches:
                    target_geojson = matches[0]
                else:
                    print(f"  SKIP: {target_geojson_name}")
                    skip += 1
                    continue

            # Find target .czi
            target_czi = find_czi(animal_id, target_stain)
            if not target_czi:
                print(f"  ERROR: {target_stain} .czi not found for {animal_id}")
                fail += 1
                continue

            output_path = OUTPUT_DIR / target_geojson.name

            ok = process_pair(wsck_path, wsck_czi,
                              target_geojson, target_czi,
                              output_path)
            success += ok
            fail    += not ok

    print(f"\n{'='*60}")
    print(f"COMPLETE — Success: {success} | Failed: {fail} | Skipped: {skip}")
    print(f"Registered GeoJSON → {OUTPUT_DIR}")
    print(f"Next: run import_registered_annotations.groovy in QuPath")


if __name__ == "__main__":
    main()

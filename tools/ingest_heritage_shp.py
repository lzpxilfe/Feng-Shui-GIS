#!/usr/bin/env python3
"""Convert Korea Heritage Service shapefiles into UTF-8 GeoPackages.

National heritage shapefiles arrive CP949-encoded, and often without the .cpg
sidecar that would declare it. GDAL then guesses, Korean attribute values come
through as mojibake, and the damage is silent — the layer opens, the geometry
is fine, and only the names are wrong.

This decides the encoding explicitly, records what it decided and why, and
writes a manifest alongside the output so the provenance of a dataset can be
audited later rather than remembered.

Usage:
    python3 tools/ingest_heritage_shp.py SRC_DIR OUT_DIR [--t-srs EPSG:5186]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# Shapefile DBF text starts after the header; scanning the whole file is fine
# for the sizes involved and avoids parsing the header format.
_HANGUL_RANGES = ((0xAC00, 0xD7A3), (0x3130, 0x318F))
# EUC-KR is deliberately absent: CP949 is its superset and decodes anything
# EUC-KR does, plus the extended Hangul that appears in some place names.
# Keeping both only produces ties between two encodings that read the same.
CANDIDATE_ENCODINGS = ("utf-8", "cp949")

QGIS_APP = "/Applications/QGIS.app"


def hangul_ratio(text):
    """Share of characters that are Hangul, used to score a decode attempt."""
    if not text:
        return 0.0
    hits = sum(
        1
        for char in text
        if any(low <= ord(char) <= high for low, high in _HANGUL_RANGES)
    )
    return hits / len(text)


def detect_encoding(dbf_bytes, cpg_text=None):
    """Decide the DBF encoding, preferring an explicit .cpg declaration.

    Returns ``(encoding, reason, confidence)``. A file that decodes under
    several encodings is resolved by which one yields actual Hangul: mojibake
    decodes cleanly as latin-1 or cp949 too, it just produces nonsense.
    """
    declared = (cpg_text or "").strip().upper().replace("-", "").replace("_", "")
    if declared:
        if declared in ("UTF8", "UTF"):
            return "utf-8", "declared in .cpg", "declared"
        if declared in ("CP949", "MS949", "EUCKR", "KSC5601", "ANSI949"):
            return "cp949", "declared in .cpg", "declared"

    # A DBF carries a binary header, so strict decoding fails under every
    # candidate. Decode leniently instead and score: the right encoding is the
    # one that yields Hangul without scattering replacement characters.
    scored = []
    for encoding in CANDIDATE_ENCODINGS:
        text = dbf_bytes.decode(encoding, errors="replace")
        replacement_ratio = text.count("\ufffd") / max(1, len(text))
        hangul = hangul_ratio(text)
        scored.append((hangul - replacement_ratio, hangul, encoding))
    scored.sort(reverse=True)
    best_score, best_hangul, best_encoding = scored[0]

    if best_hangul <= 0.0:
        # No candidate produced Hangul. Either the attributes are ASCII-only,
        # where the choice does not matter, or the file is not what we think.
        return best_encoding, "no Hangul found; encoding choice is moot", "weak"
    runner_up = scored[1][0] if len(scored) > 1 else None
    if runner_up is not None and (best_score - runner_up) < 0.005:
        return (
            best_encoding,
            f"ambiguous: {best_encoding} scored {best_score:.3f} vs "
            f"{scored[1][2]} {runner_up:.3f}",
            "ambiguous",
        )
    return (
        best_encoding,
        f"hangul {best_hangul:.3f} minus replacements, score {best_score:.3f}",
        "inferred",
    )


def gdal_env():
    """Environment for the QGIS-bundled GDAL, which needs its data paths set."""
    env = dict(os.environ)
    macos_bin = os.path.join(QGIS_APP, "Contents", "MacOS")
    if os.path.isdir(macos_bin):
        env["PATH"] = macos_bin + os.pathsep + env.get("PATH", "")
        resources = os.path.join(QGIS_APP, "Contents", "Resources")
        proj_dir = os.path.join(resources, "qgis", "proj")
        if os.path.isdir(proj_dir):
            env["PROJ_DATA"] = proj_dir
            env["PROJ_LIB"] = proj_dir
        gdal_dir = os.path.join(resources, "gdal")
        if os.path.isdir(gdal_dir):
            env["GDAL_DATA"] = gdal_dir
    return env


def _read_sidecar(shp_path, extension):
    path = os.path.splitext(shp_path)[0] + extension
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def find_shapefiles(src_dir):
    found = []
    for root, _dirs, files in os.walk(src_dir):
        for name in sorted(files):
            if name.lower().endswith(".shp"):
                found.append(os.path.join(root, name))
    return found


def convert(shp_path, out_dir, target_srs=None, env=None):
    """Convert one shapefile, returning its manifest record."""
    env = env or gdal_env()
    layer_name = os.path.splitext(os.path.basename(shp_path))[0]
    out_path = os.path.join(out_dir, f"{layer_name}.gpkg")

    with open(os.path.splitext(shp_path)[0] + ".dbf", "rb") as handle:
        dbf_bytes = handle.read()
    cpg_text = _read_sidecar(shp_path, ".cpg")
    encoding, reason, confidence = detect_encoding(dbf_bytes, cpg_text)

    record = {
        "source": os.path.abspath(shp_path),
        "source_bytes": os.path.getsize(shp_path),
        "layer": layer_name,
        "declared_cpg": (cpg_text or "").strip() or None,
        "encoding": encoding,
        "encoding_reason": reason,
        "encoding_confidence": confidence,
        "source_prj": (_read_sidecar(shp_path, ".prj") or "").strip()[:200] or None,
        "output": os.path.abspath(out_path),
        "target_srs": target_srs,
    }
    if encoding is None:
        record["status"] = "failed"
        record["error"] = "encoding could not be determined"
        return record

    command = ["ogr2ogr", "-f", "GPKG", out_path, shp_path, "-nln", layer_name]
    if target_srs:
        command += ["-t_srs", target_srs]
    run_env = dict(env)
    # GDAL wants the shapefile encoding named here; the .cpg alone is not
    # enough when it is missing or wrong.
    run_env["SHAPE_ENCODING"] = "CP949" if encoding == "cp949" else encoding.upper()

    if os.path.exists(out_path):
        os.remove(out_path)
    result = subprocess.run(
        command, env=run_env, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        record["status"] = "failed"
        record["error"] = (result.stderr or "").strip()[-400:]
        return record

    record["status"] = "ok"
    record.update(_describe(out_path, layer_name, env))
    return record


def _describe(gpkg_path, layer_name, env):
    result = subprocess.run(
        ["ogrinfo", "-so", "-al", gpkg_path, layer_name],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    info = {"feature_count": None, "geometry": None, "extent": None, "fields": []}
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("Feature Count:"):
            try:
                info["feature_count"] = int(stripped.split(":", 1)[1])
            except ValueError:
                pass
        elif stripped.startswith("Geometry:"):
            info["geometry"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Extent:"):
            info["extent"] = stripped.split(":", 1)[1].strip()
        elif "(" in stripped and stripped.endswith(")") and ":" in stripped:
            field = stripped.split(":", 1)[0].strip()
            if field and field not in info["fields"]:
                info["fields"].append(field)
    return info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src_dir", help="directory containing .shp files")
    parser.add_argument("out_dir", help="directory for GeoPackage output")
    parser.add_argument(
        "--t-srs",
        default=None,
        help="target CRS, e.g. EPSG:5186 (Korea 2000 Central Belt)",
    )
    args = parser.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    env = gdal_env()
    shapefiles = find_shapefiles(args.src_dir)
    if not shapefiles:
        print(f"No .shp files found under {args.src_dir}", file=sys.stderr)
        return 1

    records = [convert(path, args.out_dir, args.t_srs, env) for path in shapefiles]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_dir": os.path.abspath(args.src_dir),
        "target_srs": args.t_srs,
        "layer_count": len(records),
        "layers": records,
    }
    manifest_path = os.path.join(args.out_dir, "ingest_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    for record in records:
        status = record["status"]
        if status == "ok":
            print(
                f"[ok]   {record['layer']}: {record['feature_count']} features, "
                f"{record['geometry']}, encoding={record['encoding']} "
                f"({record['encoding_confidence']})"
            )
        else:
            print(f"[FAIL] {record['layer']}: {record.get('error', '')}")
    print(f"\nmanifest: {manifest_path}")
    return 0 if all(r["status"] == "ok" for r in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())

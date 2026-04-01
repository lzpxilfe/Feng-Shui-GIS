# -*- coding: utf-8 -*-
"""Helpers for packaging support bundles without embedding raw source datasets."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


class SupportBundleWriter:
    @staticmethod
    def _json_text(payload):
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def write_bundle(cls, output_path, *, payload_entries=None, file_entries=None):
        bundle_path = Path(output_path)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        payload_entries = payload_entries or {}
        file_entries = file_entries or {}
        with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as handle:
            for archive_name, payload in payload_entries.items():
                if not archive_name:
                    continue
                handle.writestr(str(archive_name), cls._json_text(payload))
            for archive_name, path_text in file_entries.items():
                if not archive_name or not path_text:
                    continue
                path = Path(path_text)
                if not path.is_file():
                    continue
                handle.write(path, arcname=str(archive_name))
        return str(bundle_path)

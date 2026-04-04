"""Support bundle zip writer adapter."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable


class SupportBundleWriter:
    """Build a support bundle zip for issue reporting and reproducibility."""

    @staticmethod
    def write_bundle(
        bundle_path: str | os.PathLike[str],
        *,
        payload_entries: Dict[str, Any],
        file_entries: Dict[str, str],
    ) -> None:
        bundle_path = Path(bundle_path)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)

        def _payload_items() -> Iterable[tuple[str, str]]:
            for zip_name, payload in payload_entries.items():
                content = json.dumps(payload, ensure_ascii=False, indent=2)
                yield str(zip_name), content

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            for zip_name, content in _payload_items():
                handle.writestr(zip_name, content)
            for zip_name, source_path in file_entries.items():
                source = Path(source_path)
                if source.is_file():
                    handle.write(source, arcname=zip_name)

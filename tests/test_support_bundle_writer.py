import json
import pathlib
import tempfile
import unittest
import zipfile

from feng_shui_gis.reporting.support_bundle_writer import SupportBundleWriter


class SupportBundleWriterTests(unittest.TestCase):
    def test_bundle_contains_payload_and_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            metadata_path = root / "metadata.txt"
            metadata_path.write_text("name=Feng Shui GIS\n", encoding="utf-8")
            bundle_path = root / "support_bundle.zip"

            SupportBundleWriter.write_bundle(
                bundle_path,
                payload_entries={
                    "bundle_manifest.json": {"bundle": True},
                    "recent_errors.json": [{"context": "test"}],
                },
                file_entries={
                    "plugin/metadata.txt": str(metadata_path),
                },
            )

            self.assertTrue(bundle_path.is_file())
            with zipfile.ZipFile(bundle_path, "r") as handle:
                names = set(handle.namelist())
                self.assertIn("bundle_manifest.json", names)
                self.assertIn("recent_errors.json", names)
                self.assertIn("plugin/metadata.txt", names)
                manifest = json.loads(handle.read("bundle_manifest.json").decode("utf-8"))
                self.assertTrue(manifest["bundle"])


if __name__ == "__main__":
    unittest.main()

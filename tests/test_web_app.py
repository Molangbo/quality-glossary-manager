import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import web_app


class SendAnkiFileTests(unittest.TestCase):
    def test_download_regenerates_existing_export(self):
        with TemporaryDirectory() as temp_dir:
            export_path = Path(temp_dir) / "anki_cards.csv"
            export_path.write_bytes(b"stale")

            def regenerate_export():
                export_path.write_bytes(b"fresh")
                return export_path, 1

            handler = object.__new__(web_app.GlossaryHandler)
            handler.wfile = io.BytesIO()
            handler.send_response = lambda status: None
            handler.send_header = lambda name, value: None
            handler.end_headers = lambda: None

            with (
                patch.object(web_app, "ANKI_EXPORT_PATH", export_path),
                patch.object(
                    web_app,
                    "export_anki_cards_to_file",
                    side_effect=regenerate_export,
                ) as export_mock,
            ):
                handler.send_anki_file()

            export_mock.assert_called_once_with()
            self.assertEqual(handler.wfile.getvalue(), b"fresh")


if __name__ == "__main__":
    unittest.main()

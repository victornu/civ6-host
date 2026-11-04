"""The local source review refuses accidental private data and changed bytes."""
from pathlib import Path
import tempfile
import unittest

from review_source_payload import _source_bytes


class SourceReviewTests(unittest.TestCase):
    def test_text_source_screen_rejects_binary_credentials_and_personal_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'source.py'
            authored = b'print("hello")\n'
            source.write_bytes(authored)
            self.assertEqual(_source_bytes(root, source.name), authored)
            rejected = (
                b'chunk=\x00',
                b'-----BEGIN ' + b'PRIVATE KEY-----',
                b'path=r"D:\\Users\\local-user\\settings"',
                b'path="/home/local-user/settings"',
            )
            for raw in rejected:
                with self.subTest(raw=raw):
                    source.write_bytes(raw)
                    with self.assertRaisesRegex(ValueError, 'credential marker or personal home path'):
                        _source_bytes(root, source.name)


if __name__ == '__main__':
    unittest.main()

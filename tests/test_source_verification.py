import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import source_verification as source


class SourceVerificationTests(unittest.TestCase):
    def test_digest_only_json_is_bounded_and_rejects_modified_bytes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.json'
            initial = b'{"pinned": true}'
            expected = hashlib.sha256(initial).hexdigest()
            path.write_bytes(initial)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file allocation')):
                source.verify_pinned_json_bytes(path, expected)
                path.write_bytes(b'{"pinned": null}')
                with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch'):
                    source.verify_pinned_json_bytes(path, expected)
                with path.open('wb') as stream:
                    stream.truncate(8 * 1024 * 1024 + 1)
                with self.assertRaisesRegex(ValueError, 'oversized'):
                    source.verify_pinned_json_bytes(path, expected)

    def test_static_digest_is_reused_only_while_file_identity_matches(self):
        with TemporaryDirectory() as directory, patch.object(
                source.hashlib, 'file_digest', wraps=hashlib.file_digest) as digest:
            path = Path(directory) / 'proof'
            path.write_bytes(b'original')
            with source.verification_scope():
                old = source.file_sha256(path)
                self.assertEqual(source.file_sha256(path), old)
                self.assertEqual(digest.call_count, 1)
                path.write_bytes(b'changed bytes')
                new = source.file_sha256(path)
                self.assertNotEqual(new, old)
                self.assertEqual(source.file_sha256(path), new)
                self.assertEqual(digest.call_count, 2)
            self.assertEqual(source.file_sha256(path), new)
            self.assertEqual(digest.call_count, 3)

    def test_pinned_json_is_scoped_to_hash_and_identity(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.json'
            path.write_text('{}', encoding='utf-8')
            load = Mock(side_effect=lambda path, _: path.read_text(encoding='utf-8'))
            with source.verification_scope():
                self.assertEqual(source.pinned_json(path, 'a', load), '{}')
                self.assertEqual(source.pinned_json(path, 'a', load), '{}')
                self.assertEqual(load.call_count, 1)
                self.assertEqual(source.pinned_json(path, 'b', load), '{}')
                self.assertEqual(load.call_count, 2)
                path.write_text('{"changed": true}', encoding='utf-8')
                self.assertEqual(source.pinned_json(path, 'a', load), '{"changed": true}')
                self.assertEqual(load.call_count, 3)
            source.pinned_json(path, 'a', load)
            self.assertEqual(load.call_count, 4)

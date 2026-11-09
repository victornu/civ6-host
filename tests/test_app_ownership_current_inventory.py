"""Source-backed XP2 inventory transition checks; no native or entitlement calls."""

import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.native import native_app_ownership as ownership
from civ6_host.runtime.native import native_host_capability_status as abi
from civ6_host.runtime.native.native_session_resume import plain


PROFILE_ID = 'xp2-gamecore-current-092abfbb'
STATUS_AST_SHA256 = 'd1f9a2b7aab7d2f3866772bbd47660453d72808e0d2ec9f7937053baaae98358'


def _selected_profile():
    return select(PROFILE_ID, core_path=known_path(PROFILE_ID))


def _inventory_proofs():
    host = abi.verify_source()
    producer = ownership.verify_producer_source()
    return host, producer, host['catalogue_evidence']['fixed_files']


class AppOwnershipCurrentInventoryTests(unittest.TestCase):
    def test_exact_current_xp2_inventory_is_admitted_and_legacy_stays_strict(self):
        profile = _selected_profile()
        host, producer, original = _inventory_proofs()
        backend = NS(core=NS(_civ6_host_execution_image=profile))
        root = Path(profile.path).parents[4]

        snapshot = ownership._read_current_xp2_fixed_inventory(
            root, original, backend, host, producer)
        self.assertEqual(len(snapshot), 65)
        self.assertEqual(sum(row['present'] for row in snapshot), 35)
        self.assertEqual(snapshot[0]['path'], original[0]['installed_relative_path'])
        with self.assertRaisesRegex(ValueError, 'Ownership input changed: Base/Assets/Civ6_9ae5ab5ed97dd296.xml'):
            ownership._read_current_xp2_fixed_inventory(
                root, original, NS(core=NS()), host, producer)

    def test_changed_third_xml_refuses_and_private_receipt_property_tampering_refuses(self):
        profile = _selected_profile()
        host, producer, original = _inventory_proofs()
        backend = NS(core=NS(_civ6_host_execution_image=profile))
        receipt = ownership.load_pinned_json(
            abi.ROOT / ownership.CURRENT_XP2_INVENTORY_PATH,
            ownership.CURRENT_XP2_INVENTORY_SHA256)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installed = Path(profile.path).parents[4]
            for row in receipt['current_inventory']:
                if row['present']:
                    target = root / row['installed_relative_path']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(installed / row['installed_relative_path'], target)
            third = root / 'Base/Assets/Civ6_904144542bc1d3af.xml'
            raw = bytearray(third.read_bytes())
            raw[0] ^= 1
            third.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'Ownership input changed: Base/Assets/Civ6_904144542bc1d3af.xml'):
                ownership._read_current_xp2_fixed_inventory(
                    root, original, backend, host, producer)

        tampered = deepcopy(plain(receipt))
        tampered['current_inventory'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'unchanged inventory input differs'):
            ownership._validate_current_xp2_inventory_receipt(
                tampered, original, ownership.CURRENT_XP2_IMAGE_IDENTITY, host, producer)

    def test_foreign_reference_profile_is_refused(self):
        profile = _selected_profile()
        foreign = profile.__class__(**{
            **profile.__dict__,
            'reference_core_sha256': 'f' * 64,
        })
        backend = NS(core=NS(_civ6_host_execution_image=foreign))
        with self.assertRaisesRegex(ValueError, 'registered immutable identity'):
            ownership._execution_image_for_ownership(backend)

    def test_status_method_ast_is_unchanged(self):
        source = Path(ownership.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        cls = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == 'ClosedBaseOwnership')
        method = next(node for node in cls.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'status')
        digest = hashlib.sha256(ast.dump(method, include_attributes=False).encode()).hexdigest()
        self.assertEqual(digest, STATUS_AST_SHA256)


if __name__ == '__main__':
    unittest.main()

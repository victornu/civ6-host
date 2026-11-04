from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'civ6-rl-lab'
LAB_SOURCE = LAB / 'civ6rl' / 'native_found_city_event.py'
HISTORIC_SOURCE_SHA256 = 'f17973355287e55ecef67ba699b222bac56caa1839904f5ae498785d013dcddb'


def _hook():
    path = Path(__file__).resolve().parents[1] / 'tools' / 'extraction_found_unit_event.py'
    spec = importlib.util.spec_from_file_location('extraction_found_unit_event', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_imported_module():
    source = LAB_SOURCE.read_text(encoding='utf-8')
    transformed = _hook().transform(source)
    name = 'civ6_host.runtime.native.native_found_city_event'
    module = types.ModuleType(name)
    module.__file__ = str(LAB_SOURCE)
    module.__package__ = 'civ6_host.runtime.native'
    exec(compile(transformed, str(LAB_SOURCE), 'exec'), module.__dict__)
    return module, transformed


class FoundUnitExtractionTests(unittest.TestCase):
    def test_found_unit_extraction_preserves_historic_source_and_selects_profiles_explicitly(self):
        source = LAB_SOURCE.read_text(encoding='utf-8')
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), HISTORIC_SOURCE_SHA256)
        transformed = _hook().transform(source)
        tree = ast.parse(transformed)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

        query = functions['query_unit_parameters']
        query_args = {arg.arg: default for arg, default in zip(query.args.kwonlyargs, query.args.kw_defaults)}
        self.assertEqual(ast.unparse(query_args['core_sha256']), 'PINNED_CORE_SHA256')
        query_text = ast.unparse(query)
        self.assertIn('abi = query_abi(core_sha256)', query_text)
        self.assertIn('TABLES = abi.tables', query_text)
        self.assertIn('abi.constants', query_text)
        self.assertIn('abi.code_pins', query_text)
        self.assertIn('abi.inner_vtable_rva', query_text)

        contract = functions['unit_query_contract']
        contract_args = {arg.arg: default for arg, default in zip(contract.args.kwonlyargs, contract.args.kw_defaults)}
        self.assertEqual(ast.unparse(contract_args['core_sha256']), 'PINNED_CORE_SHA256')
        contract_text = ast.unparse(contract)
        self.assertIn('abi = query_abi(core_sha256)', contract_text)
        self.assertIn("abi.tables['unit']", contract_text)
        self.assertIn('abi.core_sha256', contract_text)

        verifier_text = ast.unparse(functions['verify_selector_source'])
        self.assertIn("source['images']['exe_sha256']", verifier_text)
        self.assertNotIn("source['images'] !=", verifier_text)

    def test_exact_hook_output_imports_and_keeps_callable_defaults_bound(self):
        module, _ = render_imported_module()
        self.assertEqual(module.query_unit_parameters.__kwdefaults__['core_sha256'],
                         module.PINNED_CORE_SHA256)
        self.assertEqual(module.unit_query_contract.__kwdefaults__['core_sha256'],
                         module.PINNED_CORE_SHA256)

"""Pinned official default handler; special deal/demand handlers stay separate."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib, re
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_diplomacy_default.py')))).resolve().parents[1]
PROOF_SHA256 = '7e8623c3d8568e275c82dbd88ff3dd70cca4003997c0f72c22e29c7869c0059e'
PROOF_PATH = ROOT / 'evidence/native-diplomacy-default' / (PROOF_SHA256 + '.json')
CUSTOM_HANDLERS = ('MAKE_DEAL', 'MAKE_DEMAND')

def verify_source():
    p = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    if p['schema'] != 'civ6rl.diplomacy_default950.static.v1' or tuple(p['denied_custom_handlers']) != CUSTOM_HANDLERS or p['contract']['opaque_blob_key'] != 2684726792 or (p['contract']['absent_blob_preserved_as_null'] is not True) or (not p['validation']['all_captured_instructions_match_pinned_pe']):
        raise ValueError('Default diplomacy handler/optional payload source changed')
    return p

def validate_handler(name, subtype):
    verify_source()
    if any((type(v) is not str or re.fullmatch('[A-Z0-9_]+', v) is None for v in (name, subtype))):
        raise ValueError('Invalid native statement names')
    if name in CUSTOM_HANDLERS:
        raise ValueError('Special native statement handler is not implemented')

def handler_source():
    from civ6_host.runtime.native.native_diplomacy_choices import official_source
    from civ6_host.runtime.native.native_diplomacy_choices import VIEW_SHA
    proof = verify_source()
    original = official_source('DiplomacyActionView.lua', VIEW_SHA)
    pieces = []
    for name in ('GetStatementHandler', 'SetDefaultHandlers'):
        row = proof['functions'][name]
        raw = original[row['byte_offset']:row['byte_offset'] + row['bytes']]
        if hashlib.sha256(raw).hexdigest() != row['sha256'] or raw.decode('utf8') != row['source']:
            raise ValueError('Official default handler extraction changed')
        pieces.append(raw)
    return b'local StatementHandlers={}\nlocal DefaultHandlers\n' + b'\n'.join(pieces) + b'\nSetDefaultHandlers("DEFAULT"); DefaultHandlers=StatementHandlers["DEFAULT"];\n'

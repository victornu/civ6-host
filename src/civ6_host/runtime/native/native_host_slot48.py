"""Identity guard for the existing GameCore lock's host+48 extension."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = 'b19c7cf819baed2b9c7346e80b257aa5dc2144e1876ee60e7dcbda426cc4b20e'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_host_slot48.py')))).resolve().parents[1] / 'evidence/native-host-slot48' / f'{PINNED_EVIDENCE_SHA256}.json'

def verify_source_evidence():
    """Verify static identity; this never chooses a lock result or invokes native code."""
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_host_slot48.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['slots']['0x48'] != {'target': '0x1401ca910', 'raw_hex': '10a91c4001000000'}) or (proof['captures']['try_acquire']['code_sha256'] != '51287d2c8eb2d2d9bddd9675e9b797c059d869a8fad8e39236e32d2108d502fd') or (proof['imports']['0x140f96730']['name'] != 'TryEnterCriticalSection') or (proof['imports']['0x140f96988']['name'] != 'GetCurrentThreadId'):
        raise RuntimeError('Pinned host+48 GameCore lock source identity changed')
    return proof

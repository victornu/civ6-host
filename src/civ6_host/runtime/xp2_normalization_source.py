"""Pinned XP2 proof for one provider representation change; no native calls."""
from __future__ import annotations

import hashlib

from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-provider-normalization/source-profile-v2.json',
          '71a19c2e32ad3cc864f33e50ff82230628475b28c340b27abcf1e76308180350')
_BODIES = {
    'empty_string_setter': ('0x9a6e40', '243b799dd9998593e48d36363e43b676b7548dd1f6e40c842d5714acd65453fc'),
    'inline_dword_reader': ('0x3ee8b0', 'fc24448d2f1302a2a0bc824b15eab9a7a13861d7de9d5120529495cb71dfa029'),
    'provider_entry_writer_200': ('0x9a9950', 'ddf64ff273c4ea481eccf0c59b94be442b1f58ed88cba851d7b72f7793ecea22'),
    'provider_field_reader': ('0x9a0e50', 'ceafd08c6d2d5c9587678c2fe2a6fbe0c5e51eb7c5c68f45f722e709ab064075'),
    'provider_reader_dispatch_1e8': ('0x9a9a40', '4a81868f9cd470d3a2f562a072e0734fd038a9f71f9218cb8e18e461981db192'),
    'provider_writer_dispatch_1f0': ('0x99fb50', 'e484b32f8e3bf8c1f231875cd9276244776180287c59925dda331046874a0634'),
    'typed_value_setter_b0': ('0x9a0890', '518e6f279f961f07e448464454f5fcb5450382a8575995d2307bd2ed824401b4'),
    'variant_value_reader': ('0x9a44f0', '1a21778569510a27852ead52eb9cde62fe3428abd9a7ebffcbe5cf7d7fef9b25'),
    'variant_writer_forwarder': ('0x99fae0', 'a16fdb8bd9e39364212b4474e17b8955b1c0e958cc94b3ff89e2c6b57f5df0bb'),
    'variant_writer_payload': ('0x9a4180', 'ba06ef4ecc4a7838ad015ab91f7b1c65b289cee66194d41638e4e4940a4a4642'),
}


def _check_fragment(fragment):
    raw = bytes.fromhex(fragment['raw_hex'])
    if len(raw) != fragment['length']:
        raise ValueError('XP2 normalization fragment length differs')
    offset = int(fragment['start_rva'], 16)
    decoded = bytearray()
    for instruction in fragment['instructions']:
        if int(instruction['rva'], 16) != offset:
            raise ValueError('XP2 normalization source has an instruction gap')
        code = bytes.fromhex(instruction['bytes'])
        decoded.extend(code)
        offset += len(code)
    if bytes(decoded) != raw:
        raise ValueError('XP2 normalization decoded bytes differ')
    return raw


def verify_source():
    proof = _source(SOURCE)
    contract = proof['contract']
    exact = dict(tag=5, extra_word=0, flags=0x20000000, size=1, inline_value=0)
    if (proof['schema'] != 'civ6-host.xp2-provider-empty-string-normalization-source.v2'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or proof['native_execution'] is not False
            or proof['conclusion']['status'] != 'source_proven_for_xp2'
            or contract['input_exact'] != exact
            or contract['output_exact'] != dict(exact, flags=0)
            or proof['validation']['all_captured_instruction_bytes_match_pinned_pe'] is not True):
        raise ValueError('XP2 normalization source contract differs')
    for name, (rva, sha) in _BODIES.items():
        body = proof['bodies'][name]
        raw = b''.join(_check_fragment(f) for f in body['fragments'])
        if (body['entry_rva'] != rva or body['raw_sha256'] != sha
                or hashlib.sha256(raw).hexdigest() != sha
                or body['boundary_method'] != 'complete-runtime-function-chained-unwind-root-v2'):
            raise ValueError('XP2 normalization function differs: ' + name)
    iterator = proof['bodies']['provider_next_node_helper']
    raw = _check_fragment(iterator)
    if (iterator['start_rva'] != '0x994d90' or iterator['length'] != 68
            or iterator['end_rva_exclusive'] != '0x994dd4'
            or hashlib.sha256(raw).hexdigest() != 'a0978695096493b0fe7886fe4e1facb0122606de8436fe80dfe2736ccfe34347'
            or iterator['complete_control_flow'] is not True):
        raise ValueError('XP2 provider iterator omits a reachable branch')
    for reference in proof['references'].values():
        path = resolve_path(resource_root()/reference['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError('XP2 normalization source dependency differs: ' + str(path))
    return proof


def source_dependencies():
    from .native.native_checkpoint_configuration_normalization import (
        PROVIDER_PROOF_SHA256, verify_source_evidence,
    )
    proof = verify_source()
    # The shared stream comparator reads this parent even for the XP2 wire.
    verify_source_evidence()
    references = [dict(path=SOURCE[0], sha256=SOURCE[1]), *proof['references'].values()]
    references.append(dict(
        path=f'evidence/native-checkpoint-configuration-stream-v3/{PROVIDER_PROOF_SHA256}.json',
        sha256=PROVIDER_PROOF_SHA256,
    ))
    return {str(resolve_path(resource_root()/ref['path'])):ref['sha256'] for ref in references}

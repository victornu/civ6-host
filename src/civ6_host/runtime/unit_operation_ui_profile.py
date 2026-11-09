"""Proposed source profile for the original XP1 UI unit-operation callbacks.

No operation is emulated or invoked here. Native UI functions retain argument
conversion, legality and serialization; the shared transport owns delivery.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from .configuration_profiles import XP2_CORE_SHA256

CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
SOURCE = ('work/host-extensions/xp1-unit-request-static/unit-request-source-v1.json',
          '00cbb7e10a53c2d7c1ad784a6ec7ac24e5738248a10100dd4392c750ca6df628')
CALLBACKS = {'CanStartOperation': 0x5DBE80, 'RequestOperation': 0x5DEC40}


def source(root: Path | None = None, *, core_sha256=CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_action_transport_source import source as selected
        return selected(root)
    if core_sha256 != CORE_SHA256:
        raise ValueError('Unknown unit-operation source engine')
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root = resource_root()
    path = Path(root) / SOURCE[0]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE[1]:
        raise ValueError('XP1 unit-operation UI source changed')
    proof = json.loads(raw)
    if (proof['schema'] != 'civ6_host.xp1_unit_request.source.v1'
            or proof['image']['sha256'] != CORE_SHA256
            or proof['api']['namespace'] != 'UnitManager'
            or any(int(proof['targets'][name], 16) != address for name, address in CALLBACKS.items())
            or proof['api']['RequestOperation']['lua_return_count'] != 0
            or proof['api']['RequestOperation']['host_send_slot'] != '0x70'):
        raise ValueError('Unexpected XP1 UI unit-operation profile')
    return proof


def source_dependencies(root: Path | None = None, *, core_sha256=CORE_SHA256, execution_image=None):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_action_transport_source import source_dependencies as selected
        return selected(root, execution_image=execution_image)
    if core_sha256 != CORE_SHA256:
        raise ValueError('Unknown unit-operation source engine')
    if execution_image is not None:
        raise ValueError('XP1 unit-operation source does not accept an XP2 execution image')
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root = resource_root()
    proof = source(root)
    from .resource_resolution import resolve_path
    return {str(Path(root) / SOURCE[0]): SOURCE[1],
            str(resolve_path(Path(proof['parent']['path']))): proof['parent']['sha256'],
            str(resolve_path(Path(proof['image']['path']))): CORE_SHA256}


def instruction_spans(proof):
    """Merge exact captured instructions; never infer bytes between fragments."""
    byte_map = {}
    for body in proof['functions'].values():
        rows = body.get('instructions') or [r for f in body['fragments'] for r in f['instructions']]
        for row in rows:
            address = int(row['va'], 16) - 0x180000000
            for offset, value in enumerate(bytes.fromhex(row['bytes'])):
                location = address + offset
                if location in byte_map and byte_map[location] != value:
                    raise ValueError('Conflicting source instruction bytes')
                byte_map[location] = value
    spans = []
    start = previous = None
    data = bytearray()
    for address in sorted(byte_map):
        if previous is None or address != previous + 1:
            if data:
                spans.append((start, bytes(data)))
            start, data = address, bytearray()
        data.append(byte_map[address])
        previous = address
    if data:
        spans.append((start, bytes(data)))
    return tuple(spans)


def verify_live(base, read, *, core_sha256, root=None):
    """Check source identity only. Success is not command or action admission."""
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_action_transport_source import verify_live as selected
        return selected(base, read, family='unit', root=root)
    if core_sha256 != CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Unit UI profile requires its exact XP1 module')
    proof = source(root)
    spans = instruction_spans(proof)
    for rva, expected in spans:
        if read(base + rva, len(expected)) != expected:
            raise ValueError('XP1 unit-operation instruction bytes changed at ' + hex(rva))
    table = proof['data']['unit_operation_message_vtable']
    expected = b''.join(struct.pack('<Q', base + int(value, 16)) for value in table['entries'])
    if read(base + int(table['rva'], 16), len(expected)) != expected:
        raise ValueError('XP1 unit-operation message vtable changed')
    for rva, text in proof['data']['argument_type_names'].items():
        expected = text.encode('ascii') + b'\0'
        if read(base + int(rva, 16), len(expected)) != expected:
            raise ValueError('XP1 unit-operation argument type changed')
    return {'source_sha256': SOURCE[1], 'callbacks': dict(CALLBACKS),
            'instruction_spans_verified': len(spans),
            'native_request_invoked': False, 'actions_admitted': False}

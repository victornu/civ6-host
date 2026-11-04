"""Immutable source-selected GameCore script binding ABI and read-only guards.

No native function is called here. A source profile and matching live bytes do
not admit saved-game Load, a complete Lua API, gameplay, or training.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import struct

from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE_PATH = 'work/host-extensions/xp2-script-api/source-profile-v1.json'
SOURCE_SHA = '622ed4cb467b70b776c3ff4ca09a284feebca872ff7e99e2af01f1d07d9b94d6'
SCHEMA = 'civ6-host.script-api-binding-profile.v1'
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_REFERENCE_BYTES = 16 * 1024 * 1024
_MAX_RVA = 128 * 1024 * 1024
_MAX_ADDRESS = (1 << 47) - 1
_ABI_FIELDS = ('profile_id', 'context_vtable_rva', 'getter_slot', 'getter_rva',
               'interface_rva', 'interface_vtable_rva', 'method_slot', 'method_rva',
               'registration_rva')
_XP2_ABI = (2, 0xA101E8, 0x68, 0x590440, 0xB8F0E0, 0xA126C8, 0x10, 0x5A1DA0, 0x5BDAC0)
_CANONICAL = None


@dataclass(frozen=True, slots=True)
class NativeBody:
    name: str
    rva: int
    bytes: int
    sha256: str
    raw: bytes


@dataclass(frozen=True, slots=True)
class NativeSlot:
    table_rva: int
    slot: int
    target_rva: int


@dataclass(frozen=True, slots=True)
class PrerequisiteOwner:
    name: str
    global_rva: int
    reader_rva: int
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class SourceReference:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class GameScriptBindingABI:
    ruleset: str
    core_sha256: str
    source_path: str
    source_sha256: str
    profile_id: int
    context_vtable_rva: int
    getter_slot: int
    getter_rva: int
    interface_rva: int
    interface_vtable_rva: int
    method_slot: int
    method_rva: int
    registration_rva: int
    bodies: tuple[NativeBody, ...]
    slots: tuple[NativeSlot, ...]
    prerequisites: tuple[PrerequisiteOwner, ...]
    references: tuple[SourceReference, ...]
    load_admitted: bool = False
    complete_api_verified: bool = False


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, low, high, name):
    _require(type(value) is int and low <= value <= high, 'Invalid script binding '+name)
    return value


def _sha(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
             'Script binding source hash is not sealed')
    return value


def _private_path(name):
    _require(type(name) is str and name and '\0' not in name
             and not Path(name).is_absolute() and not Path(name).drive
             and all(part not in ('', '.', '..') for part in name.replace('\\','/').split('/')),
             'Script binding source needs a relative private resource path')
    root = resource_root()
    path = resolve_path(root / name).resolve(strict=True)
    _require(path.is_relative_to(root) and path.is_file(), 'Script binding source left its resource root')
    return path


def _verify_reference(row):
    _require(isinstance(row, Mapping) and set(row) == {'path','bytes','sha256'},
             'Malformed script binding source reference')
    size = _integer(row['bytes'], 1, _MAX_REFERENCE_BYTES, 'reference size')
    sha = _sha(row['sha256'])
    path = _private_path(row['path'])
    before = path.stat()
    _require(before.st_size == size, 'Script binding reference size changed')
    with path.open('rb') as stream:
        raw = stream.read(size + 1)
    after = path.stat()
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    _require(identity(before) == identity(after) and len(raw) == size
             and hashlib.sha256(raw).hexdigest() == sha, 'Script binding reference bytes changed')
    return SourceReference(row['path'], size, sha)


def _parse(document):
    fields = {'schema','engine','native_execution','abi','bodies','slots','prerequisites','references'}
    _require(isinstance(document, Mapping) and set(document) == fields
             and document['schema'] == SCHEMA and document['native_execution'] is False,
             'Script binding source classification differs')
    _require(isinstance(document['engine'], Mapping)
             and dict(document['engine']) == dict(ruleset='xp2', sha256=XP2_CORE_SHA256),
             'Script binding engine identity differs')
    abi = document['abi']
    _require(isinstance(abi, Mapping) and set(abi) == set(_ABI_FIELDS), 'Incomplete script binding ABI')
    for key in _ABI_FIELDS:_integer(abi[key], 0, _MAX_RVA, key)
    _require(tuple(abi[key] for key in _ABI_FIELDS) == _XP2_ABI,
             'Script binding ABI differs from its closed native profile')
    bodies = []
    rows = document['bodies']
    _require(type(rows) in (list,tuple) and 0 < len(rows) <= 64, 'Invalid script binding body inventory')
    for row in rows:
        _require(isinstance(row, Mapping) and set(row) == {'name','rva','bytes','sha256','raw_hex'}
                 and type(row['name']) is str and 0 < len(row['name']) <= 128,
                 'Malformed script binding body')
        rva = _integer(row['rva'], 1, _MAX_RVA, 'body RVA')
        size = _integer(row['bytes'], 1, 1024*1024, 'body size')
        sha = _sha(row['sha256'])
        _require(type(row['raw_hex']) is str and len(row['raw_hex']) == size*2
                 and re.fullmatch('[0-9a-fA-F]+', row['raw_hex']) is not None,
                 'Script binding body is not a complete byte sequence')
        raw = bytes.fromhex(row['raw_hex'])
        _require(rva+size <= _MAX_RVA and hashlib.sha256(raw).hexdigest() == sha,
                 'Script binding body digest or bounds differ')
        bodies.append(NativeBody(row['name'], rva, size, sha, raw))
    _require(len({b.rva for b in bodies}) == len(bodies)
             and len({b.name for b in bodies}) == len(bodies)
             and sum(b.bytes for b in bodies) <= 4*1024*1024, 'Repeated or oversized script binding body inventory')
    slots = []
    rows = document['slots']
    _require(type(rows) in (list,tuple) and 0 < len(rows) <= 128, 'Invalid script binding slot inventory')
    for row in rows:
        _require(isinstance(row, Mapping) and set(row) == {'table_rva','slot','target_rva'},
                 'Malformed script binding slot')
        table = _integer(row['table_rva'], 1, _MAX_RVA-4096, 'slot table')
        slot = _integer(row['slot'], 0, 4088, 'slot offset')
        target = _integer(row['target_rva'], 1, _MAX_RVA, 'slot target')
        _require(table%8 == slot%8 == 0, 'Unaligned script binding slot')
        slots.append(NativeSlot(table, slot, target))
    _require(len({(s.table_rva,s.slot) for s in slots}) == len(slots), 'Repeated script binding slot')
    _require(NativeSlot(abi['context_vtable_rva'],abi['getter_slot'],abi['getter_rva']) in slots
             and NativeSlot(abi['interface_vtable_rva'],abi['method_slot'],abi['method_rva']) in slots,
             'Script binding source omits its required dispatch slots')
    owners = []
    rows = document['prerequisites']
    _require(type(rows) in (list,tuple) and 0 < len(rows) <= 128, 'Missing script registration prerequisites')
    for row in rows:
        _require(isinstance(row, Mapping) and set(row) == {'name','global_rva','reader_rva','nullable'}
                 and type(row['name']) is str and 0 < len(row['name']) <= 128 and row['nullable'] is False,
                 'Malformed or nullable script registration prerequisite')
        global_rva = _integer(row['global_rva'], 1, _MAX_RVA-8, 'prerequisite global')
        reader = _integer(row['reader_rva'], 1, _MAX_RVA, 'prerequisite reader')
        _require(global_rva%8 == 0, 'Unaligned script prerequisite global')
        owners.append(PrerequisiteOwner(row['name'],global_rva,reader))
    _require(len({p.name for p in owners}) == len(owners)
             and len({p.global_rva for p in owners}) == len(owners), 'Repeated script registration prerequisite')
    required = {abi['getter_rva'],abi['method_rva'],abi['registration_rva'],*[p.reader_rva for p in owners]}
    _require(required.issubset({body.rva for body in bodies}), 'Script binding source omits a required complete body')
    rows = document['references']
    _require(type(rows) in (list,tuple) and 0 < len(rows) <= 128, 'Missing script binding raw source references')
    references = tuple(_verify_reference(row) for row in rows)
    _require(len({r.path for r in references}) == len(references), 'Repeated script binding source reference')
    return GameScriptBindingABI('xp2', XP2_CORE_SHA256, SOURCE_PATH, SOURCE_SHA,
        **{key:abi[key] for key in _ABI_FIELDS}, bodies=tuple(bodies), slots=tuple(slots),
        prerequisites=tuple(owners), references=references)


def profile_for_sha(core_sha256):
    """Select only a sealed exact engine/source pair; unknown engines fail closed."""
    if type(core_sha256) is not str or core_sha256 != XP2_CORE_SHA256:
        raise ValueError('No qualified GameCore script binding source profile')
    _sha(SOURCE_SHA)
    path = _private_path(SOURCE_PATH)
    _require(0 < path.stat().st_size <= _MAX_SOURCE_BYTES, 'Unbounded script binding profile source')
    document = load_pinned_json(path, SOURCE_SHA)
    global _CANONICAL
    if _CANONICAL is not None and _CANONICAL[0] is document:
        for reference in _CANONICAL[1].references:
            _verify_reference(dict(path=reference.path,bytes=reference.bytes,sha256=reference.sha256))
        return _CANONICAL[1]
    profile = _parse(document)
    _CANONICAL = (document, profile)
    return profile


def _canonical(profile):
    _require(type(profile) is GameScriptBindingABI and profile is profile_for_sha(profile.core_sha256),
             'Expected the canonical source-selected script binding profile')


def _address(value):
    _require(type(value) is int and 0x10000 <= value <= _MAX_ADDRESS and value%8 == 0,
             'Invalid native script binding address')
    return value


def _at(base, offset, size):
    _require(type(offset) is int and offset >= 0 and type(size) is int and size > 0
             and base+offset+size-1 <= _MAX_ADDRESS, 'Native script binding address overflow')
    return base+offset


def _read(read, address, size):
    _require(callable(read), 'Native script binding requires an explicit byte reader')
    raw = read(address, size)
    _require(type(raw) is bytes and len(raw) == size, 'Incomplete native script binding read')
    return raw


def _pointer(read, address):
    return struct.unpack('<Q', _read(read,address,8))[0]


def verify_live(profile, base, context, read):
    """Verify code/dispatch and every non-null owner before returning a getter."""
    _canonical(profile);_address(base);_address(context)
    _require(_pointer(read,_at(context,0,8)) == _at(base,profile.context_vtable_rva,8),
             'Native script context vtable differs')
    for body in profile.bodies:
        raw = _read(read,_at(base,body.rva,body.bytes),body.bytes)
        _require(raw == body.raw and hashlib.sha256(raw).hexdigest() == body.sha256,
                 'Native script binding body changed: '+body.name)
    for slot in profile.slots:
        _require(_pointer(read,_at(base,slot.table_rva+slot.slot,8)) == _at(base,slot.target_rva,1),
                 'Native script binding dispatch slot changed')
    for owner in profile.prerequisites:
        pointer = _pointer(read,_at(base,owner.global_rva,8))
        _require(pointer != 0, 'Native script registration owner is null: '+owner.name)
        _address(pointer)
    return _at(base,profile.getter_rva,1)


def verify_interface(profile, base, pointer, read):
    """Require the exact static singleton, its vtable and its method slot."""
    _canonical(profile);_address(base);_address(pointer)
    _require(pointer == _at(base,profile.interface_rva,8), 'Native script getter returned a foreign interface')
    _require(_pointer(read,pointer) == _at(base,profile.interface_vtable_rva,8)
             and _pointer(read,_at(base,profile.interface_vtable_rva+profile.method_slot,8))
                 == _at(base,profile.method_rva,1), 'Native script interface vtable/method differs')


def source_dependencies(core_sha256=XP2_CORE_SHA256):
    profile = profile_for_sha(core_sha256)
    return {str(_private_path(name)):sha for name,sha in (
        (profile.source_path,profile.source_sha256), *[(row.path,row.sha256) for row in profile.references])}

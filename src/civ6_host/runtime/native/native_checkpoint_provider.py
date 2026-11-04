"""Bounded native application configuration stream; import never invokes Core.

B is our NativeApplicationConfiguration owner, not an EXE secondary section.
The provider and its variants are serialized/deserialized by the real Core
methods. Python only owns the bounded stream and verifies object identity.
Native callbacks are fatal on error. Once a provider operation has entered
Core, any exception is fatal too: a partially restored map cannot be retried.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_provider.py')))).resolve().parents[1]
from civ6_host.runtime.native.native_application_configuration import NativeApplicationConfiguration
from civ6_host.runtime.native import native_application_configuration as application
from civ6_host.runtime.native.native_checkpoint_stream import Win64Stream
from civ6_host.runtime.native.native_checkpoint_stream import LocalMemory
PROOF_SHA256 = '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7'
CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CORE_BASE = 6442450944
VTABLE_RVA = 8507296
METHODS = {488: 7668432, 496: 7627280, 504: 7668032, 512: 7668192}
DEPENDENCY_SLOTS = {32: 7661648, 312: 7632112, 352: 7622544, 472: 422768}
FATAL_EXIT_CODE = 87
UINT64_MAX = (1 << 64) - 1
_STATES = {}
_STATES_LOCK = threading.RLock()

def _uint(value, name, maximum=UINT64_MAX, *, positive=False):
    if type(value) is not int or not int(positive) <= value <= maximum:
        raise ValueError(name + ' has an invalid exact unsigned integer domain')
    return value

def _sha(data):
    return hashlib.sha256(data).hexdigest()

def _instructions(value):
    if isinstance(value, dict):
        if {'va', 'bytes', 'text'} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from _instructions(child)
    elif isinstance(value, list):
        for child in value:
            yield from _instructions(child)

def verify_source(*, core_sha256=CORE_SHA256):
    if core_sha256 != CORE_SHA256:
        return _expansion_codec_source(core_sha256)
    if len(PROOF_SHA256) != 64:
        raise RuntimeError('Provider stream source pin is not frozen')
    path = ROOT / 'evidence/native-checkpoint-configuration-stream-v3' / (PROOF_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if _sha(raw) != PROOF_SHA256:
        raise RuntimeError('Provider stream proof changed')
    proof = json.loads(raw)
    if proof.get('schema') != 'civ6rl.native_checkpoint_configuration_stream.static.v3' or proof.get('images', {}).get('core', {}).get('sha256') != CORE_SHA256 or proof.get('images', {}).get('exe', {}).get('sha256') != EXE_SHA256 or (proof.get('native_execution') is not False):
        raise RuntimeError('Provider stream source identity changed')
    wrappers = proof['registration_and_callers']['provider_wrappers']
    if wrappers['write']['flags_r8d'] != 0 or wrappers['read']['r8_value'] != 0 or wrappers['read']['core_third_argument'] != 'optional void*; null skips provider vtable slot+0x10':
        raise RuntimeError('Provider third-argument contract changed')
    slots = proof['registration_and_callers']['provider_vtable']
    if slots['va'] != '0x18081cfa0':
        raise RuntimeError('Provider vtable source changed')
    for slot, rva in METHODS.items():
        row = slots['slots'][hex(slot)]
        if int(row['target_rva'], 16) != rva:
            raise RuntimeError('Provider method source changed')
    rows = {int(i['va'], 16): i['text'] for i in _instructions(proof['captures']['core'])}
    expected = {6450078253: 'mov esi, r8d', 6450078262: 'call qword ptr [rax + 0x1f8]', 6450078309: 'call qword ptr [rax + 0x200]', 6450119411: 'mov rdi, r8', 6450119432: 'call qword ptr [rax + 0x160]', 6450119438: 'test rdi, rdi', 6450119452: 'call qword ptr [rax + 0x10]', 6450119520: 'call qword ptr [rax + 0x30]', 6450119529: 'call qword ptr [rax + 0x40]'}
    if any((rows.get(va) != text for va, text in expected.items())):
        raise RuntimeError('Provider reader/writer ABI source changed')
    for relative, row in proof['parent_captures'].items():
        if _sha(_resolve_resource_path(ROOT / relative).read_bytes()) != row['sha256']:
            raise RuntimeError('Provider stream parent changed: ' + relative)
    application.verify_source()
    return proof

class _Runtime:
    """Only OS-checked reads and verified native method addresses."""

    def __init__(self):
        self.memory = LocalMemory()
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetCurrentThreadId.argtypes = []
        self.kernel.GetCurrentThreadId.restype = C.c_uint32
        self.kernel.GetModuleFileNameW.argtypes = [C.c_void_p, C.c_wchar_p, C.c_uint32]
        self.kernel.GetModuleFileNameW.restype = C.c_uint32

    def thread(self):
        return (threading.get_ident(), int(self.kernel.GetCurrentThreadId()))

    def image(self, base, proof):
        _require_owner_profile(_configuration_abi(proof['images']['core']['sha256']))
        path_buffer = C.create_unicode_buffer(32768)
        length = self.kernel.GetModuleFileNameW(base, path_buffer, len(path_buffer))
        if not length or length >= len(path_buffer):
            raise OSError('Cannot establish actual loaded Core path')
        actual = _resolve_resource_path(Path(path_buffer.value))
        expected = _resolve_resource_path(Path(proof['images']['core']['path']))
        if not actual.is_absolute() or not expected.is_absolute() or '..' in actual.parts or ('..' in expected.parts):
            raise ValueError('Loaded Core path is not absolute and traversal-free')
        if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
            raise ValueError('Loaded Core path differs from pinned Base image')
        if _sha(_resolve_resource_path(actual).read_bytes()) != proof['images']['core']['sha256']:
            raise ValueError('Loaded Core file hash differs')
        return str(actual)

    def read(self, address, size):
        raw = self.memory.read(address, size)
        if type(raw) is not bytes or len(raw) != size:
            raise ValueError('Incomplete provider memory read')
        return raw

    def invoke(self, address, pointer, stream, mode):
        third = C.c_uint32 if mode == 'writer' else C.c_void_p
        f = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, third)(address)
        f(pointer, stream, 0 if mode == 'writer' else None)

def _fatal(state, error):
    state.poisoned = True
    try:
        os.write(2, (json.dumps({'stage': 'provider_stream_fatal', 'error': str(error)[:512], 'poisoned': True, 'retry_permitted': False}) + '\n').encode('utf-8'))
    finally:
        from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
        terminate_worker(FATAL_EXIT_CODE)

class _Session:

    def __init__(self, core, context, owner, max_bytes, max_calls):
        self.abi = _require_owner_profile(getattr(owner, '_configuration_abi', None))
        self.core, self.context, self.owner = (core, context, owner)
        self.max_bytes = _uint(max_bytes, 'byte limit', sys.maxsize, positive=True)
        self.max_calls = _uint(max_calls, 'call limit', positive=True)
        self.base = _uint(core._handle, 'Core base', positive=True)
        _uint(context, 'context', positive=True)
        self.runtime = _Runtime()
        self.thread = self.runtime.thread()
        self.busy = self.poisoned = self.restore_attempted = self.restore_sealed = False
        self.streams = []
        self.proof = verify_source(core_sha256=self.abi.core_sha256)
        self.loaded_path = self.runtime.image(self.base, self.proof)
        self._validate_owner(False)
        self._live_code()

    def _qword(self, address):
        return struct.unpack('<Q', self.runtime.read(address, 8))[0]

    def _validate_owner(self, restoring):
        if getattr(self.owner, '_configuration_abi', None) is not self.abi:
            raise ValueError('Provider owner changed its engine ABI identity')
        owner = self.owner
        if type(owner) is not NativeApplicationConfiguration or getattr(self.core, '_civ6rl_application_configuration', None) is not owner or owner.closed is not False or (owner.base != self.base) or (owner.context != self.context) or (owner.call is not None):
            raise ValueError("Expected this context's real owned application provider B")
        owner._check_guard()
        if C.sizeof(owner.storage) != application.STORAGE_SIZE + 32 or owner.pointer != C.addressof(owner.storage) + 16:
            raise ValueError('Provider B does not point into its guarded owned storage')
        owner.require_context(self.base, self.context)
        if self._qword(self.context) != self.base + self.abi.load.outer_vtable_rva:
            raise ValueError('Outer context vtable differs')
        inner = self._qword(self.context + 8)
        if not inner or self._qword(inner) != self.base + self.abi.load.inner_vtable_rva:
            raise ValueError('Inner context vtable differs')
        core_provider = self._qword(inner + 3456 + 128)
        game = self._qword(inner + 96)
        if not core_provider or owner.pointer in (core_provider, game, self.context, inner):
            raise ValueError('Provider restore/save target must be distinct owned B, never A or Game')
        if self._qword(owner.pointer) != self.base + self.abi.vtable_rva or self._qword(core_provider) != self.base + self.abi.vtable_rva:
            raise ValueError('Application/Core provider vtable differs')
        for slot, rva in dict(self.abi.codec_slots).items():
            if self._qword(self.base + self.abi.vtable_rva + slot) != self.base + rva:
                raise ValueError('Provider method slot differs')
        if restoring and (game != 0 or owner.new_game_entered is not False or self.restore_attempted or self.restore_sealed):
            raise ValueError('Restore requires unused owned B before NewGame/Load handoff')
        return (inner, core_provider, game)

    def _live_code(self):
        application._live_code(self.base, self.runtime.read, core_sha256=self.abi.core_sha256)
        for ins in _instructions(self.proof['captures']['core']):
            data = bytes.fromhex(ins['bytes'])
            if self.runtime.read(self.base + int(ins['va'], 16) - CORE_BASE, len(data)) != data:
                raise ValueError('Provider codec live instruction mismatch at ' + ins['va'])

    def _identity(self):
        inner, core_provider, game = self._validate_owner(False)
        before = application.provider_snapshot(self.base, self.owner.pointer, self.runtime.read, core_sha256=self.abi.core_sha256)
        addresses = (before['descriptor'], before['normalized'], before['map_normalized'], *before['players'])
        headers = tuple((self.runtime.read(p, application.STORAGE_SIZE) for p in addresses))
        core = application.provider_snapshot(self.base, core_provider, self.runtime.read, core_sha256=self.abi.core_sha256)
        core_addresses = (core['descriptor'], core['normalized'], core['map_normalized'], *core['players'])
        if set(addresses) & set(core_addresses):
            raise ValueError('Owned B submaps alias the Core setup')
        return {'inner': inner, 'core_provider': core_provider, 'game': game, 'B_topology': before, 'B_headers': headers, 'A_topology': core, 'owner_pointer': self.owner.pointer}

    def _preflight(self, restoring):
        if self.runtime.thread() != self.thread:
            raise ValueError('Provider operation attempted from a different bound thread')
        if self.poisoned:
            raise RuntimeError('Provider session is poisoned')
        if self.busy:
            _fatal(self, RuntimeError('Reentrant provider operation'))
        self._validate_owner(restoring)
        self._live_code()
        return self._identity()

    def execute(self, mode, data=b'', expected_sha256=None):
        restoring = mode == 'reader'
        if mode not in ('writer', 'reader'):
            raise ValueError('Unknown provider stream operation')
        if restoring:
            if type(data) is not bytes or not 4 <= len(data) <= self.max_bytes or type(expected_sha256) is not str or (len(expected_sha256) != 64) or any((c not in '0123456789abcdef' for c in expected_sha256)) or (_sha(data) != expected_sha256):
                raise ValueError('Restore requires bounded immutable bytes and exact source SHA-256')
        before = self._preflight(restoring)
        stream = Win64Stream(mode, max_bytes=self.max_bytes, max_calls=self.max_calls, input_bytes=data if restoring else b'')
        self.streams.append(stream)
        self.busy = True
        entered = False
        try:
            self._validate_owner(restoring)
            stream._check(stream.pointer)
            if restoring:
                self.restore_attempted = True
            entered = True
            self.runtime.invoke(self.base + dict(self.abi.codec_slots)[488 if restoring else 496], self.owner.pointer, stream.pointer, mode)
            stream._check(stream.pointer)
            after = self._identity()
            if restoring:
                if stream.transport.cursor != len(data):
                    raise RuntimeError('Provider restore did not consume the complete sidecar')
                if any((before[key] != after[key] for key in ('inner', 'core_provider', 'game', 'A_topology', 'owner_pointer'))):
                    raise RuntimeError('Restore changed context/Core topology or provider owner')
            elif before != after:
                raise RuntimeError('Provider Save changed its object identity/topology/header')
            output = b'' if restoring else stream.output_bytes()
            receipt = {'operation': 'restore' if restoring else 'serialize', 'proof_sha256': self.abi.codec_proof_sha256, 'core_sha256': self.abi.core_sha256, 'native_method_result_observed': False, 'native_return_interpreted': False, 'writer_flags32': 0 if not restoring else None, 'reader_optional_pointer': None, 'bytes': len(data) if restoring else len(output), 'sha256': expected_sha256 if restoring else _sha(output), 'stream_calls': stream.transport.calls, 'identity_checked_before_after': True, 'all_property_values_compared': False, 'eligible_for_training': False}
            stream.close()
            return receipt if restoring else (output, receipt)
        except BaseException as exc:
            if entered:
                _fatal(self, exc)
            if not stream.transport.closed and (not stream.transport.poisoned):
                stream.close()
            raise
        finally:
            self.busy = False

def _session(core, context, owned_provider, max_bytes, max_calls):
    _uint(context, 'context', positive=True)
    _uint(max_bytes, 'byte limit', sys.maxsize, positive=True)
    _uint(max_calls, 'call limit', positive=True)
    key = id(owned_provider)
    with _STATES_LOCK:
        existing = _STATES.get(key)
        if existing is None:
            existing = _Session(core, context, owned_provider, max_bytes, max_calls)
            _STATES[key] = existing
        elif existing.core is not core or existing.context != context or existing.owner is not owned_provider or (existing.max_bytes != max_bytes) or (existing.max_calls != max_calls):
            raise ValueError('Provider session identity or fixed resource limits differ')
    return existing

def serialize_provider(core, context, owned_provider, *, max_bytes, max_calls):
    """Return (native bytes, diagnostic receipt); first use binds this OS thread."""
    return _session(core, context, owned_provider, max_bytes, max_calls).execute('writer')

def restore_provider(core, context, owned_provider, data, *, expected_sha256, max_bytes, max_calls):
    """Restore once into owned B, before its NewGame/Load handoff. No Core status is fabricated."""
    return _session(core, context, owned_provider, max_bytes, max_calls).execute('reader', data, expected_sha256)

def seal_restoration(core, context, owned_provider, *, max_bytes, max_calls):
    """Caller invokes before handing B to +120/+130; restores then remain forbidden."""
    state = _session(core, context, owned_provider, max_bytes, max_calls)
    state._preflight(False)
    state.restore_sealed = True
from civ6_host.runtime.configuration_profiles import configuration_abi as _configuration_abi
from civ6_host.runtime.configuration_profiles import require_owner_profile as _require_owner_profile
from civ6_host.runtime.configuration_profiles import application_source as _expansion_application_source
from civ6_host.runtime.configuration_profiles import codec_source as _expansion_codec_source

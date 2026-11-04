"""Explicit Performance settings derived from the pinned EXE, in a real XP1 map.

The automatic CPU detection branch is unsupported, not approximated. This is
host configuration, not a replacement for native rules or native job execution.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_xp1_map_setup import _read
from civ6_host.runtime.native.native_xp1_map_setup import PREFERRED_BASE
from civ6_host.runtime.native.native_xp1_map_setup import CORE_SHA
from civ6_host.runtime.native.native_xp1_application_configuration import UnsafeOwnership
from civ6_host.runtime.native.native_xp1_application_configuration import GUARD
CAPTURE_SHA = '8bc505c5bd4fd4007f0e4f13c13876a0f34771f25198316182a9b973e37d809a'
DOMAIN = 4222936745
KEYS = (2126765924, 3246517102, 3768025511)
INPUTS = ('MaxJobThreads', 'MaxGameCoreThreads', 'GameCoreReserveThreads', 'MaxGameCoreUnitMovementThreads', 'MaxGameCoreTradeRouteThreads')
_QUARANTINE = []

def source_profile(root):
    root = _resolve_resource_path(Path(root))
    p = load_pinned_json(root / 'work/native-xp1-options896/capture896v2.json', CAPTURE_SHA)
    if p['xp1_sha256'] != CORE_SHA or p['eligible_for_training'] is not False:
        raise ValueError('XP1 Performance proof scope differs')
    for ref in p['parents'].values():
        load_pinned_json(root / ref['path'], ref['sha256'])
    return p

def _i32(value):
    value &= 4294967295
    return value if value < 2147483648 else value - 4294967296

def derive(settings):
    """EXE06cf0a..47,06d2b6,06d363..403; all arithmetic is signed DWORD.

    A positive per-path override is used as-is, even when below the general
    count. It is not a maximum with that count (cmovle tests the input itself).
    """
    if set(settings) != set(INPUTS) or any((type(settings[k]) is not int or not -2147483648 <= settings[k] <= 2147483647 for k in INPUTS)):
        raise ValueError('Performance requires exactly five signed DWORD inputs')
    jobs, maximum, reserve, units, trade = (settings[k] for k in INPUTS)
    if jobs == -1:
        raise ValueError('Automatic hardware thread detection is not implemented')
    engine = min(32, max(2, jobs)) + 1
    if maximum < 0:
        maximum = engine
    if reserve < 0:
        if engine <= 8:
            maximum = _i32(maximum - 2)
        elif engine <= 16:
            maximum = _i32(maximum - 4)
    selected = min(engine, maximum)
    extra = _i32(_i32(reserve - engine) + selected)
    count = max(1, _i32(selected - max(0, extra)))
    return {'effective_engine_threads': engine, 'values': dict(zip(KEYS, (count, units if units > 0 else count, trade if trade > 0 else count)))}

def _rows(body):
    yield from body.get('instructions', ())
    for f in body.get('fragments', ()):
        yield from f.get('instructions', ())

def verify_code(base, read, proof):
    bodies = [proof['xp1_consumer'], proof['xp1_dispatch'], proof['xp1_numeric_setter']]
    bodies.extend(proof['xp1_owner_bodies'].values())
    bodies.extend(proof['xp1_getter_bodies'].values())
    for body in bodies:
        for row in _rows(body):
            raw = bytes.fromhex(row['bytes'])
            if _read(read, base + int(row['va'], 16) - PREFERRED_BASE, len(raw)) != raw:
                raise ValueError('XP1 Performance native code differs')
    for slot, rva in proof['contract']['slots'].items():
        if struct.unpack('<Q', _read(read, base + proof['contract']['map_vtable_rva'] + int(slot, 16), 8))[0] != base + rva:
            raise ValueError('XP1 Performance native vtable differs')

class PerformanceDomain:
    """Own only outer storage; the official constructor/setter/destructor own values."""

    def __init__(self, borrower, *, root, settings=None, recorded_input=None):
        borrower._check()
        self.base, self.read, self.invoke = (borrower.base, borrower.read, borrower._invoke)
        from civ6_host.runtime.xp2_load_options_capability_profile import performance_select
        self.proof = performance_select(borrower, root, source_profile)
        if recorded_input is None:
            self.settings = dict(settings)
            self.derived = derive(settings)
        else:
            if settings is not None:
                raise ValueError('Recorded options cannot mix with diagnostic settings')
            from civ6_host.runtime.xp1_load_options import recorded_values
            self.derived = {'values': recorded_values(recorded_input, borrower), recorded_input.kind: True}
            self.settings = dict(recorded_input.raw_settings)
        self.closed = self.poisoned = self.bound = False
        self.calls = 0
        verify_code(self.base, self.read, self.proof)
        self.storage = C.create_string_buffer(88 + 32)
        start = C.addressof(self.storage)
        self.pointer = start + 16
        C.memmove(start, GUARD, 16)
        C.memmove(self.pointer + 88, GUARD, 16)
        try:
            result = self.invoke(self.proof['contract']['constructor_rva'], C.c_void_p, (C.c_void_p,), self.pointer)
            self._guard()
            if result != self.pointer:
                raise ValueError('XP1 Performance constructor identity differs')
            for key, value in self.derived['values'].items():
                self.invoke(self.proof['contract']['slots']['0x130'], C.c_void_p, (C.c_void_p, C.c_uint32, C.c_uint32), self.pointer, key, value)
            self.snapshot()
        except BaseException as error:
            self.poisoned = True
            _QUARANTINE.append(self)
            raise UnsafeOwnership('XP1 Performance construction uncertain; terminate process') from error

    def _guard(self):
        if self.closed or self.poisoned:
            raise ValueError('XP1 Performance owner closed or poisoned')
        if self.storage.raw[:16] != GUARD or self.storage.raw[-16:] != GUARD:
            raise ValueError('XP1 Performance storage guard changed')
        if struct.unpack('<Q', _read(self.read, self.pointer, 8))[0] != self.base + self.proof['contract']['map_vtable_rva']:
            raise ValueError('XP1 Performance provider identity changed')

    def snapshot(self):
        self._guard()
        values = {}
        if struct.unpack('<I', _read(self.read, self.pointer + 80, 4))[0] != 3:
            raise ValueError('XP1 Performance does not contain exactly three derived fields')
        for key, expected in self.derived['values'].items():
            node = self.invoke(self.proof['contract']['slots']['0x68'], C.c_void_p, (C.c_void_p, C.c_uint32), self.pointer, key)
            if not node:
                raise ValueError('XP1 Performance nonnullable getter returned NULL')
            raw = _read(self.read, node, 24)
            if struct.unpack_from('<I', raw)[0] != 2 or struct.unpack_from('<Q', raw, 16)[0] != 0:
                raise ValueError('XP1 Performance requires an inline native DWORD')
            value = struct.unpack_from('<I', raw, 8)[0]
            if value != expected:
                raise ValueError('XP1 Performance native value changed')
            values[f'0x{key:08x}'] = value
        return values

    def close(self, *, context_destroyed=False):
        if self.bound and context_destroyed is not True:
            raise ValueError('Bound Performance domain must outlive the Core context')
        try:
            values = self.snapshot()
            verify_code(self.base, self.read, self.proof)
            self.invoke(self.proof['contract']['destructor_rva'], None, (C.c_void_p,), self.pointer)
            if self.storage.raw[:16] != GUARD or self.storage.raw[-16:] != GUARD:
                raise ValueError('XP1 Performance destructor exceeded storage')
        except BaseException as error:
            self.poisoned = True
            _QUARANTINE.append(self)
            raise UnsafeOwnership('XP1 Performance destruction uncertain; terminate process') from error
        self.closed = True
        return {'native_destructor_returned': True, 'guards_intact': True, 'values_before_close': values, 'outer_storage_freed_by_native': False}

def install(borrower, host, *, root):
    if getattr(host, 'xp1_performance', None) is not None:
        raise ValueError('XP1 Performance already installed')
    p = source_profile(root)
    if host.core_base != borrower.base or struct.unpack('<Q', _read(borrower.read, borrower.base + 10430016, 8))[0] != host.pointer:
        raise ValueError('XP1 Performance global refers to a different host')
    provider = PerformanceDomain(borrower, root=root, settings=p['profile'])

    def get_domain(this, domain):
        host._check(this)
        if host.xp1_performance is not provider or host.core_base != provider.base:
            raise ValueError('XP1 Performance owner replaced')
        if domain != DOMAIN:
            raise ValueError('Unsupported XP1 option domain ' + hex(domain))
        values = provider.snapshot()
        provider.calls += 1
        host.emit('xp1_performance_requested', domain=f'0x{domain:08x}', values=values, call_index=provider.calls, source_sha256=CAPTURE_SHA, explicit_diagnostic_settings=True, real_native_provider=True, eligible_for_training=False)
        return provider.pointer
    try:
        host.xp1_performance = provider
        provider.bound = True
        host._bind(host.vtable, 344, C.c_void_p, [C.c_void_p, C.c_uint32], get_domain)
    except BaseException as error:
        provider.poisoned = True
        _QUARANTINE.append(provider)
        raise UnsafeOwnership('XP1 Performance binding uncertain; terminate process') from error
    return {'source_sha256': CAPTURE_SHA, 'inputs': dict(provider.settings), 'effective_engine_threads': provider.derived['effective_engine_threads'], 'native_readbacks': provider.snapshot(), 'real_native_provider': True, 'user_auto_settings_reproduced': False, 'automatic_hardware_detection_supported': False, 'eligible_for_training': False}

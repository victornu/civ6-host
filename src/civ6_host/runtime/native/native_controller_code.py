"""Owned original controller constructor/getter code; no EXE startup or scheduler.

Only relocation operands change. Clock and critical-section calls go to Windows.
Other controller services remain outside this owner's admitted interface.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import ctypes as C
import hashlib, json, os, struct, threading
from civ6_host.runtime.native.native_subscriber_code import RuntimeFunction
from civ6_host.runtime.native.native_subscriber_code import NativeSubscriberCode
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_controller_code.py')))).resolve().parents[1]
SOURCE_SHA = 'f164f34ca68ef71c5d7475e4881d84d2c6d88145e9e866532f4fed861adac90b'
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
OFFSETS = {'constructor': 0, 'get_flag': 256, 'clock': 512, 'elapsed': 768, 'critical_section': 1024, 'set_flag': 1280}
IMPORT_OFFSETS = {'QueryPerformanceCounter': 8192, 'QueryPerformanceFrequency': 8200, 'InitializeCriticalSection': 8208}

def source_profile():
    raw = _resolve_resource_path(ROOT / 'work/native-controller911/source-r2.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Controller source pin changed')
    p = json.loads(raw)
    if p['schema'] != 'civ6rl.native_controller911.source.v1' or p['image']['sha256'] != EXE_SHA or p['mutable_globals']['frequency']['section']['raw_backed'] is not False:
        raise ValueError('Controller image or fresh zero-backed global differs')
    return p

def build_image(source, imports):
    """Small closed island: code RX, unwind/imports RO, clock-frequency cache RW."""
    if source != source_profile():
        raise ValueError('Unpinned controller code/dependencies')
    if set(imports) != set(IMPORT_OFFSETS) or any((type(p) is not int or not 0 < p < 2 ** 64 for p in imports.values())):
        raise ValueError('Controller requires exactly its three Windows imports')
    image = bytearray(16384)
    image[:4096] = b'\xcc' * 4096
    for name, f in source['functions'].items():
        raw = bytes.fromhex(f['raw_hex'])
        start = OFFSETS[name]
        if len(raw) > 256 or hashlib.sha256(raw).hexdigest() != f['raw_sha256']:
            raise ValueError('Controller body identity changed')
        image[start:start + len(raw)] = raw
    relocated = []
    for row in source['fixups']:
        original = bytes.fromhex(row['bytes'])
        start = OFFSETS[row['function']] + row['offset']
        if image[start:start + len(original)] != original:
            raise ValueError('Overlapping/mismatched relocation')
        target = row['target']
        kind = target['kind']
        if kind == 'function':
            destination = OFFSETS[target['name']] + target['offset']
        elif kind == 'import':
            destination = IMPORT_OFFSETS[target['name']]
        elif kind == 'global' and target['name'] == 'frequency':
            destination = 12288
        else:
            raise ValueError('Unclosed controller relocation')
        size = row['displacement_size']
        pos = start + row['displacement_offset']
        old = int.from_bytes(original[row['displacement_offset']:row['displacement_offset'] + size], 'little', signed=True)
        source_pc = source['functions'][row['function']]['begin_rva'] + row['offset'] + len(original)
        if source_pc + old != row['target_source_rva']:
            raise ValueError('Source relocation does not resolve')
        delta = destination - start - len(original)
        image[pos:pos + size] = delta.to_bytes(size, 'little', signed=True)
        relocated.append(dict(offset=pos, bytes=size, destination=destination, original=original.hex()))
    cursor = 4096
    table = []
    for row in source['unwind_rows']:
        raw = bytes.fromhex(row['unwind_hex'])
        if raw[0] & 7 != 1 or raw[0] >> 3:
            raise ValueError('Unknown controller unwind handler')
        cursor = cursor + 3 & ~3
        image[cursor:cursor + len(raw)] = raw
        function = source['functions'][row['function']]
        start = OFFSETS[row['function']]
        table.append((start + row['begin_rva'] - function['begin_rva'], start + row['end_rva'] - function['begin_rva'], cursor))
        cursor += len(raw)
    if cursor > 8192:
        raise ValueError('Controller unwind storage overflow')
    for name, address in imports.items():
        struct.pack_into('<Q', image, IMPORT_OFFSETS[name], address)
    return dict(image=bytes(image), table=sorted(table), entries=OFFSETS.copy(), relocations=relocated, code_size=4096, readonly_size=8192, mutable_offset=12288)

class NativeControllerCode:
    """Executable owner. Controllers must close before their code/unwind owner."""

    def __init__(self):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('Controller requires Win64')
        self.owner = threading.get_ident()
        self.closed = False
        self.busy = False
        self.poisoned = False
        self.pointer = 0
        self.registered = False
        self.objects = set()
        self.source = source_profile()
        original = _resolve_resource_path(_resolve_resource_path(Path(self.source['image']['path']))).read_bytes()
        if hashlib.sha256(original).hexdigest() != EXE_SHA:
            raise ValueError('Installed EXE hash changed')
        for row in self.source['functions'].values():
            raw = bytes.fromhex(row['raw_hex'])
            offset = row['file_offset']
            if original[offset:offset + len(raw)] != raw:
                raise ValueError('Original controller instructions differ')
        for row in self.source['unwind_rows']:
            raw = bytes.fromhex(row['unwind_hex'])
            offset = row['file_offset']
            if original[offset:offset + len(raw)] != raw:
                raise ValueError('Original controller unwind differs')
        k = self.kernel = C.WinDLL('kernel32', use_last_error=True)
        n = self.ntdll = C.WinDLL('ntdll', use_last_error=True)
        imports = {name: C.cast(getattr(k, name), C.c_void_p).value for name in IMPORT_OFFSETS}
        self.layout = build_image(self.source, imports)
        k.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
        k.VirtualAlloc.restype = C.c_void_p
        k.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
        k.VirtualFree.restype = C.c_int
        k.VirtualProtect.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.POINTER(C.c_uint32)]
        k.VirtualProtect.restype = C.c_int
        k.GetCurrentProcess.argtypes = []
        k.GetCurrentProcess.restype = C.c_void_p
        k.FlushInstructionCache.argtypes = [C.c_void_p, C.c_void_p, C.c_size_t]
        k.FlushInstructionCache.restype = C.c_int
        k.DeleteCriticalSection.argtypes = [C.c_void_p]
        k.DeleteCriticalSection.restype = None
        n.RtlAddFunctionTable.argtypes = [C.POINTER(RuntimeFunction), C.c_uint32, C.c_uint64]
        n.RtlAddFunctionTable.restype = C.c_uint8
        n.RtlDeleteFunctionTable.argtypes = [C.POINTER(RuntimeFunction)]
        n.RtlDeleteFunctionTable.restype = C.c_uint8
        n.RtlLookupFunctionEntry.argtypes = [C.c_uint64, C.POINTER(C.c_uint64), C.c_void_p]
        n.RtlLookupFunctionEntry.restype = C.POINTER(RuntimeFunction)
        self.table = (RuntimeFunction * len(self.layout['table']))(*(RuntimeFunction(*r) for r in self.layout['table']))
        try:
            self.pointer = k.VirtualAlloc(None, 16384, 12288, 4)
            if not self.pointer:
                raise C.WinError(C.get_last_error())
            C.memmove(self.pointer, self.layout['image'], 16384)
            old = C.c_uint32()
            for offset, size, protection in ((0, 4096, 32), (4096, 8192, 2)):
                if not k.VirtualProtect(self.pointer + offset, size, protection, C.byref(old)):
                    raise C.WinError(C.get_last_error())
            if not k.FlushInstructionCache(k.GetCurrentProcess(), self.pointer, 4096):
                raise C.WinError(C.get_last_error())
            if not n.RtlAddFunctionTable(self.table, len(self.table), self.pointer):
                raise RuntimeError('Controller unwind registration failed')
            self.registered = True
            NativeSubscriberCode._verify_unwind(self)
            self.constructor = C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(self.pointer + OFFSETS['constructor'])
            self.getter = C.WINFUNCTYPE(C.c_uint8, C.c_void_p)(self.pointer + OFFSETS['get_flag'])
            self.setter = C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(self.pointer + OFFSETS['set_flag'])
        except BaseException:
            self.close()
            raise

    def _check(self):
        if self.closed or self.owner != threading.get_ident():
            raise RuntimeError('Controller code closed or foreign thread')
        if self.poisoned:
            raise RuntimeError('Controller code poisoned; retain allocations until bounded process exit')

    def create(self):
        self._check()
        if self.busy:
            raise RuntimeError('Nested controller construction')
        self.busy = True
        try:
            obj = NativeControllerFlag(self)
            return obj
        except BaseException:
            self.poisoned = True
            raise
        finally:
            self.busy = False

    def close(self):
        if self.closed:
            return
        self._check()
        if self.busy or self.objects:
            raise RuntimeError('Live controllers retain original code')
        if self.registered:
            if not self.ntdll.RtlDeleteFunctionTable(self.table):
                raise RuntimeError('Controller unwind deregistration failed')
            self.registered = False
        if self.pointer:
            if not self.kernel.VirtualFree(self.pointer, 0, 32768):
                raise C.WinError(C.get_last_error())
            self.pointer = 0
        self.closed = True

class NativeControllerFlag:
    """Private constructed 0x4B0 object; only the proven flag surface is exposed."""

    def __init__(self, code):
        self.code = code
        self.closed = False
        self.constructed = False
        self.poisoned = False
        self.storage = C.create_string_buffer(1200 + 64)
        self.pointer = C.addressof(self.storage) + 32
        C.memset(self.pointer - 32, 165, 32)
        C.memset(self.pointer + 1200, 165, 32)
        code.objects.add(self)
        try:
            result = code.constructor(self.pointer)
            if result != self.pointer:
                raise RuntimeError('Native controller constructor returned a foreign object')
            self.constructed = True
            self._check_canaries()
            if self.get_flag() != 0:
                raise RuntimeError('Native fresh controller flag differs')
        except BaseException:
            self.poisoned = True
            raise

    def _check_canaries(self):
        if C.string_at(self.pointer - 32, 32) != b'\xa5' * 32 or C.string_at(self.pointer + 1200, 32) != b'\xa5' * 32:
            raise RuntimeError('Native controller object boundary corrupted')

    def _check(self):
        self.code._check()
        if self.closed or self.poisoned or (not self.constructed):
            raise RuntimeError('Native controller is not alive')
        self._check_canaries()

    def get_flag(self):
        self._check()
        return self.code.getter(self.pointer)

    def set_flag(self, value):
        self._check()
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError('Native controller flag must be uint8')
        self.code.setter(self.pointer, value)
        if self.get_flag() != value:
            raise RuntimeError('Original controller setter/getter disagree')

    def snapshot(self):
        self._check()
        raw = C.string_at(self.pointer, 1200)
        return dict(flag=self.get_flag(), mode=struct.unpack_from('<I', raw, 0)[0], enabled=raw[4], constructor_bytes_0c_11=raw[12:18].hex(), clock_ticks=[struct.unpack_from('<q', raw, x)[0] for x in (24, 48)], frequency=C.c_int64.from_address(self.code.pointer + 12288).value, pointers_448_450=list(struct.unpack_from('<QQ', raw, 1096)), tail_4a0_4a4=list(struct.unpack_from('<iI', raw, 1184)), canaries_intact=True, constructor_executed=True, full_controller_lifecycle_proven=False)

    def close(self):
        if self.closed:
            return
        self._check()
        self.code.kernel.DeleteCriticalSection(self.pointer + 1120)
        self._check_canaries()
        self.closed = True
        self.code.objects.discard(self)
        self.pointer = 0
        self.storage = None

"""Original EXE subscriber routines with owned executable/unwind lifetime.

This component executes the captured dispatcher and its erase helper without
rewriting their instructions. It does not install Engine Events factories or
create subscriptions. Its internal entry requires caller-owned, validated native
row/list/callback storage and is currently exercised only in isolated diagnostics.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import ctypes as C
import hashlib, json, os, struct, threading
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_subscriber_code.py')))).resolve().parents[1]
SOURCE_SHA = '0c3f9d6c4c744a6e87cc64c8bfc1af8b5d367b0f32a0872981d9645a58625804'
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_CAPTURED_EXE_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\CivilizationVI.exe"
BODY_SHA = {618288: '4e17440fadb1c1e2de92f6c92fbbde66786772148a98eb87f2b23c6c79467c08', 901328: '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca'}

def source_profile(root=ROOT):
    raw = _resolve_resource_path(_resolve_resource_path(Path(root)) / 'work/native-subscribers899/capture899.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Subscriber source changed')
    p = json.loads(raw)
    if p['image']['sha256'] != EXE_SHA or p['rip_relative_data_dependencies']:
        raise ValueError('Subscriber source image/dependencies changed')
    return p

def _verify_captured_exe_identity(source, execution_image):
    if execution_image is None:
        return False
    from civ6_host.runtime.execution_images import identity
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
    selected = identity(execution_image)
    if selected['reference_core_sha256'] not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Subscriber capture requires a registered expansion execution profile')
    if (source.get('image', {}).get('path') != _CAPTURED_EXE_PATH
            or source.get('image', {}).get('sha256') != EXE_SHA):
        raise ValueError('Pinned subscriber capture executable identity differs')
    return True

def build_image(p):
    """Preserve code-relative displacements; relocate only unwind table RVAs."""
    if set(p['functions']) != {hex(r) for r in BODY_SHA}:
        raise ValueError('Subscriber function set changed')
    minimum = min(BODY_SHA) & ~4095
    code_size = max((v['end_rva'] for v in p['functions'].values())) - minimum + 4095 & ~4095
    code = bytearray(b'\xcc' * code_size)
    for key, f in p['functions'].items():
        rva = int(key, 16)
        raw = bytes.fromhex(f['raw_hex'])
        if hashlib.sha256(raw).hexdigest() != BODY_SHA[rva] or f['begin_rva'] != rva or len(raw) != f['end_rva'] - rva:
            raise ValueError('Subscriber instruction body changed')
        code[rva - minimum:rva - minimum + len(raw)] = raw
    rows = p['unwind_rows']
    starts = {r['begin_rva']: r for r in rows}
    if len(rows) != 11 or len(starts) != len(rows):
        raise ValueError('Subscriber unwind row set changed')
    unwind = bytearray()
    offsets = {}
    for r in rows:
        while len(unwind) % 4:
            unwind.append(0)
        offsets[r['unwind_source_rva']] = code_size + len(unwind)
        unwind.extend(bytes.fromhex(r['unwind_hex']))
    if len(offsets) != len(rows):
        raise ValueError('Subscriber duplicate unwind data')
    table = []
    for r in rows:
        raw = bytes.fromhex(r['unwind_hex'])
        flags = raw[0] >> 3
        head = 4 + (raw[2] + 1 & ~1) * 2
        if raw[0] & 7 != 1 or flags not in (0, 4) or len(raw) != head + (12 if flags == 4 else 0):
            raise ValueError('Subscriber unwind encoding changed')
        if flags == 4:
            parent = struct.unpack_from('<III', raw, head)
            if list(parent) != r['chain'] or parent[0] not in starts:
                raise ValueError('Subscriber unwind chain escapes code')
            other = starts[parent[0]]
            if (other['end_rva'], other['unwind_source_rva']) != parent[1:]:
                raise ValueError('Subscriber unwind parent mismatch')
            pos = offsets[r['unwind_source_rva']] - code_size + head
            struct.pack_into('<III', unwind, pos, parent[0] - minimum, parent[1] - minimum, offsets[parent[2]])
        elif r['chain'] is not None:
            raise ValueError('Unexpected subscriber chain')
        if not any((f['begin_rva'] <= r['begin_rva'] < r['end_rva'] <= f['end_rva'] for f in p['functions'].values())):
            raise ValueError('Subscriber unwind range outside code')
        table.append((r['begin_rva'] - minimum, r['end_rva'] - minimum, offsets[r['unwind_source_rva']]))
    table.sort()
    if any((a[1] > b[0] for a, b in zip(table, table[1:]))):
        raise ValueError('Overlapping subscriber unwind ranges')
    data_size = len(unwind) + 4095 & ~4095
    return {'minimum_rva': minimum, 'code_size': code_size, 'data_size': data_size, 'image': bytes(code + unwind + bytes(data_size - len(unwind))), 'table': table}

class RuntimeFunction(C.Structure):
    _fields_ = [('BeginAddress', C.c_uint32), ('EndAddress', C.c_uint32), ('UnwindData', C.c_uint32)]

class NativeSubscriberCode:
    """Thread-affine original code owner; no hidden empty-subscriber profile."""

    def __init__(self, *, root=ROOT, execution_image=None):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise RuntimeError('Original subscriber code needs Win64')
        self.source = source_profile(root)
        self.layout = build_image(self.source)
        selected_current = _verify_captured_exe_identity(self.source, execution_image)
        self.owner = threading.get_ident()
        self.busy = False
        self.closed = False
        self.pointer = 0
        self.registered = False
        if not selected_current:
            original = _resolve_resource_path(_resolve_resource_path(Path(self.source['image']['path']))).read_bytes()
            if hashlib.sha256(original).hexdigest() != EXE_SHA:
                raise ValueError('Installed EXE identity changed')
            for f in self.source['functions'].values():
                raw = bytes.fromhex(f['raw_hex'])
                offset = f['file_offset']
                if original[offset:offset + len(raw)] != raw:
                    raise ValueError('Subscriber code differs from installed original')
            for r in self.source['unwind_rows']:
                raw = bytes.fromhex(r['unwind_hex'])
                offset = r['unwind_file_offset']
                if original[offset:offset + len(raw)] != raw:
                    raise ValueError('Subscriber unwind differs from installed original')
        k = self.kernel = C.WinDLL('kernel32', use_last_error=True)
        n = self.ntdll = C.WinDLL('ntdll', use_last_error=True)
        k.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
        k.VirtualAlloc.restype = C.c_void_p
        k.VirtualProtect.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.POINTER(C.c_uint32)]
        k.VirtualProtect.restype = C.c_int
        k.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
        k.VirtualFree.restype = C.c_int
        k.GetCurrentProcess.argtypes = []
        k.GetCurrentProcess.restype = C.c_void_p
        k.FlushInstructionCache.argtypes = [C.c_void_p, C.c_void_p, C.c_size_t]
        k.FlushInstructionCache.restype = C.c_int
        n.RtlAddFunctionTable.argtypes = [C.POINTER(RuntimeFunction), C.c_uint32, C.c_uint64]
        n.RtlAddFunctionTable.restype = C.c_uint8
        n.RtlDeleteFunctionTable.argtypes = [C.POINTER(RuntimeFunction)]
        n.RtlDeleteFunctionTable.restype = C.c_uint8
        n.RtlLookupFunctionEntry.argtypes = [C.c_uint64, C.POINTER(C.c_uint64), C.c_void_p]
        n.RtlLookupFunctionEntry.restype = C.POINTER(RuntimeFunction)
        self.table = (RuntimeFunction * len(self.layout['table']))(*(RuntimeFunction(*r) for r in self.layout['table']))
        try:
            self.pointer = k.VirtualAlloc(None, len(self.layout['image']), 12288, 4)
            if not self.pointer:
                raise C.WinError(C.get_last_error())
            C.memmove(self.pointer, self.layout['image'], len(self.layout['image']))
            old = C.c_uint32()
            if not k.VirtualProtect(self.pointer, self.layout['code_size'], 32, C.byref(old)):
                raise C.WinError(C.get_last_error())
            if not k.VirtualProtect(self.pointer + self.layout['code_size'], self.layout['data_size'], 2, C.byref(old)):
                raise C.WinError(C.get_last_error())
            if not k.FlushInstructionCache(k.GetCurrentProcess(), self.pointer, self.layout['code_size']):
                raise C.WinError(C.get_last_error())
            if not n.RtlAddFunctionTable(self.table, len(self.table), self.pointer):
                raise RuntimeError('Subscriber unwind registration failed')
            self.registered = True
            self._verify_unwind()
            address = self.pointer + 901328 - self.layout['minimum_rva']
            self._entry = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p)(address)
        except BaseException:
            self.close()
            raise

    def _check(self):
        if self.closed or self.owner != threading.get_ident():
            raise RuntimeError('Subscriber code closed or foreign thread')

    def _verify_unwind(self):
        for expected in self.layout['table']:
            image_base = C.c_uint64()
            p = self.ntdll.RtlLookupFunctionEntry(self.pointer + expected[0], C.byref(image_base), None)
            if not p or image_base.value != self.pointer or (p.contents.BeginAddress, p.contents.EndAddress, p.contents.UnwindData) != expected:
                raise RuntimeError('Registered subscriber unwind lookup differs')

    def _dispatch_owned(self, payload_address, row_address):
        """Internal ABI entry. Caller must retain and validate all pointer owners."""
        self._check()
        if self.busy:
            raise RuntimeError('Nested subscriber entry is not yet admitted by this owner')
        if any((type(p) is not int or p <= 0 for p in (payload_address, row_address))):
            raise ValueError('Invalid native owned pointer')
        self.busy = True
        try:
            self._entry(payload_address, row_address)
        finally:
            self.busy = False

    def close(self):
        if self.closed:
            return
        if self.owner != threading.get_ident() or self.busy:
            raise RuntimeError('Cannot release active/foreign subscriber code')
        if self.registered:
            if not self.ntdll.RtlDeleteFunctionTable(self.table):
                raise RuntimeError('Subscriber unwind deregistration failed; code retained')
            self.registered = False
        if self.pointer:
            if not self.kernel.VirtualFree(self.pointer, 0, 32768):
                raise C.WinError(C.get_last_error())
            self.pointer = 0
        self.closed = True

"""Use the retained native AUX map converter for BBG trade property tables."""
from contextlib import contextmanager
import ctypes as C
from pathlib import Path

from .a0_policy_unlock_current import _require_image, CURRENT_CORE_SHA256, CURRENT_EXE_SHA256
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('evidence/host-xp2-bbg-trade-table-variant-source.json',
          '797dc64de1bbb8db7862535c99857afc0baa04814c029b4c06cc499195dd06ca')
_SCALAR_SLOT = 0xA0 // 8


def matches_active_binding(lease, table, snapshot):
    continuation = getattr(lease, 'continuation', None)
    feedback = getattr(continuation, 'trade_feedback', None)
    reader = getattr(feedback, 'table_reader', None)
    if (type(reader) is not TradeTableVariantReader or reader.continuation is not continuation
            or reader.active_lease is not lease or reader.host is not lease.host
            or table is not lease.host.aux_vtable or snapshot[_SCALAR_SLOT] != reader.original_address
            or reader.scalar.function is not reader.push or reader.scalar.address != reader.push_address):
        return False
    expected = snapshot[:_SCALAR_SLOT] + (reader.push_address,) + snapshot[_SCALAR_SLOT + 1:]
    return tuple(table) == expected


def source_dependencies(*, execution_image):
    _require_image(execution_image)
    proof = _source(SOURCE)
    selector = proof['native_selector']
    if (proof['schema'] != 'civ6-host.xp2-bbg-trade-table-variant-source.v1'
            or proof['exe_sha256'] != CURRENT_EXE_SHA256 or proof['core_sha256'] != CURRENT_CORE_SHA256
            or (selector['tag'], selector['flags'], selector['size'], selector['pointer_offset']) !=
                (10, '0x05000000', 0, 8)
            or selector['case_entry']['rva'] != '0xdb65a8'
            or selector['branch']['rva'] != '0xdb651a' or selector['map_to_table']['rva'] != '0xdb5d30'
            or selector['names'] is not True or proof['bridge_import_count'] != 0):
        raise ValueError('BBG trade table converter source differs')
    root = resource_root()
    binary = resolve_path(root / proof['bridge']['path'])
    source = Path(__file__).resolve().parents[3] / 'native/xp2_trade_table_variant.c'
    return {root / SOURCE[0]: SOURCE[1], binary: proof['bridge']['sha256'],
            source: proof['source']['sha256']}


class TradeTableVariantReader:
    def __init__(self, continuation):
        from .script_scalar_service import ScalarService
        from .script_map_service import MapService
        from .source_verification import file_sha256

        host = continuation.prefix.host
        scalar, maps = host._scalar_service_owner, host._map_service_owner
        if (type(scalar) is not ScalarService or type(maps) is not MapService or scalar.closed or maps.closed
                or scalar.runtime is not continuation.runtime or maps.runtime is not continuation.runtime
                or maps.adapter.allow_nested_maps is not True):
            raise ValueError('BBG trade requires the retained scalar and map converters')
        image = continuation.owner.core._civ6_host_execution_image
        pins = source_dependencies(execution_image=image)
        for path, digest in pins.items():
            if file_sha256(path) != digest:
                raise ValueError('BBG trade table converter bytes changed')
        binary = next(path for path in pins if path.suffix == '.dll')
        self.library = C.WinDLL(str(binary.resolve(strict=True)))
        self.bind = self.library.Civ6HostBindTradeTableVariant
        self.bind.argtypes, self.bind.restype = [C.c_void_p] * 3, C.c_int
        self.unbind = self.library.Civ6HostUnbindTradeTableVariant
        self.unbind.argtypes, self.unbind.restype = [C.c_void_p], C.c_int
        self.push = self.library.Civ6HostPushTradeTableVariant
        self.push.argtypes, self.push.restype = [C.c_void_p] * 3, None
        self.push_address = C.cast(self.push, C.c_void_p).value
        self.scalar, self.maps, self.host = scalar, maps, host
        self.continuation = continuation
        self.original_address = scalar.address
        self.active_lease = None

    @contextmanager
    def active(self):
        import threading

        host, scalar, maps = self.host, self.scalar, self.maps
        original, address = scalar.function, scalar.address
        map_slot, map_address, _, map_function = maps.bindings[0]
        if (host._scalar_service_owner is not scalar or host._map_service_owner is not maps
                or scalar.closed or maps.closed or threading.get_ident() != scalar.thread
                or self.active_lease is not None or address != self.original_address
                or host.aux_vtable[_SCALAR_SLOT] != address or C.cast(original, C.c_void_p).value != address
                or map_slot != 0xA8 or host.aux_vtable[map_slot // 8] != map_address
                or C.cast(map_function, C.c_void_p).value != map_address):
            raise ValueError('BBG trade converter lost its live auxiliary owner')
        owner = C.addressof(host.aux_object)
        if self.bind(owner, address, map_address) != 1:
            raise RuntimeError('BBG trade table converter is already active')
        scalar.function, scalar.address = self.push, self.push_address
        host.aux_vtable[_SCALAR_SLOT] = self.push_address
        self.active_lease = self.continuation.lease
        try:
            yield
        finally:
            expected = (host.aux_vtable[_SCALAR_SLOT] == self.push_address and scalar.function is self.push
                        and scalar.address == self.push_address and self.active_lease is self.continuation.lease)
            self.active_lease = None
            host.aux_vtable[_SCALAR_SLOT] = address
            scalar.function, scalar.address = original, address
            if self.unbind(owner) != 1 or not expected:
                raise RuntimeError('BBG trade table converter ownership changed')

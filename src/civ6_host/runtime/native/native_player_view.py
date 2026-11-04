"""Initialize and refresh GameCore's player-scoped native UI cache.

Initial population defaults to the service-owned public cache facade. An
explicit internal diagnostic profile remains available for controlled probes.
The kind-4 descriptor asks Core to refresh its own cache from the live Game
singleton; neither step reproduces the EXE's normal notification cadence.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
import threading
from civ6_host.runtime.native.native_host import virtual
from civ6_host.runtime.native.native_setup import local_reader
OUTER_VTABLE_RVA = 7987232
OUTER_PUBLISH_SLOT = 400
OUTER_PUBLISH_RVA = 4388448
SERVICE_GLOBAL_RVA = 9155584
SERVICE_VTABLE_RVA = 8155464
SERVICE_ENSURE_CACHE_SLOT = 8
SERVICE_ENSURE_CACHE_RVA = 34208
SERVICE_CACHE_OWNER_SLOT = 128
SERVICE_CACHE_OWNER_GETTER_RVA = 7551424
SERVICE_PUBLISH_SLOT = 168
SERVICE_PUBLISH_RVA = 34464
CACHE_GAME_VTABLE_RVA = 7760496
CACHE_GAME_MAP_VIEW_OFFSET = 6000
CACHE_MAP_VIEW_VTABLE_RVA = 7734504
GAME_GLOBAL_RVA = 9156424
GAME_FACADE_GETTER_SLOT = 160
GAME_FACADE_GETTER_RVA = 4381904
GAME_FACADE_VTABLE_RVA = 7990488
GAME_FACADE_RELEASE_SLOT = 8
GAME_FACADE_RELEASE_RVA = 4409168
GAME_FACADE_POPULATE_SLOT = 56
GAME_FACADE_POPULATE_RVA = 4410928
INITIALIZATION_PROFILES = frozenset(('public-cache-facade', 'explicit-internal-diagnostic'))

def kind4_descriptor() -> bytes:
    """Return the 8-byte descriptor consumed by Core's kind-4 branch.

    The handler reads only the uint16 at byte offset 2. All other descriptor
    bytes are explicit zero padding in this diagnostic profile.
    """
    return struct.pack('<HHI', 0, 4, 0)

class NativePlayerViewPublisher:
    """Ask Core to refresh its existing UI cache from the live Game object."""

    def __init__(self, core, context, emit, read=None, initialization_profile='public-cache-facade', *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
        if initialization_profile not in INITIALIZATION_PROFILES:
            raise ValueError('Unrecognized or unavailable player-view initialization profile')
        from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi
        self.cache_abi = loaded_cache_abi(core_sha256)
        self.core = core
        self.context = int(context)
        self.emit = emit
        self.read = local_reader() if read is None else read
        self.initialization_profile = initialization_profile
        self._facades = None
        self._closed = False
        self.native_cache_gate = False
        self.cache_map_snapshot = None
        self.full_facade_initialization_reproduced = False
        self._owner_thread_id = threading.get_ident()

    def _set_cache_gate(self, enabled):
        self.native_cache_gate = enabled

    def read_retained_game_value(self):
        """EXE F1420 equivalent on the facade retained by public initialization."""
        if self._closed or self.initialization_profile != 'public-cache-facade' or self.full_facade_initialization_reproduced is not True or (self.native_cache_gate is not True) or (threading.get_ident() != self._owner_thread_id):
            raise RuntimeError('Retained Game getter requires a live initialized public facade')
        from civ6_host.runtime.native.native_retained_game_getter import read_retained_game_value
        from civ6_host.runtime.native.native_retained_game_getter import PINNED_EVIDENCE_SHA256
        result = read_retained_game_value(self._facades, self.read, core_sha256=self.cache_abi.core_sha256)
        self.emit('native_retained_game_getter_returned', exe_rva='0xf1420', core_rva='0x434b00', facade_slot='0x128', result_signed32=result, source_sha256=PINNED_EVIDENCE_SHA256, native_call_executed=True, semantic_player_identity_assumed=False, eligible_for_training=False)
        return result

    def close(self):
        """Release cache wrappers before Core services or the context are destroyed."""
        if self._closed:
            return
        if getattr(self, '_loaded_cache_candidate_owner', None) is not None:
            self._loaded_cache_candidate_owner.authorize_publisher_close(self)
        try:
            if self._facades is not None:
                self._facades.close()
        finally:
            self._closed = True

    def query_combat_owner(self, signed_owner):
        """EXE F16E0 on the already retained native facade, never local-player inference."""
        if self._closed or self.initialization_profile != 'public-cache-facade' or self.full_facade_initialization_reproduced is not True or (self.native_cache_gate is not True) or (threading.get_ident() != self._owner_thread_id):
            raise RuntimeError('Combat predicate requires a live initialized public facade')
        if self.cache_abi.core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            raise ValueError('XP1 public combat cache queries are not qualified')
        from civ6_host.runtime.native.native_combat_owner_predicate import query_owner
        from civ6_host.runtime.native.native_combat_map_owner import PROOF_SHA256
        result = query_owner(self._facades, signed_owner, self.read)
        self.emit('native_combat_owner_predicate_returned', signed_owner=signed_owner, value=result, source_proof_sha256=PROOF_SHA256, facade_slot='0x130', native_call_executed=True, eligible_for_training=False)
        return result

    def _validate(self):
        from civ6_host.runtime.loaded_cache_profiles import service_state
        return service_state(self.core._handle, self.context, self.read, self.cache_abi)

    def publish(self, *, publication_owner=None):
        """Refresh the native UI map view once using the kind-4 Core event."""
        if self._closed:
            raise RuntimeError('Native player-view publisher is closed')
        target_rva = OUTER_PUBLISH_RVA
        if self.cache_abi.core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            from civ6_host.runtime.xp1_cache_publication import validate_publisher
            if publication_owner is None:
                publication_owner = getattr(self, '_xp1_continuation', None)
            target_rva = validate_publisher(self, publication_owner)
        elif publication_owner is not None:
            raise ValueError('Base publication does not accept an XP1 candidate owner')
        service, game = self._validate()
        ensure = virtual(self.core, service, SERVICE_ENSURE_CACHE_SLOT, self.cache_abi.service_ensure_rva, None)
        ensure(service)
        owner = struct.unpack('<Q', self.read(service + 8, 8))[0]
        if not owner:
            raise RuntimeError('GameCore did not create its UI cache owner')
        get_owner = virtual(self.core, service, SERVICE_CACHE_OWNER_SLOT, self.cache_abi.service_owner_rva, C.c_void_p)
        if int(get_owner(service) or 0) != owner:
            raise RuntimeError('GameCore cache-owner getter disagrees with its owner slot')
        owner_vtable = struct.unpack('<Q', self.read(owner, 8))[0]
        if owner_vtable != self.core._handle + self.cache_abi.cache_owner_vtable_rva:
            raise ValueError('Unexpected Cache_Game_Instance vtable')
        view = struct.unpack('<Q', self.read(owner + self.cache_abi.map_view_offset, 8))[0]
        if not view:
            raise RuntimeError('GameCore UI map view is unavailable')
        view_vtable = struct.unpack('<Q', self.read(view, 8))[0]
        if view_vtable != self.core._handle + self.cache_abi.map_view_vtable_rva:
            raise ValueError('Unexpected Cache_Lua_IMap vtable')
        manager = owner + 56
        table = struct.unpack('<Q', self.read(manager + 32, 8))[0]
        initialized = self.read(manager, 1)
        if initialized not in (b'\x00', b'\x01'):
            raise RuntimeError('Unrecognized native visibility-cache initialization flag')
        if table and initialized != b'\x01':
            raise RuntimeError('Native visibility cache table exists without its initialized flag')
        if not table:
            if publication_owner is not None:
                raise ValueError('XP1 publication needs the native populated visibility table')
            if initialized != b'\x00':
                raise RuntimeError('Partially initialized native visibility cache')
            if self.initialization_profile == 'public-cache-facade':
                from civ6_host.runtime.native.native_ui_cache_facades import NativeUiCacheFacades
                from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
                if self._facades is not None:
                    raise RuntimeError('Public cache facades exist without an initialized table')
                backend = NativeCacheFacadeBackend(self.core, self._set_cache_gate, context_alive=lambda: not self._closed, read=self.read)
                self._facades = NativeUiCacheFacades(backend, self.context)
                facade_owner = struct.unpack('<Q', self.read(self._facades.game_facade + 16, 8))[0]
                if facade_owner != owner:
                    raise RuntimeError('Public UI cache facade does not reference the service cache owner')
                self.emit('before_native_player_view_initial_population', outer_game_slot='0xa0', game_facade_slot='0x38', core_wrapper_rva=hex(GAME_FACADE_POPULATE_RVA), source_game_pointer=game, cache_owner_borrowed=True, entry_profile=self.initialization_profile, normal_exe_cadence_reproduced=False, eligible_for_training=False)
                copied = self._facades.refresh()
                self.cache_map_snapshot = bytes(copied.output)
                if self.native_cache_gate is not True:
                    raise RuntimeError('Source cache initialization did not enable its host gate')
                self.full_facade_initialization_reproduced = True
                self.emit('native_public_cache_facades_initialized', source_enable_rva='0xf15c0', outer_borrowed=True, retained_outer_slots=['0xa0', '0xb0', '0xd0'], copied_bytes=len(copied.output), copied_hex=copied.output.hex(), native_copy_return=copied.copied_value, retained_b0_result=bool(self._facades.cache_b0_result), retained_c0_result=bool(self._facades.cache_c0_result), full_facade_sequence_returned=True, host_cache_gate=True, original_exe_caller_cadence=False, eligible_for_training=False)
            else:
                self.emit('before_native_player_view_initial_population', core_method_rva='0x74800', source_game_pointer=game, cache_owner_borrowed=True, entry_profile=self.initialization_profile, normal_exe_entry_reproduced=False, eligible_for_training=False)
                populate = C.WINFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_uint8)(self.core._handle + 477184)
                populate(owner, game, 1)
            if self.read(manager, 1) != b'\x01' or not struct.unpack('<Q', self.read(manager + 32, 8))[0]:
                raise RuntimeError('Core did not initialize the native visibility cache')
            self.emit('native_player_view_initial_population_returned', records_created_by_core=True, entry_profile=self.initialization_profile, normal_exe_cadence_reproduced=False, eligible_for_training=False)
        descriptor = C.create_string_buffer(kind4_descriptor(), 8)
        pointer = C.addressof(descriptor)
        if self.read(pointer, 8) != kind4_descriptor():
            raise RuntimeError('Kind-4 descriptor storage changed')
        publish = virtual(self.core, self.context, OUTER_PUBLISH_SLOT, target_rva, None, C.c_void_p, C.c_uint8)
        self.emit('before_native_player_view_publish', event_kind=4, descriptor_hex=kind4_descriptor().hex(), descriptor_bytes=8, source_game_pointer=game, service_borrowed=True, cache_owner_borrowed=True, profile='Explicit one-shot UI cache refresh; EXE cadence not reproduced', eligible_for_training=False)
        if publication_owner is not None:
            from civ6_host.runtime.xp1_cache_publication import before_native
            before_native(self, publication_owner)
        publish(self.context, pointer, 1)
        width, height, plot_count = struct.unpack('<iii', self.read(view + 40, 12))
        if width <= 0 or height <= 0 or plot_count != width * height:
            raise RuntimeError('Core UI map cache did not publish a valid map view')
        self.emit('native_player_view_published', width=width, height=height, plot_count=plot_count, source_game_pointer=game, cache_owner_borrowed=True, descriptor_owner='caller stack', action_applied=False, eligible_for_training=False)
        result = (width, height, plot_count)
        if publication_owner is not None:
            from civ6_host.runtime.xp1_cache_publication import after_native
            after_native(self, publication_owner, result)
        return result

"""Explicit post-Load cache-population diagnostic; never advances a game turn.

This reduced source-scoped sequence is not the complete EXE load lifecycle.
The worker retains all owners and stops without +160, +190, Update or Destroy.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from civ6_host.runtime.native import native_checkpoint_load as load
PLAN_PATH = 'work/native-checkpoint-postload-plan367.json'
PLAN_SHA256 = 'bbaff3e0d34a903bf26ba956e3f5ae1cd06ff55ba8f974ac5602628f412ccc22'
FACADES_PATH = 'work/native-checkpoint-postload-facades-audit358.json'
FACADES_SHA256 = '31fcaf224df55860287fa63c2fe6acd32bcddea0c9ad6614ae0e0172cca321e5'
_ATTEMPTS = {}

def verify_source(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi, source
    abi = loaded_cache_abi(core_sha256)
    if abi.core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        return source(core_sha256=core_sha256)
    plan = load.pinned_json(PLAN_PATH, PLAN_SHA256)
    proof = load.pinned_json(FACADES_PATH, FACADES_SHA256)
    for document in (plan, proof):
        for path, pin in document['parents'].items():
            load.pinned_json(path, pin)
    if plan['abi']['notification_enable']['target_rva'] != '0x42dca0' or plan['abi']['notification_enable']['signature'] != 'uint32(this:void*, new_byte:uint8)' or proof['images']['core']['sha256'] != load.provider.CORE_SHA256 or (proof['binding']['outer1A0']['width'] != 1) or (proof['binding']['outer1A0']['allowed_future_profile_argument'] != 1):
        raise ValueError('Post-load facade source contract changed')
    return proof

def check_live_code(base, read, proof, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi, verify_live
    abi = loaded_cache_abi(core_sha256)
    if abi.core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        return verify_live(base, read, proof, core_sha256=core_sha256)
    captured = list(load.instructions(proof['captures']['core']))
    if not captured:
        raise ValueError('Post-load facade proof has no addressed Core instructions')
    for ins in captured:
        rva = int(ins['va'], 16) - load.CORE_BASE
        raw = bytes.fromhex(ins['bytes'])
        if rva < 0 or not raw or read(base + rva, len(raw)) != raw:
            raise ValueError('Post-load live Core instruction differs at ' + hex(rva))
    for slot, target in ((416, 4381856), (160, 4381904), (176, 4381968), (208, 4382096)):
        if struct.unpack('<Q', read(base + 7987232 + slot, 8))[0] != base + target:
            raise ValueError('Post-load facade virtual slot changed')

def run_sequence(backend, emit):
    """Injected orchestration seam. Only NativeFacadeBackend calls native code."""
    if backend.attempted:
        raise RuntimeError('Post-load cache attempt cannot be retried')
    backend.attempted = True
    try:
        backend.enter()
        identity = backend.observe()
        before = backend.jobs_snapshot('before')
        previous = backend.enable_notifications()
        if type(previous) is not int or not 0 <= previous <= 255:
            raise ValueError('Native notification previous value is not a byte')
        backend.acquire_facades()
        copied, returned = backend.refresh_facades()
        if type(copied) is not bytes or len(copied) != 28 or type(returned) is not int or (not 0 <= returned <= 4294967295):
            raise ValueError('Native cache copy result is not its exact 28-byte/DWORD contract')
        emit('native_checkpoint_postload_cache_copy_returned', notification_previous_byte=previous, copied_hex=copied.hex(), native_copy_return=returned, validation_completed=False, eligible_for_training=False)
        backend.bind_cache(copied)
        after = backend.jobs_snapshot('after')
        if before != after:
            raise RuntimeError('Post-load cache population changed the scheduler')
        if backend.observe() != identity:
            raise RuntimeError('Post-load cache population changed context ownership')
        result = dict(cache_facades_populated=True, cache_snapshot_hex=copied.hex(), native_copy_return=returned, notification_previous_byte=previous, jobs_identical=True, post160_called=False, game_update_called=False, publish190_called=False, context_destroyed=False, full_exe_load_lifecycle_reproduced=False, reset_validated=False, continuation_validated=False, scheduler_load_ledger_postrun_required=True, owners_retained=True, controlled_stop_required=True, eligible_for_training=False)
        if getattr(backend, 'publication_mode', 'public') == 'candidate':
            result.update(candidate_native_cache_only=True, public_cache_gate_enabled=False, post160_admitted=False)
        backend.finish()
        backend.completed_result = result
        emit('native_checkpoint_postload_facades_observed', **result)
        return result
    except BaseException:
        backend.poison()
        raise

class NativeFacadeBackend:

    def __init__(self, owner, load_result, *, publication_mode='public'):
        if type(owner) is not load.NativeLoadBackend:
            raise TypeError('Post-load facades require the retained native Load owner')
        self.owner, self.load_result = (owner, load_result)
        self.attempted = False
        self.publisher = None
        self.configure_publication(publication_mode)

    def configure_publication(self, publication_mode):
        from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi, require_mode
        self.cache_abi = loaded_cache_abi(self.owner.load_abi.core_sha256)
        require_mode(self.cache_abi, publication_mode)
        self.publication_mode = publication_mode
        self.publication_owner = None
        self.proof = verify_source(core_sha256=self.cache_abi.core_sha256)

    def enter(self):
        b = self.owner
        b.check_thread()
        inputs = load.validated_owner_inputs(b)
        if load._RETAINED.get((id(b.core), b.context)) is not b or b.busy or b.stage != 'observed-awaiting-post160' or (b.reader is None) or (b.reader.transport.closed is not True) or (b.reader.transport.cursor != len(inputs.game)):
            raise RuntimeError('Post-load cache entry lacks its exclusive completed raw Load')
        result = self.load_result
        receipt = result.get('receipt', {})
        if result.get('raw_component_load_observed') is not True or result.get('controlled_stop_required') is not True or result.get('post160_called') is not False or (type(receipt.get('status')) is not int) or (receipt['status'] != 0) or (receipt.get('bytes_consumed') != len(inputs.game)) or (receipt.get('scheduler_ledger_reconciliation_pending') is not True):
            raise RuntimeError('Post-load cache entry has an unverified raw Load receipt')
        p = b.prefix
        d = p.deferred_events
        from civ6_host.runtime.loaded_cache_publication import initial_publisher_state
        initial_publisher_state(p, self.cache_abi.core_sha256)
        check_live_code(b.core._handle, b.runtime.read, self.proof, core_sha256=self.cache_abi.core_sha256)
        b.busy = True
        self.begin_publication_owner()

    def begin_publication_owner(self):
        if self.publication_mode == 'candidate':
            from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
            if hasattr(self.owner, '_saved_load_job_cache_owner'):
                raise RuntimeError('Loaded-cache scheduler lease is already installed')
            self.publication_owner = LoadedCachePublication(self)
            self.owner._saved_load_job_cache_owner = self.publication_owner
            from civ6_host.runtime.xp1_load_capability import begin_cache_source_scope
            begin_cache_source_scope(self)

    def observe(self):
        b = self.owner
        b.check_thread()
        topology = b.topology(game_required=True)
        if topology != b.bound_identity or b.game_flag() != 1:
            raise RuntimeError('Restored Game/provider identity changed')
        b.owner.require_context(b.core._handle, b.context)
        b.control(empty=True)
        return (b.context, topology['inner'], topology['game'], topology['provider'], b.owner.pointer, b.prefix.game_child)

    def jobs_snapshot(self, phase):
        return self.owner.jobs_snapshot(phase)

    def enable_notifications(self):
        b = self.owner
        if self.publication_owner is not None:
            self.publication_owner._check()
        before = b.runtime.read(b.core._handle + self.cache_abi.notification_byte_rva, 1)[0]
        returned = int(C.WINFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint8)(b.core._handle + self.cache_abi.notification_rva)(b.context, 1))
        if returned != before or b.runtime.read(b.core._handle + self.cache_abi.notification_byte_rva, 1) != b'\x01':
            raise RuntimeError('Native notification byte transition differs from its source')
        if self.publication_owner is not None:
            self.publication_owner._check()
        return returned

    def acquire_facades(self):
        from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
        from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
        from civ6_host.runtime.native.native_ui_cache_facades import NativeUiCacheFacades
        b = self.owner
        self.publisher = NativePlayerViewPublisher(b.core, b.context, b.emit, read=b.runtime.read, core_sha256=self.cache_abi.core_sha256)
        b.prefix.view_publisher = self.publisher
        backend = NativeCacheFacadeBackend(b.core, self.publisher._set_cache_gate, context_alive=lambda: not b.destroyed and (not b.poisoned), read=b.runtime.read, core_sha256=self.cache_abi.core_sha256, publication_owner=self.publication_owner)
        if self.publication_owner is not None:
            self.publisher._loaded_cache_candidate_owner = self.publication_owner
            self.publication_owner.attach(self.publisher, backend)
        facades = NativeUiCacheFacades.__new__(NativeUiCacheFacades)
        self.publisher._facades = facades
        facades.__init__(backend, b.context, core_sha256=self.cache_abi.core_sha256)

    def refresh_facades(self):
        copied = self.publisher._facades.refresh(public_gate=self.publication_mode == 'public')
        return (copied.output, copied.copied_value)

    def bind_cache(self, copied):
        from civ6_host.runtime.loaded_cache_profiles import validate_copy
        b, p = (self.owner, self.publisher)
        expected = self.load_result['readback']
        state = validate_copy(b.core._handle, b.context, b.runtime.read, self.cache_abi, p._facades, copied, expected_game=b.bound_identity['game'], expected_dimensions=(expected['width'], expected['height']))
        if self.publication_mode == 'candidate':
            if p.native_cache_gate is not False or self.publication_owner.copied is not True:
                raise RuntimeError('Candidate publication opened a public gate or lacks its native copy')
            self.publication_owner.require(p._facades.backend, p._facades)
            p.cache_map_snapshot = copied
            self.validated_candidate_cache = state
            return
        if p.native_cache_gate is not True:
            raise RuntimeError('Native facade refresh did not enable its cache gate')
        p.cache_map_snapshot = copied
        p.full_facade_initialization_reproduced = True
        d = b.prefix.deferred_events
        d.admit_initialized_ui_cache_profile('public-cache-facade', state['dimensions'], full_facade_initialization_reproduced=True, cache_map_snapshot=copied)
        d.bind_retained_game_getter(p.read_retained_game_value)
        d.bind_retained_combat_predicate(p.query_combat_owner)
        d.bind_natural_wonder_facades(p)

    def finish(self):
        from civ6_host.runtime.xp1_load_capability import finish_cache_source_scope
        finish_cache_source_scope(self)
        if self.publication_mode == 'candidate':
            if getattr(self.owner, '_saved_load_job_cache_owner', None) is not self.publication_owner:
                raise RuntimeError('Loaded-cache scheduler lease was replaced')
            del self.owner._saved_load_job_cache_owner
        self.owner.stage = 'facades-candidate-observed' if self.publication_mode == 'candidate' else 'facades-observed-awaiting-post160'
        self.owner.busy = False

    def poison(self):
        try:
            from civ6_host.runtime.xp1_load_capability import finish_cache_source_scope
            finish_cache_source_scope(self)
        finally:
            if self.publication_owner is not None:
                self.publication_owner.poison()
            self.owner.poisoned = True
            self.owner.stage = 'poisoned'
            self.owner.busy = False

def run_facades_only(core, context, load_result, emit, *, publication_mode='public'):
    key = (id(core), context)
    if key in _ATTEMPTS or key not in load._RETAINED:
        raise RuntimeError('Missing or previously attempted retained Load context')
    owner = load._RETAINED[key]
    _ATTEMPTS[key] = None
    try:
        backend = NativeFacadeBackend(owner, load_result, publication_mode=publication_mode)
        _ATTEMPTS[key] = backend
        return run_sequence(backend, emit)
    except BaseException as error:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.busy = False
        load._fatal(error)
        raise RuntimeError('Fatal post-load termination unexpectedly returned') from error

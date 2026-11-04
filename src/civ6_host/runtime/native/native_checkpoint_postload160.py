"""Bounded diagnostic for the source-pinned outer +0x160 call.

It does not implement AUX/Host42, publish
through +0x190, update the game, or destroy the retained context.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import struct
from civ6_host.runtime.native import native_checkpoint_load as load
from civ6_host.runtime.native import native_checkpoint_postload_facades as facades
from civ6_host.runtime.postload160_source import profile_for_sha, require_runtime_admission
PLAN_PATH = facades.PLAN_PATH
PLAN_SHA256 = facades.PLAN_SHA256
FACADES_PATH = facades.FACADES_PATH
FACADES_SHA256 = facades.FACADES_SHA256
POST160_SLOT = 352
POST160_RVA = 4383936
_ATTEMPTS = {}

def verify_source(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.postload160_source import expansion_source
        return expansion_source(core_sha256)
    plan = load.pinned_json(PLAN_PATH, PLAN_SHA256)
    proof = facades.verify_source()
    post = plan['abi']['postload']
    if post['slot'] != '0x160' or post['target_rva'] != '0x42e4c0' or post['signature'] != 'void-like(this:void*, flag:uint8=1)' or ('No meaningful EAX status' not in post['return']):
        raise ValueError('Post-load +160 source contract changed')
    bodies = proof['captures']['core']
    body = bodies.get('new_0x42e4c0')
    if not body or not list(load.instructions(body)):
        raise ValueError('Post-load +160 body is not source-pinned')
    return proof

def check_live_post160(base, read, proof, *, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.postload160_source import verify_expansion_live
        return verify_expansion_live(base, read, proof, core_sha256=core_sha256)
    facades.check_live_code(base, read, proof)
    slot = struct.unpack('<Q', read(base + 7987232 + POST160_SLOT, 8))[0]
    if slot != base + POST160_RVA:
        raise ValueError('Outer +0x160 vtable target differs from the pinned route')

def _validate_readback(value, *, expected_major_ids=(0, 1)):
    if type(expected_major_ids) is not tuple or any((type(pid) is not int for pid in expected_major_ids)) or (not 1 <= len(expected_major_ids) <= 64 or any((not 0 <= pid < 64 for pid in expected_major_ids)) or tuple(sorted(set(expected_major_ids))) != expected_major_ids):
        raise ValueError('Unsupported post-load diagnostic roster')
    if type(value) is not dict or set(value) != {'current_game_turn', 'width', 'height', 'major_player_ids', 'scope', 'game_update_called'} or any((type(value[k]) is not int for k in ('current_game_turn', 'width', 'height'))) or (value['current_game_turn'] < 0) or (not 0 < value['width'] <= 16384) or (not 0 < value['height'] <= 16384) or (value['width'] * value['height'] > 16384) or (type(value['major_player_ids']) is not list) or (len(value['major_player_ids']) != len(expected_major_ids)) or any((type(pid) is not int for pid in value['major_player_ids'])) or (value['major_player_ids'] != list(expected_major_ids)) or (value['scope'] != 'privileged diagnostic; no learner observation') or (value['game_update_called'] is not False):
        raise ValueError('Post-load gameplay readback is not the exact privileged diagnostic')
    return value

def run_sequence(backend, emit, *, expected_major_ids=(0, 1)):
    """Execute one void-like +160 call and validate immediate/post-readback state."""
    if backend.attempted:
        raise RuntimeError('Post-load +160 attempt cannot be retried')
    backend.attempted = True
    try:
        backend.enter()
        identity = backend.observe()
        before = backend.jobs_snapshot('before')
        backend.call_post160_once()
        after_call = backend.jobs_snapshot('after')
        emit('native_checkpoint_postload_160_returned', native_return=None, jobs_before=before, jobs_after=after_call, jobs_identical=before == after_call, validation_completed=False, return_semantics='void-like; no EAX success claim', post190_called=False, game_update_called=False, context_destroyed=False, eligible_for_training=False)
        if before != after_call:
            raise RuntimeError('Post-load +160 changed the immediate scheduler snapshot')
        if backend.observe() != identity:
            raise RuntimeError('Post-load +160 changed retained ownership/context identity')
        readback = _validate_readback(backend.readback(), expected_major_ids=expected_major_ids)
        after_readback = backend.jobs_snapshot('after')
        if before != after_readback:
            raise RuntimeError('Post-load readback changed the scheduler snapshot')
        if backend.observe() != identity:
            raise RuntimeError('Post-load readback changed retained ownership/context identity')
        result = dict(post160_called=True, call_returned=True, call_abi='void-like; return value ignored', immediate_jobs_unchanged=True, postreadback_jobs_unchanged=True, readback=readback, post190_called=False, game_update_called=False, context_destroyed=False, full_exe_load_lifecycle_reproduced=False, reset_validated=False, continuation_validated=False, owners_retained=True, scheduler_load_ledger_postrun_required=True, controlled_stop_required=True, eligible_for_training=False)
        backend.finish()
        emit('native_checkpoint_postload_160_observed', **result)
        return result
    except BaseException:
        backend.poison()
        raise

class NativePostload160Backend:
    """Concrete native adapter; observations also use original Core getters."""

    def __init__(self, owner, load_result, inputs):
        if type(owner) is not load.NativeLoadBackend:
            raise TypeError('Post-load +160 requires the retained native Load owner')
        self.post160_abi = require_runtime_admission(profile_for_sha(owner.load_abi.core_sha256))
        load.validate_inputs(inputs)
        self.owner, self.load_result, self.inputs = (owner, load_result, inputs)
        self.attempted = False
        self.native_call_attempted = False
        self.proof = verify_source(core_sha256=self.post160_abi.core_sha256)
        self._facade_attempt = None

    def enter(self):
        b = self.owner
        b.check_thread()
        if load.validated_owner_inputs(b) is not self.inputs:
            raise RuntimeError('Post-load input pair differs from the retained Load owner')
        key = (id(b.core), b.context)
        attempt = facades._ATTEMPTS.get(key)
        if load._RETAINED.get(key) is not b or b.busy or b.stage != 'facades-observed-awaiting-post160' or (b.reader is None) or (b.reader.transport.closed is not True) or (b.reader.transport.cursor != len(self.inputs.game)) or (type(attempt) is not facades.NativeFacadeBackend) or (attempt.owner is not b) or (attempt.load_result is not self.load_result) or (attempt.publisher is not getattr(b.prefix, 'view_publisher', None)) or (attempt.attempted is not True):
            raise RuntimeError('Post-load +160 lacks this context’s completed facade phase')
        publisher = attempt.publisher
        if publisher is None or publisher._closed or publisher.full_facade_initialization_reproduced is not True or (publisher.native_cache_gate is not True) or (publisher._facades is None) or (len(publisher.cache_map_snapshot or b'') != 28):
            raise RuntimeError('Post-load +160 requires the retained initialized public facades')
        receipt = self.load_result.get('receipt', {})
        if self.load_result.get('raw_component_load_observed') is not True or self.load_result.get('controlled_stop_required') is not True or self.load_result.get('post160_called') is not False or (type(receipt.get('status')) is not int) or (receipt['status'] != 0) or (receipt.get('bytes_consumed') != len(self.inputs.game)) or (receipt.get('scheduler_ledger_reconciliation_pending') is not True):
            raise RuntimeError('Post-load +160 lacks a validated raw Load receipt')
        b.control(empty=True)
        check_live_post160(b.core._handle, b.runtime.read, self.proof, core_sha256=self.post160_abi.core_sha256)
        self._facade_attempt = attempt
        b.busy = True

    def observe(self):
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import check_active
            check_active(self)
        b = self.owner
        b.check_thread()
        topology = b.topology(game_required=True)
        if topology != b.bound_identity or b.game_flag() != 1:
            raise RuntimeError('Loaded Game/provider identity changed around +160')
        b.owner.require_context(b.core._handle, b.context)
        b.control(empty=True)
        if self._facade_attempt is None or self._facade_attempt.publisher is not b.prefix.view_publisher:
            raise RuntimeError('Retained public facade identity changed around +160')
        return (b.context, topology['inner'], topology['game'], topology['provider'], b.owner.pointer, b.prefix.game_child, id(b.prefix.view_publisher), id(b.prefix.view_publisher._facades))

    def jobs_snapshot(self, phase):
        return self.owner.jobs_snapshot(phase)

    def call_post160_once(self):
        b = self.owner
        b.check_thread()
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import before_call
            before_call(self)
        else:
            require_runtime_admission(self.post160_abi)
        if self.native_call_attempted or not b.busy or self._facade_attempt is None:
            raise RuntimeError('Post-load +160 requires its first exclusive attempt')
        check_live_post160(b.core._handle, b.runtime.read, self.proof, core_sha256=self.post160_abi.core_sha256)
        self.native_call_attempted = True
        C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(b.core._handle + self.post160_abi.target_rva)(b.context, 1)
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import after_call
            after_call(self)

    def readback(self):
        b = self.owner
        b.check_thread()
        if b.prefix is None or b.prefix.game_child is None:
            raise RuntimeError('Actual loaded gameplay child is unavailable')
        raw = b.prefix.runtime.evaluate_text(b.prefix.game_child, load.READBACK_LUA, b'@native_postload_160_readback', capacity=256)
        return load.parse_readback(raw, self.inputs)

    def finish(self):
        if getattr(self, 'postload_mode', 'public') == 'candidate':
            from civ6_host.runtime.xp1_postload_candidate import finish, FINISHED_STAGE
            finish(self)
            self.owner.stage = FINISHED_STAGE
            self.owner.busy = False
            return
        self.owner.stage = 'post160-observed-awaiting-controlled-stop'
        self.owner.busy = False

    def poison(self):
        try:
            if getattr(self, 'postload_mode', 'public') == 'candidate':
                from civ6_host.runtime.xp1_postload_candidate import poison
                poison(self)
        finally:
            self.owner.poisoned = True
            self.owner.stage = 'poisoned'
            self.owner.busy = False

def run_postload_160(core, context, load_result, emit):
    key = (id(core), context)
    if key in _ATTEMPTS or key not in load._RETAINED:
        raise RuntimeError('Missing or previously attempted retained Load context')
    owner = load._RETAINED[key]
    _ATTEMPTS[key] = None
    try:
        inputs = load.validated_owner_inputs(owner)
        backend = NativePostload160Backend(owner, load_result, inputs)
        _ATTEMPTS[key] = backend
        return run_sequence(backend, emit)
    except BaseException as error:
        owner.poisoned = True
        owner.stage = 'poisoned'
        owner.busy = False
        load._fatal(error)
        raise RuntimeError('Fatal post-load +160 termination unexpectedly returned') from error

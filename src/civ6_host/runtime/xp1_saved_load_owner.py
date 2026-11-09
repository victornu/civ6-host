"""One retained XP1 saved-Load graph shared by qualification and session workers.

The caller owns closure/build verification, process containment, receipts and
termination after failure. This owner reuses the existing native stages; it
admits no additional capture, command, turn, observation or outcome capability.
"""
from contextlib import contextmanager
import threading
from types import MappingProxyType

from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256


_FLAGS = ('post160_candidate', 'publish_cache_candidate', 'close_loaded_candidate',
          'observe_player_candidate', 'unit_commands_candidate')
_STAGES = {
    'raw-loaded': 'raw-loaded',
    'caches': 'facades-candidate-observed',
    'postload': 'post160-candidate-observed-awaiting-controlled-stop',
    'published': 'publication-candidate-observed-awaiting-controlled-stop',
    'observed': 'publication-candidate-observed-awaiting-controlled-stop',
    'commands': 'xp1-continuation-ready',
}


def _requested(closure):
    if (type(closure) is not dict or closure.get('input_profile') not in ('xp1-lan','xp2-lan')
            or closure.get('raw_only_candidate') is not True):
        raise ValueError('Saved owner requires the explicit XP1 saved-Load candidate')
    flags = {name: closure.get(name, False) for name in _FLAGS}
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError('Saved owner capability requests must be exact Booleans')
    if ((flags['publish_cache_candidate'] or flags['close_loaded_candidate'])
            and not flags['post160_candidate']
            or flags['observe_player_candidate']
            and not (flags['publish_cache_candidate'] and flags['close_loaded_candidate'])
            or flags['unit_commands_candidate'] and not flags['observe_player_candidate']):
        raise ValueError('Saved owner capability dependencies are incomplete')
    return MappingProxyType(flags)


class SavedLoadOwner:
    """Thread-bound orchestration of the existing exact native owners."""

    def __init__(self):
        raise TypeError('Use SavedLoadOwner.open with an explicit private closure')

    @classmethod
    def open(cls, closure, emit, win):
        requested = _requested(closure)
        from .captured_saved_load import select_load_closure
        contract=select_load_closure(closure)
        owner=cls._allocate(requested,emit)
        try:
            from .workers.run_official_postload909 import open_official_backend
            owner._bind_loaded(open_official_backend(closure,emit,win),contract.core_sha256)
            return owner
        except BaseException:
            owner._poison()
            raise

    @classmethod
    def from_loaded(cls,backend,closure,emit):
        """Reuse the same stage graph after the exact captured XP2 raw Load."""
        requested=_requested(closure)
        if closure['input_profile']!='xp2-lan' or not requested['post160_candidate']:
            raise ValueError('Captured XP2 attachment requires explicit postload capability')
        from .captured_saved_load import validate_candidate_inputs
        validate_candidate_inputs(backend.inputs,backend.captured_bundle)
        if (backend.load_abi.core_sha256!=XP2_CORE_SHA256
                or getattr(backend,'_xp2_postload_requested',False) is not True):
            raise ValueError('XP2 attachment lacks the selected composed Load graph')
        owner=cls._allocate(requested,emit)
        try:
            owner._bind_loaded(backend,XP2_CORE_SHA256)
            return owner
        except BaseException:
            owner._poison()
            raise

    @classmethod
    def _allocate(cls,requested,emit):
        if cls is not SavedLoadOwner or not callable(emit):
            raise TypeError('Exact SavedLoadOwner and event sink required')
        owner = object.__new__(cls)
        owner.thread = threading.get_ident()
        owner.requested, owner.emit = requested, emit
        owner.phase, owner.poisoned, owner._running = 'opening', False, False
        owner.backend = owner._backend = None
        owner.facade = owner.post = owner.publication = None
        owner.player_view = owner.continuation = None
        owner.cache_result = owner.post_result = owner.publication_result = None
        owner.view_result = owner.close_result = None
        return owner

    def _bind_loaded(self,backend,core_sha256):
        from .native.native_official_postload import validate_receipt
        from .native.native_official_load import OfficialLoadBackend
        owner=self
        try:
            if type(backend) is not OfficialLoadBackend or hasattr(backend,'_saved_stage_owner'):
                raise TypeError('Shared loader returned a foreign backend')
            owner._engine_sha256=core_sha256
            owner.backend = owner._backend = backend
            backend._saved_stage_owner=owner
            owner.prefix, owner.core, owner.host = backend.prefix, backend.core, backend.host
            owner.context, owner.inputs = backend.context, backend.inputs
            owner.receipt = backend.raw_load_result
            validate_receipt(owner.receipt, backend.inputs)
            owner.raw_result = dict(schema='civ6-host.xp1-raw-load-observed.v1',
                raw_load_receipt=owner.receipt, readback=backend.loaded_readback,
                saved_game_loaded=True, post160_called=False,
                public_runtime_admitted=False, strategic_training_ready=False)
            owner.phase = 'raw-loaded'
            owner._check('raw-loaded')
        except BaseException:
            owner._poison()
            raise

    def _poison(self):
        self.poisoned = True
        self.phase = 'poisoned'
        # Python state only: no guessed native release, callback or Destroy.
        backend = self._backend
        if backend is not None:
            backend.poisoned = True
            backend.stage = 'poisoned'
            backend.busy = False
            prefix = getattr(self, 'prefix', None)
            if prefix is not None:
                prefix.quarantined = True
        if self.continuation is not None:
            self.continuation.poisoned = True

    def _thread(self):
        if threading.get_ident() != self.thread:
            raise RuntimeError('Saved owner belongs to another thread')

    def _check(self, *phases, requested=None, active=False, query=False):
        self._thread()
        if (type(active) is not bool or type(query) is not bool or active and query
                or self.poisoned or self._running is not (active or query)
                or self.phase not in phases or (active or query) and self.phase!='commands'):
            raise RuntimeError('Saved owner phase is incomplete, active, closed or poisoned')
        if requested is not None and not self.requested[requested]:
            raise ValueError('Saved owner capability was not requested before Load')
        b = self.backend
        if (b is not self._backend or b.prefix is not self.prefix
                or getattr(b,'_saved_stage_owner',None) is not self
                or b.core is not self.core or b.host is not self.host
                or b.context != self.context or b.inputs is not self.inputs
                or b.raw_load_result is not self.receipt
                or b.load_abi.core_sha256 != self._engine_sha256
                or self._engine_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
                or self._engine_sha256==XP2_CORE_SHA256 and getattr(b,'_xp2_postload_requested',None) is not self.requested['post160_candidate']
                or getattr(b, '_saved_load_candidate', False) is not True
                or getattr(b, '_xp1_commands_requested', False) is not self.requested['unit_commands_candidate']
                or b.stage != ('xp1-continuation-active' if active else _STAGES[self.phase])
                or b.busy is not active
                or b.poisoned or b.destroyed
                or getattr(self.prefix, 'quarantined', False)):
            raise ValueError('Saved owner lost its original live backend graph')
        b.check_thread()
        for local, root in (('facade', 'saved_load_cache_attempt'),
                            ('post', 'saved_load_post160_attempt'),
                            ('publication', 'saved_load_publication_attempt'),
                            ('player_view', '_xp1_player_view'),
                            ('continuation', '_xp1_continuation')):
            attempt = getattr(self, local)
            if attempt is not None and (attempt.owner is not b or getattr(b, root, None) is not attempt):
                raise ValueError('Saved owner retained attempt was replaced')

    def _check_active(self):
        self._check('commands',requested='unit_commands_candidate',active=True)
        self.continuation.check(active=True)

    def _check_query(self):
        """Read inside the retained attempt while Core remains at READY."""
        self._check('commands',requested='unit_commands_candidate',query=True)
        self.continuation.check(active=False)

    @contextmanager
    def _attempt(self):
        self._running = True
        try:
            yield
        except BaseException:
            self._poison()
            raise
        finally:
            self._running = False

    def _finish(self, phase):
        # Called inside the attempt so an unexpected return also poisons it.
        self.phase = phase
        self._running = False
        self._check(phase)
        self._running = True

    def populate_caches(self):
        self._check('raw-loaded')
        from .native.native_official_postload import OfficialFacadeBackend
        from .native.native_checkpoint_postload_facades import run_sequence
        with self._attempt():
            self.facade = OfficialFacadeBackend(self.backend, self.receipt, publication_mode='candidate')
            self.backend.saved_load_cache_attempt = self.facade
            self.cache_result = run_sequence(self.facade, self.emit)
            if (self.cache_result.get('candidate_native_cache_only') is not True
                    or self.cache_result.get('public_cache_gate_enabled') is not False
                    or self.cache_result.get('post160_admitted') is not False):
                raise RuntimeError('Cache result crossed the candidate boundary')
            self._finish('caches')
        return self.cache_result

    def postload(self):
        self._check('caches', requested='post160_candidate')
        from .native.native_official_postload import OfficialPost160Backend
        from .native.native_checkpoint_postload160 import run_sequence
        with self._attempt():
            self.post = OfficialPost160Backend(self.backend, self.facade, self.cache_result, postload_mode='candidate')
            self.backend.saved_load_post160_attempt = self.post
            major_ids = tuple(map(int, self.backend.loaded_roster.decode('ascii').split('|')[3:]))
            result = run_sequence(self.post, self.emit, expected_major_ids=major_ids)
            self.post_result = dict(result, candidate_diagnostics=self.post.candidate_diagnostics)
            self._finish('postload')
        return self.post_result

    def publish(self):
        self._check('postload', requested='publish_cache_candidate')
        from .xp1_cache_publication import SavedCachePublication
        with self._attempt():
            self.publication = SavedCachePublication(self.post)
            self.backend.saved_load_publication_attempt = self.publication
            self.publication_result = self.publication.run()
            from . import xp2_bbg_inputs
            if (self._engine_sha256 == XP2_CORE_SHA256
                    and xp2_bbg_inputs.is_reference(getattr(self.inputs, 'official_bundle', None))):
                from .xp2_bbg_view_ready import deliver
                deliver(self.publication)
            self._finish('published')
        return self.publication_result

    def observe_initial(self):
        self._check('published', requested='observe_player_candidate')
        from .xp1_ui_binding import SavedPlayerView
        with self._attempt():
            self.player_view = SavedPlayerView(self.publication)
            self.view_result = self.player_view.run()
            self._finish('observed')
        return self.view_result

    def begin_commands(self):
        self._check('observed', requested='unit_commands_candidate')
        from .xp1_continuation import SavedContinuation
        with self._attempt():
            self.continuation = SavedContinuation(self.player_view)
            self._finish('commands')
        return self.continuation

    def execute(self, action):
        self._check('commands', requested='unit_commands_candidate')
        from .xp1_continuation import validate_command
        validate_command(action, observation=self.continuation.observation)
        with self._attempt():
            result = self.continuation.execute(action,session=self)
            self._finish('commands')
        return result

    def advance_congress_empty(self, protocol_sequence):
        """Private post-action/poll SetPhase transition, never an actor opcode."""
        self._check('commands', requested='unit_commands_candidate')
        if getattr(self, 'world_congress_diagnostic', False) is not True:
            return None
        from .xp2_world_congress import prepare_empty_phase
        with self._attempt():
            result = None
            if prepare_empty_phase(self, sequence=protocol_sequence):
                result = self.continuation._transition(
                    dict(kind='automatic_congress_empty_phase', sequence=protocol_sequence),
                    session=self, pump=False)
            self._finish('commands')
        return result

    def advance(self):
        self._check('commands',requested='unit_commands_candidate')
        with self._attempt():
            result=self.continuation.advance(self)
            self._finish('commands')
        return result

    def close(self):
        self._thread()
        if self.phase == 'closed' and not self.poisoned:
            return self.close_result
        self._check('postload', 'published', 'observed', 'commands', requested='close_loaded_candidate')
        from .native.native_official_postload import OfficialPost160Backend
        from .xp1_cache_publication import SavedCachePublication
        from .xp1_continuation import SavedContinuation
        completed = self.continuation if self.continuation is not None else self.publication if self.publication is not None else self.post
        expected = SavedContinuation if self.phase == 'commands' else SavedCachePublication if self.phase in ('published', 'observed') else OfficialPost160Backend
        if type(completed) is not expected or completed.owner is not self.backend:
            raise ValueError('Saved owner lacks the exact completed native close capability')
        with self._attempt():
            self.close_result = self.backend.close_loaded(completed=completed)
            # check_thread intentionally rejects destroyed contexts: only inspect
            # retained Python metadata after the qualified lifetime returns.
            if (self.backend.destroyed is not True or self.backend.poisoned
                    or self.backend.stage != 'loaded-lifetime-closed'
                    or self.close_result.get('native_unload_called') is not True
                    or self.close_result.get('native_destroy_called') is not True):
                raise RuntimeError('Native loaded close did not confirm its complete return')
            self.phase = 'closed'
        return self.close_result

"""Adapt source-qualified empty presentation families on the existing A0 owner.

Only fixed host composition supplies these trusted source modules. Protocol
requests cannot select a module, register a kind or relax a receiver contract.
Native Core producers and cache updates are never intercepted by this adapter.
"""
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
import re

from .configuration_profiles import XP2_CORE_SHA256

POLICY = 'source-qualified-empty-presentation-zero-records'


@dataclass(frozen=True)
class Binding:
    owner: object
    backend: object
    source: object
    source_sha256: str


def check_registry(owner):
    if (owner.presentation_sources is not owner._presentation_sources
            or type(owner.presentation_sources) is not MappingProxyType):
        raise RuntimeError('Empty presentation source registry changed')
    for kind, binding in owner.presentation_sources.items():
        if (type(binding) is not Binding or binding.owner is not owner
                or binding.backend is not owner._foundation_backend
                or binding.source.SOURCE[1] != binding.source_sha256
                or kind not in binding.source.KINDS or binding.source.POLICY != POLICY):
            raise RuntimeError('Empty presentation source binding changed')


def enable(owner, backend, source):
    from .a0_family_service import A0FamilyService
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    from .a0_family_source import _path, verify_pinned_files

    if type(owner) is not A0FamilyService:
        raise ValueError('Empty presentation requires the real shared A0 owner')
    owner._check(); backend.check_thread()
    if (owner._foundation_backend is not backend or owner._foundation_borrow is not None
            or owner.arguments.depth or owner.active_kind is not None or owner.pending
            or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or backend.stage != 'prepared' or backend.prefix is not None
            or getattr(backend, '_xp1_commands_requested', False) is not True
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context != owner.deferred.context
            or owner.arguments.reader.core_sha256 != XP2_CORE_SHA256
            or owner.deferred.cache_core_sha256 != XP2_CORE_SHA256):
        raise ValueError('Empty presentation requires its idle prepared XP2 owner')
    if (not isinstance(source, ModuleType)
            or not source.__name__.startswith('civ6_host.runtime.xp2_')
            or source.POLICY != POLICY or type(source.KINDS) is not frozenset
            or not source.KINDS or set(source.CALLBACKS) != set(source.KINDS)
            or any(type(k) is not int or not 0 <= k <= 0xffffffff for k in source.KINDS)
            or type(source.SOURCE) is not tuple or len(source.SOURCE) != 2
            or type(source.SOURCE[0]) is not str or type(source.SOURCE[1]) is not str
            or re.fullmatch('[0-9a-f]{64}', source.SOURCE[1]) is None
            or any(EXE_EVENT_CALLBACKS.get(k) != source.CALLBACKS[k] for k in source.KINDS)):
        raise ValueError('Empty presentation source contract is not explicit')
    if any(owner.handles_kind(k) for k in source.KINDS):
        raise ValueError('Empty presentation family overlaps an installed callback')
    pins = source.source_dependencies()
    if pins.get(str(_path(source.SOURCE[0]).resolve())) != source.SOURCE[1]:
        raise ValueError('Empty presentation profile is absent from source dependencies')
    verify_pinned_files(pins)
    source.bind_owner(backend, backend.core, owner.read)
    binding = Binding(owner, backend, source, source.SOURCE[1])
    updated = dict(owner.presentation_sources)
    updated.update((kind, binding) for kind in source.KINDS)
    owner.presentation_sources = owner._presentation_sources = MappingProxyType(updated)
    owner._check()
    owner.emit('native_empty_presentation_family_installed', core_sha256=XP2_CORE_SHA256,
        source_module=source.__name__, source_proof_sha256=source.SOURCE[1],
        dispatch_kinds=[hex(k) for k in sorted(source.KINDS)], policy=POLICY,
        synthetic_records=False, unknown_service_fallback=False)
    return binding


def dispatch(owner, kind, fields):
    from .a0_foundation_events import require_borrow
    owner._check()
    binding = owner.presentation_sources.get(kind)
    if type(binding) is not Binding or owner.active_kind != kind or owner._foundation_borrow is not None:
        raise ValueError('Empty presentation callback lacks its registered synchronous owner')
    backend = binding.backend
    token = getattr(backend, '_xp1_continuation', None)
    from .xp1_continuation import SavedContinuation
    if type(token) is not SavedContinuation or token.owner is not backend:
        raise ValueError('Empty presentation callback lacks its actual continuation')
    token.check(active=True)
    before = (owner._sequence, tuple(owner.pending), owner.host_notification_counter,
              owner.host_metadata_counter)
    owner._foundation_borrow = token
    try:
        require_borrow(owner)
        source = binding.source
        if source.validate_empty_owner(owner) != POLICY:
            raise ValueError('Empty presentation source policy changed')
        copied = source.decode_fields(kind, fields, owner.read).to_admin()
        if source.validate_empty_owner(owner) != POLICY:
            raise ValueError('Empty presentation source policy changed during input copy')
        sequence, pending, notifications, metadata = before
        if (owner._sequence != sequence or len(owner.pending) != len(pending)
                or any(a is not b for a, b in zip(owner.pending, pending))
                or (owner.host_notification_counter, owner.host_metadata_counter) != (notifications, metadata)):
            raise RuntimeError('Empty presentation changed its native FIFO or notification scope')
        owner.emit('native_empty_presentation_callback_omitted', dispatch_kind=hex(kind),
            source_module=source.__name__, source_proof_sha256=binding.source_sha256,
            policy=POLICY, administrative_arguments=copied,
            information_scope='administrative-unfiltered', public_visibility_qualified=False,
            native_queries_executed=False, native_gameplay_written=False,
            presentation_arrays_allocated=False, records_enqueued=0,
            fifo_sequence_before=sequence, fifo_sequence_after=owner._sequence,
            preceding_pending_records_preserved=True, native_dispatch_return=0,
            eligible_for_training=False)
        return 0
    finally:
        owner._foundation_borrow = None

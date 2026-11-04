"""XP2 source selection for shared pre-Load transports, not game admission.

FIFO serialization, controller state and complete-map reading stay in their
existing owners. This module selects and verifies only the XP2 native bindings.
Per-event consumers and loaded-game lifetime still need their own contracts.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import struct
import threading
from types import MappingProxyType

from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256
from .resource_resolution import resolve_path
from .native.native_source_cache import _stat_identity

SOURCE = ('work/host-extensions/xp2-preload-services/source-profile-v1.json',
          'c09f13c0895337f9bcecff5c2313242a35c50637ee8342fd558d544228386a57')
CAPTURE_SHA = 'fec7d8d7507c24a36456cb5588ea9e0b2d7bb08d1d1300007edd6f666231bc3b'
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
CACHE_OUTER_VTABLE_RVA = 0xA101E8
CACHE_DISPATCH_RVA = 0x591920
_VALIDATED_SOURCE = None
_SOURCE_LOCK = threading.RLock()
_CACHE_DISPATCH_SCOPE = ContextVar('xp2_cache_dispatch_scope', default=None)
_EVENT_READER_SCOPE = ContextVar('xp2_event_reader_scope', default=None)
_CACHE_BODIES = ('cache_outer198', 'cache_keyed_dispatch', 'b0_snapshot_emitter')
_EVENT_READER_BODIES = ('iterator_next', 'get_count')


def source():
    p = _source(SOURCE)
    if (p['schema'] != 'civ6-host.xp2-preload-services-profile.v1'
            or p['core_sha256'] != XP2_CORE_SHA256 or p['exe_sha256'] != EXE_SHA
            or p['native_execution'] is not False or p['saved_load_admitted'] is not False
            or p['source']['sha256'] != CAPTURE_SHA
            or p['validation']['all_instruction_bytes_match_pinned_images'] is not True):
        raise ValueError('XP2 pre-Load source identity differs')
    cache = p['deferred']
    if (cache['outer_vtable_rva'] != hex(CACHE_OUTER_VTABLE_RVA)
            or cache['cache_update_slot'] != 0x198
            or cache['cache_update_thunk_rva'] != hex(CACHE_DISPATCH_RVA)
            or cache['host_global_rva'] != '0xb8aa80'
            or cache['cache_registry'] != dict(buckets_rva='0xb61e10', bucket_count_rva='0xb61e18',
                key_count_rva='0xb61e1c', node_key=0, node_next=40, subscriber_begin=8,
                subscriber_end=16, subscriber_stride=32, receiver=16, function=24,
                sentinel='buckets[bucket_count]')):
        raise ValueError('XP2 shared cache registry layout differs')
    event = p['event_argument']
    if (event['map_vtable_rva'] != '0xabf080' or event['iterator_next_rva'] != '0x994d90'
            or event['get_count_rva'] != '0x84e260' or event['map_size'] != 88
            or event['iterator_bytes'] != 68
            or event['map_layout'] != dict(sentinel=48, first=56, root=64, count=80)
            or event['node_layout'] != dict(right=0, left=8, parent=16, key=32, variant=40)
            or event['variant_layout'] != dict(size=24, tag=0, payload=8, element_count=16, flags=20)):
        raise ValueError('XP2 shared event argument layout differs')
    control = p['control_input']
    if (control['host_global_rva'] != '0xb8aa80' or control['d0']['slot'] != 0xD0
            or control['d0']['return'] != 'uint32 EAX'
            or tuple(control['d0']['host_policy_domain']) != (-1,64)
            or control['controller120']['slot'] != 0x120
            or control['controller120']['return'] != 'uint8 AL'
            or control['controller120']['reuse_exact_exe_constructor_getter_state'] is not True):
        raise ValueError('XP2 controller callback ABI differs')
    capture = _source((p['source']['path'], CAPTURE_SHA))
    if (capture['images']['xp2']['sha256'] != XP2_CORE_SHA256
            or capture['images']['exe']['sha256'] != EXE_SHA):
        raise ValueError('XP2 pre-Load capture image differs')
    for r in [capture['generator'], *p['references'].values()]:
        path = resolve_path(Path(r['path']))
        if path.suffix == '.json':
            _source((str(path), r['sha256']))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError('XP2 pre-Load capture dependency differs: ' + str(path))
    return p


def _selection_identity():
    from .paths import resource_root
    from .resource_resolution import configured_reference
    root = resource_root()
    reference = configured_reference()
    relocation = None if reference is None else (reference['path'], reference['sha256'])
    return (str(root), str(resolve_path(root/SOURCE[0]).resolve()), relocation,
            SOURCE, CAPTURE_SHA, EXE_SHA, XP2_CORE_SHA256,
            id(source), id(getattr(source, '__code__', None)),
            id(_source), id(getattr(_source, '__code__', None)),
            id(resolve_path), id(resource_root), str(Path(__file__).resolve()))


def _source_files(proof, capture):
    from .paths import resource_root
    refs = [dict(path=str(resource_root()/SOURCE[0]), sha256=SOURCE[1]),
            proof['source'], capture['generator'], *proof['references'].values()]
    files = {}
    for ref in refs:
        path = resolve_path(Path(ref['path']))
        key = str(path)
        if key in files and files[key][1] != ref['sha256']:
            raise ValueError('Conflicting XP2 pre-Load source dependency')
        files[key] = (path, ref['sha256'])
    # Code identity changes re-enter full source validation; the normal runtime
    # source manifest separately pins authored module bytes for the worker.
    module = Path(__file__).resolve()
    files[str(module)] = (module, None)
    return tuple(files.values())


def _source_signature(files):
    identities = []
    for path, expected in files:
        identity = _stat_identity(path)
        actual = None
        if expected is not None and path.suffix != '.json':
            # Public source() rehashes these small generator/helper files on
            # every call. Reuse JSON verification without weakening that rule.
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError('XP2 pre-Load capture dependency differs: ' + str(path))
            if _stat_identity(path) != identity:
                raise ValueError('XP2 pre-Load dependency changed while hashing: ' + str(path))
        identities.append((str(path), expected, identity, actual))
    return tuple(identities)


def _validated_source():
    """Reuse frozen JSON validation; stat all files and rehash non-JSON inputs.

    Public source() still performs its full checks. No live code, registry,
    context, argument map, provider or game value is retained by this receipt.
    """
    global _VALIDATED_SOURCE
    with _SOURCE_LOCK:
        try:
            selection = _selection_identity()
            proof = _source(SOURCE)
            capture = _source((proof['source']['path'], CAPTURE_SHA))
            old = _VALIDATED_SOURCE
            if (old is not None and old[0] == selection
                    and old[1] is proof and old[2] is capture
                    and _source_signature(old[3]) == old[4]):
                return proof
            _VALIDATED_SOURCE = None
            if not isinstance(proof, MappingProxyType) or not isinstance(capture, MappingProxyType):
                source()  # Preserve the public validator's original refusal.
                raise ValueError('XP2 pre-Load source is not immutable pinned JSON')
            files = _source_files(proof, capture)
            before = _source_signature(files)
            verified = source()
            if (verified is not proof or not isinstance(proof, MappingProxyType)
                    or not isinstance(capture, MappingProxyType)
                    or _selection_identity() != selection
                    or _source_signature(files) != before):
                raise ValueError('XP2 pre-Load source changed during validation')
            _VALIDATED_SOURCE = (selection, proof, capture, files, before)
            return proof
        except BaseException:
            _VALIDATED_SOURCE = None
            raise


def body(name):
    p = _validated_source()
    capture = _source((p['source']['path'], CAPTURE_SHA))
    return _select_body(p, capture, name)


def _select_body(p, capture, name):
    route = p['body_sources'][name]
    row = capture['functions'][name]
    if row['entry_rva'] != route['rva'] or tuple(route['selector']) != ('functions',name,'body'):
        raise ValueError('XP2 pre-Load body selection differs')
    return row['body']


def _exact(read, address, length):
    if type(address) is not int or address <= 0 or type(length) is not int or not 0 < length <= 131072:
        raise ValueError('Invalid pre-Load memory range')
    raw = read(address, length)
    if type(raw) is not bytes or len(raw) != length:
        raise ValueError('Incomplete XP2 pre-Load memory read')
    return raw


def verify_bodies(base, read, names):
    proof = _validated_source()
    _verify_bodies(base, read, names, proof)


def _verify_bodies(base, read, names, proof):
    capture = _source((proof['source']['path'], CAPTURE_SHA))
    for name in names:
        for fragment in _select_body(proof, capture, name)['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            if (len(raw) != fragment['length']
                    or hashlib.sha256(raw).hexdigest() != fragment['sha256']
                    or _exact(read, base+int(fragment['start_rva'],16), len(raw)) != raw):
                raise ValueError('XP2 pre-Load live code differs: ' + name)


def _q(read, address):
    return struct.unpack('<Q',_exact(read,address,8))[0]


def _owner(base, context, read, *, host_pointer=None):
    return _check_owner(base, context, read, _validated_source(), host_pointer=host_pointer)


def _check_owner(base, context, read, p, *, host_pointer=None):
    guards = p['event_argument']['guards']
    inner = _q(read,context+8)
    if (_q(read,context) != base+int(p['deferred']['outer_vtable_rva'],16)
            or not inner or inner != _q(read,base+int(guards['inner_global_rva'],16))
            or _q(read,inner) != base+0xA44F70
            or (host_pointer is not None
                and _q(read,base+int(guards['host_global_rva'],16)) != host_pointer)):
        raise ValueError('XP2 pre-Load callback owner/context differs')
    return inner


def _scope_source():
    # A long update can evict the JSON objects from the shared bounded LRU.
    # Compare the verified selection and dependency identities across the
    # update, independent of which immutable Python object represents them.
    with _SOURCE_LOCK:
        proof = _validated_source()
        selection, _, _, _, signature = _VALIDATED_SOURCE
        return proof, (selection, signature)


@contextmanager
def cache_dispatch_scope(base, context, read):
    """Reuse pinned static inputs for one FIFO drain on its owner thread."""
    if _CACHE_DISPATCH_SCOPE.get() is not None:
        raise RuntimeError('Nested XP2 CacheUpdate source scope')
    proof, source_identity = _scope_source()
    fragments = _pinned_fragments(proof, _CACHE_BODIES)
    token = _CACHE_DISPATCH_SCOPE.set((base, context, read, threading.get_ident(), proof, fragments))
    try:
        yield
        if _scope_source()[1] != source_identity:
            raise ValueError('XP2 CacheUpdate source changed during deferred drain')
    finally:
        _CACHE_DISPATCH_SCOPE.reset(token)


def _pinned_fragments(proof, names):
    capture = _source((proof['source']['path'], CAPTURE_SHA))
    fragments = []
    for name in names:
        for fragment in _select_body(proof, capture, name)['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            if len(raw) != fragment['length'] or hashlib.sha256(raw).hexdigest() != fragment['sha256']:
                raise ValueError('Invalid XP2 source fragment: ' + name)
            fragments.append((int(fragment['start_rva'], 16), raw, name))
    return tuple(fragments)


@contextmanager
def event_reader_scope(base, read):
    """Reuse only immutable source proof for one native update on its owner thread."""
    if _EVENT_READER_SCOPE.get() is not None:
        raise RuntimeError('Nested XP2 event reader source scope')
    proof, source_identity = _scope_source()
    fragments = _pinned_fragments(proof, _EVENT_READER_BODIES)
    token = _EVENT_READER_SCOPE.set((base, read, threading.get_ident(), proof, fragments))
    try:
        yield
        if _scope_source()[1] != source_identity:
            raise ValueError('XP2 event reader source changed during native update')
    finally:
        _EVENT_READER_SCOPE.reset(token)


def event_reader_source():
    scope = _EVENT_READER_SCOPE.get()
    if scope is None:
        return _validated_source()
    if threading.get_ident() != scope[2]:
        raise ValueError('XP2 event reader source scope belongs to another thread')
    return scope[3]


def verify_cache(base, context, read, *, registry_key=0):
    from .cache_update_profiles import _registry_snapshot
    scope = _CACHE_DISPATCH_SCOPE.get()
    if scope is None:
        proof = _validated_source()
        _verify_bodies(base, read, _CACHE_BODIES, proof)
    else:
        owner_base, owner_context, owner_read, thread, proof, fragments = scope
        if (base != owner_base or context != owner_context or read is not owner_read
                or threading.get_ident() != thread):
            raise ValueError('XP2 CacheUpdate scope belongs to another owner')
        for rva, raw, name in fragments:
            if _exact(read, base + rva, len(raw)) != raw:
                raise ValueError('XP2 pre-Load live code differs: ' + name)
    _check_owner(base, context, read, proof)
    if _q(read,base+CACHE_OUTER_VTABLE_RVA+0x198) != base+CACHE_DISPATCH_RVA:
        raise ValueError('XP2 cache feedback dispatch slot differs')
    registry_rva = int(proof['deferred']['cache_registry']['buckets_rva'], 16)
    registry = _registry_snapshot(base, read, registry_key, registry_rva)
    return dict(source_sha256=SOURCE[1], bucket_count=registry['bucket_count'],
                registry_entries=registry['entry_count'], native_dispatch_called=False,
                saved_game_load_admitted=False)


def verify_notifications(base, read, *, host_pointer):
    verify_bodies(base,read,('notification_begin','notification_end','notification_stack_grow'))
    if _q(read,base+0xB8AA80) != host_pointer:
        raise ValueError('XP2 notification host differs')


def verify_control(base, context, read, *, host_pointer):
    verify_bodies(base,read,('local_player_update','controller_query'))
    _owner(base,context,read,host_pointer=host_pointer)
    return dict(source_sha256=SOURCE[1], caller_bodies_verified=True,
                local_identity_inferred=False, native_callers_invoked=False,
                saved_game_load_admitted=False)


def verify_reader(base, read):
    scope = _EVENT_READER_SCOPE.get()
    if scope is None:
        verify_bodies(base,read,_EVENT_READER_BODIES)
    else:
        owner_base, owner_read, thread, _, fragments = scope
        if base != owner_base or read is not owner_read or threading.get_ident() != thread:
            raise ValueError('XP2 event reader source scope belongs to another owner')
        for rva, raw, name in fragments:
            if _exact(read, base + rva, len(raw)) != raw:
                raise ValueError('XP2 pre-Load live code differs: ' + name)
    if _q(read,base+0xABF080+0x1D8) != base+0x84E260:
        raise ValueError('XP2 event count slot differs')
    return dict(source_sha256=SOURCE[1], live_reader_verified=True, pointees_copied=False)


def verify_a0_owner(base, context, read, *, host_pointer):
    verify_bodies(base,read,('a0_existing_map','a0_two_fields','a0_three_fields',
        'event_suppressed','session_getter','session_flag','internal_event_dispatch',
        'prepare','session_factory','session_constructor','session_initialize'))
    _owner(base,context,read,host_pointer=host_pointer)
    return dict(source_sha256=SOURCE[1], a0_owner_verified=True,
                c0_admitted=False, saved_game_load_admitted=False)


def source_pins():
    from .paths import resource_root
    p = source()
    capture = _source((p['source']['path'], CAPTURE_SHA))
    refs = [dict(path=str(resource_root()/SOURCE[0]),sha256=SOURCE[1]),
            p['source'],capture['generator'],*p['references'].values()]
    return {str(resolve_path(Path(r['path']))):r['sha256'] for r in refs}

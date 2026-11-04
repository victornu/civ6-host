"""Internal callback cache state, distinct from public player admission.

No native call or mutation: reuse the existing live publication lease and copy
validator. An absent, released or stale cache is refused, never interpreted as
the official gate-off branch during a qualified XP1 continuation.
"""
import hashlib
from .configuration_profiles import XP1_CORE_SHA256, _source
from .saved_load_profiles import XP2_CORE_SHA256
from .loaded_cache_profiles import validate_copy, loaded_cache_abi

GATE_SOURCE = ('evidence/native-player-view-cache-gate.json',
    '2632e4cd0892fe60c6b9e8149edad8c12b9ad00564101d21a98a9a764d2ec6b6')


def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .loaded_cache_profiles import source, SOURCE as XP1_CACHE_SOURCE
    from .cache_facade_profiles import source_pins
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown internal-cache engine')
    gate = _source(GATE_SOURCE)
    if gate['schema'] != 'civ6rl.native_player_view_cache_gate.static.v1':
        raise ValueError('Official callback gate source changed')
    proof = source(core_sha256=core_sha256)
    if core_sha256==XP1_CORE_SHA256:
        selected_source=XP1_CACHE_SOURCE
    else:
        from .xp2_cache_source import SOURCE as XP2_CACHE_SOURCE
        selected_source=XP2_CACHE_SOURCE
    refs = [dict(path=GATE_SOURCE[0], sha256=GATE_SOURCE[1]),
            dict(path=selected_source[0],sha256=selected_source[1]),
            *proof['references'].values()]
    pins = source_pins(core_sha256=core_sha256)
    for ref in refs:
        path=resolve_path(resource_root()/ref['path']).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('Internal-cache source dependency differs: '+ref['path'])
        pins[str(path)] = ref['sha256']
    return pins


def require_internal_cache(continuation):
    """Read actual cache ownership at a producer, not a remembered public flag.

The returned booleans describe the source enable sequence's prerequisites in
this live host. They do not claim the original EXE caller cadence, or expose
additional observations/actions. Call anew before each callback that uses it.
"""
    from .xp1_continuation import SavedContinuation
    from .loaded_cache_publication import LoadedCachePublication
    if type(continuation) is not SavedContinuation:
        raise ValueError('Internal cache requires the exact shared continuation')
    continuation.check(active=True)
    b = continuation.owner
    core_sha256 = b.load_abi.core_sha256
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown internal-cache engine')
    cache_abi = loaded_cache_abi(core_sha256)
    lease = continuation.lease
    publisher = continuation.publisher
    if (type(lease) is not LoadedCachePublication or lease.owner is not b
            or lease.publisher is not publisher or lease.continuation is not continuation
            or lease.core_sha256 != core_sha256
            or lease.attempt.cache_abi is not cache_abi
            or publisher.cache_abi is not cache_abi
            or publisher._closed or publisher.context != b.context
            or publisher.core is not b.core
            or not (lease.entered and lease.returned and lease.copied)
            or not lease.publication_finished or lease.poisoned
            or publisher.native_cache_gate is not False
            or publisher.full_facade_initialization_reproduced is not False):
        raise ValueError('Internal cache lost its populated, private owner')
    facades = lease.require(lease.backend, publisher._facades)
    readback = b.loaded_readback
    state = validate_copy(b.core._handle, b.context, b.runtime.read,
        cache_abi, facades, publisher.cache_map_snapshot,
        expected_game=lease.identity['game'],
        expected_dimensions=(readback['width'], readback['height']))
    return dict(callback_gate_enabled=True, native_cache_initialized=True,
        native_cache_state=state, core_sha256=core_sha256,
        public_runtime_admitted=False, original_exe_caller_cadence=False,
        gate_source_sha256=GATE_SOURCE[1])

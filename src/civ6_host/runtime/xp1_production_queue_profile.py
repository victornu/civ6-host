"""XP1 queue GetAt and the exact captured human queue-tab admission.

This selects native readers and the pinned UI gate; it implements no production
rules. Current legality remains in the common native catalogue/CanStartOperation.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp1-production-queue-static/queue-source-v1.json',
          '904de533550de187085331e6397559d22af6b23c1562f9eee2db0ab45e761fe1')
GET_AT_RVA = 0x5a7770


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_queue_source import SOURCE as selected
        return selected
    raise ValueError('Unknown production queue engine')


def _witness(proof):
    """Observed control route, not a replay of old turn/selection state."""
    for ref in proof['captured_ui_witnesses']:
        row = _source((ref['path'], ref['sha256']))['diagnostics']['ui_availability']
        if (row['schema'] != 'civ6rl.ui_availability.v2' or row['read_only'] is not True
                or row['observed_unchanged'] is not True or row['player_id'] != 0):
            raise ValueError('XP1 queue UI capture identity changed')
        for key in ('active', 'manager_active', 'overlay_enabled'):
            if row['tutorial'][key] != {'status':'observed', 'value':False}:
                raise ValueError('XP1 tutorial queue gate not witnessed inactive')
        if row['tutorial']['any_multiplayer'] != {'status':'observed', 'value':True}:
            raise ValueError('XP1 queue gate requires the captured multiplayer profile')
        for key in ('city_production', 'production_queue_tab'):
            for prop in ('hidden', 'disabled'):
                if row['controls'][key][prop] != {'status':'observed', 'value':False}:
                    raise ValueError('XP1 human queue control route unavailable')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_queue_source import verify_source as selected
        return selected()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Queue profile requires the exact XP1 engine')
    from .xp1_saved_load import REFERENCE
    p = _source(SOURCE)
    binding = p['bindings']['BuildQueue.GetAt']
    if (p['schema'] != 'civ6_host.xp1_production_queue.static.v1'
            or p['image']['sha256'] != core_sha256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False
            or set(p['bindings']) != {'BuildQueue.GetAt'}
            or binding['callback_rva'] != hex(GET_AT_RVA)
            or binding['registrar_rva'] != '0x5a6e40'
            or binding['name_va'] != '0x1808c6508'
            or binding['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'
            or p['capture_manifest']['sha256'] != REFERENCE[1]
            or p['validation'] != dict(exact_registration_pairs=1,
                all_instruction_bytes_match_image=True, conditional_branches_included=True,
                captured_ui_before_after_agree=True, base_intervals=14)):
        raise ValueError('XP1 queue binding or source identity changed')
    for name in (hex(GET_AT_RVA), '0x5a6ce0', '0x62900', '0x61ef0', 'registration:BuildQueue.GetAt'):
        if not p['functions'][name]['instructions']:
            raise ValueError('XP1 queue native helper absent: '+name)
    gate = p['gate']
    if (gate['tutorial_active'] is not False or gate['test_mode'] is not False
            or gate['queue_tab_visible'] is not True or gate['queue_tab_enabled'] is not True
            or gate['immutable_headless_profile'] is not True
            or gate['dynamic_game_state_replayed'] is not False):
        raise ValueError('XP1 queue captured UI gate changed')
    for ref in p['references']:
        _source((ref['path'], ref['sha256']))
    _witness(p)
    return p


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_queue_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 production-queue ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown production queue engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_production_profile import source_dependencies as production_dependencies
    p = verify_source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), p['image'], p['capture_manifest'],
            *p['references'], *p['official_ui_sources'], *p['captured_ui_witnesses']]
    result = production_dependencies()
    for ref in refs:
        path = resolve_path(resource_root()/ref['path']).resolve()
        key = str(path)
        if key in result and result[key] != ref['sha256']:
            raise ValueError('Conflicting XP1 queue source dependency')
        result[key] = ref['sha256']
    return result


def verify_live(base, read, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_production_queue_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown production queue engine')
    from .xp1_status_profiles import _instruction_spans
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('XP1 queue requires a module base and memory reader')
    p = verify_source()
    spans = _instruction_spans(p)
    for rva, raw in spans:
        if read(base+rva, len(raw)) != raw:
            raise ValueError('XP1 queue native instruction changed at '+hex(rva))
    strings = {**p['callback_literals'], p['bindings']['BuildQueue.GetAt']['name_va']:'GetAt'}
    for va, value in strings.items():
        raw = value.encode('ascii')+b'\0'
        if read(base+int(va,16)-0x180000000, len(raw)) != raw:
            raise ValueError('XP1 queue native field literal changed')
    return len(spans)


@dataclass(frozen=True)
class VerifiedQueueSource:
    owner: object
    core: object
    base: int
    inputs: object
    bundle: object
    source_sha256: str
    instruction_read_spans: int


def _check_receipt(owner, core, receipt):
    from .native.native_official_load import OfficialLoadBackend
    from .xp1_saved_load import REFERENCE
    if (type(owner) is not OfficialLoadBackend or owner.core is not core
            or owner.load_abi.core_sha256 != XP1_CORE_SHA256
            or type(receipt) is not VerifiedQueueSource or receipt.owner is not owner
            or receipt.core is not core or receipt.base != core._handle
            or receipt.inputs is not owner.inputs or receipt.bundle is not owner.captured_bundle
            or receipt.bundle.inputs is not receipt.inputs or receipt.bundle.reference != REFERENCE
            or receipt.source_sha256 != SOURCE[1]):
        raise ValueError('XP1 queue source belongs to another saved lifetime')


def bind_owner(owner, core, read):
    """Verify code and immutable capture inputs once on the exact retained owner."""
    from .native.native_official_load import OfficialLoadBackend
    if type(owner) is not OfficialLoadBackend:
        raise ValueError('XP1 queue requires the actual saved Load backend')
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_production_queue_source import bind_owner as selected
        return selected(owner,core,read)
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 != XP1_CORE_SHA256
            or type(core._handle) is not int or core._handle <= 0
            or read != owner.runtime.read or owner.destroyed or owner.poisoned):
        raise ValueError('XP1 queue source owner mismatch')
    old = getattr(owner, '_xp1_production_queue_source_receipt', None)
    if old is not None:
        _check_receipt(owner, core, old)
        return old
    from .xp1_saved_load import validate_candidate_inputs
    from .xp1_production_profile import bind_owner as bind_production
    validate_candidate_inputs(owner.inputs, owner.captured_bundle)
    bind_production(owner, core, read)
    # Pinned UI source/capture bytes are part of this one-time admission, not
    # repeatedly hashed for each offered queue gesture.
    for name, digest in source_dependencies().items():
        with Path(name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('XP1 queue dependency changed: '+name)
    receipt = VerifiedQueueSource(owner, core, core._handle, owner.inputs,
        owner.captured_bundle, SOURCE[1], verify_live(core._handle, read))
    owner._xp1_production_queue_source_receipt = receipt
    return receipt


def gate_admitted(owner):
    """Project the witnessed queue-tab route for this actual continuation only.

    This admits the immutable UI route. It does not assert that a city/action is
    currently legal, replay captured selection, or bypass native strategic gates.
    """
    from .xp1_continuation import SavedContinuation
    if type(owner) is not SavedContinuation:
        raise ValueError('XP1 queue gate requires the actual saved continuation')
    b = owner.owner
    if b.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_production_queue_source import gate_admitted as selected
        return selected(owner)
    owner.check(active=b.busy)
    b.check_thread()
    receipt = getattr(b, '_xp1_production_queue_source_receipt', None)
    _check_receipt(b, b.core, receipt)
    if owner.lease.inputs is not receipt.inputs:
        raise ValueError('XP1 queue gate lost its captured input lease')
    return True

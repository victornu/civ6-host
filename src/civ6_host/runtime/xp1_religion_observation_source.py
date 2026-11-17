"""Exact installed XP1 own-religion snapshot; action admission is separate."""
from hashlib import sha256
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .execution_images import _PROFILE, _XP1_PROFILE
from . import xp2_religious_chain_source as xp2
from .xp1_saved_load import REFERENCE

SOURCE = ('work/x1trade/religion-followup/41e66c1ba0e637826b53d9cdc2ce817ff42a82bee189f0ac86fc2014a6bac8eb.json',
          '41e66c1ba0e637826b53d9cdc2ce817ff42a82bee189f0ac86fc2014a6bac8eb')
_CALLBACKS = {'GetReligionTypeCreated':0x5cf200, 'HasReligiousFoundingUnit':0x5cf2a0,
    'GetNumBeliefsEarned':0x5cf110, 'GetHolyCityID':0x5cf0d0,
    'GetReligions':0x5bbca0, 'HasBeenFounded':0x5bc0e0, 'IsTooManyForReligion':0x5bc300}


def source_for(image):
    if image is _PROFILE:
        return xp2.SOURCE
    if image is _XP1_PROFILE:
        return SOURCE
    raise ValueError('Unqualified saved religion execution image')


def source_hash(core_sha256):
    verify_source(core_sha256)
    return (xp2.SOURCE if core_sha256 == XP2_CORE_SHA256 else SOURCE)[1]


def supports(reference,image):
    return (image is _XP1_PROFILE and reference == REFERENCE) or xp2.supports(reference,image)


def core_for(prefix):
    return XP2_CORE_SHA256 if is_xp2(prefix) else XP1_CORE_SHA256


def is_xp2(prefix):
    return getattr(prefix.backend.core,'_civ6_host_execution_image',None) is _PROFILE


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        return xp2.verify_source()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Own religion snapshot requires the selected Rise and Fall engine')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-own-religion-getter-source.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or {k:int(v['callback']['rva'],16) for k,v in proof['bindings'].items()} != _CALLBACKS
            or proof['observation_abi_qualified'] is not True
            or proof['action_abi_qualified'] is not False
            or proof['functions']['GetReligions']['fragment_count'] != 7
            or proof['functions']['GetReligions']['total_length'] != 1075):
        raise ValueError('Installed own-religion source differs')
    return proof


def _reused(proof):
    ref = next(r for r in proof['references'] if r['sha256'] == proof['reuse']['source_sha256'])
    old = _source((ref['path'],ref['sha256']))
    if old['image']['sha256'] != _XP1_PROFILE.image_sha256:
        raise ValueError('Reused religion facade source differs')
    spans = [old['core_bodies']['player_religion_object']]
    for name in ('Game.GetReligion','Player.GetReligion'):
        spans.extend(old['bindings'][name][key] for key in ('callback','registration'))
        if 'literal' in old['bindings'][name]:
            spans.append(old['bindings'][name]['literal'])
    return spans


def source_dependencies(image, *, reference=None):
    if image is _PROFILE:
        return xp2.source_dependencies(image,reference=reference,family='observation')
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    if image is not _XP1_PROFILE:
        raise ValueError('Own religion snapshot requires the exact installed Rise and Fall image')
    proof = verify_source()
    refs = [dict(path=p,sha256=h) for p,h in (SOURCE,REFERENCE)] + list(proof['references'])
    pins = {}
    for row in refs:
        path = str(resolve_path(resource_root()/row['path']).resolve())
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Own religion source dependency conflict')
    pins[str(Path(image.path).resolve())] = image.image_sha256
    verify_pinned_files(pins)
    return pins


def bind_prefix(prefix):
    if is_xp2(prefix):
        return xp2.bind_prefix(prefix)
    from .saved_load_services import SavedLoadServices
    from .native.native_script_runtime import NativeScriptRuntime
    if type(prefix) is not SavedLoadServices or type(prefix.runtime) is not NativeScriptRuntime:
        raise ValueError('Own religion snapshot requires the actual saved service and Lua owners')
    backend = prefix.backend
    backend.check_thread()
    core = backend.core
    if (prefix.closed or prefix.quarantined or backend.prefix is not prefix
            or prefix.core is not core or prefix.context != backend.context
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or backend.captured_bundle.reference != REFERENCE
            or getattr(core,'_civ6_host_execution_image',None) is not _XP1_PROFILE):
        raise ValueError('Own religion snapshot requires the exact installed Rise and Fall saved owner')
    proof = verify_source()
    lifetime = (core,prefix,prefix.runtime)
    if getattr(prefix,'_xp1_religion_observation_lifetime',None) == lifetime:
        return
    for span in list(proof['spans']) + _reused(proof):
        address = core._handle + int(span['rva'],16)
        # Memory belongs to the backend runtime, not NativeScriptRuntime.
        raw = b''.join(backend.runtime.read(address+offset,min(4096,span['bytes']-offset))
                       for offset in range(0,span['bytes'],4096))
        if type(raw) is not bytes or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live installed own-religion binding differs')
    prefix._xp1_religion_observation_lifetime = lifetime


def require_actions(image=None):
    if image is not None and image is not _XP1_PROFILE and image is not _PROFILE:
        raise ValueError('Unqualified saved religion execution image')
    if image is _PROFILE:
        xp2.verify_source()
    else:
        verify_source()

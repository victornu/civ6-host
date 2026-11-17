"""Source admission for installed XP1 ADD_BELIEF, separate from native coverage."""
from hashlib import sha256
from pathlib import Path
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .execution_images import _PROFILE, _XP1_PROFILE
from . import xp2_religious_chain_source as xp2
from . import xp1_religion_observation_source as snapshot
from . import xp1_pantheon_source as pantheon
from .xp1_saved_load import REFERENCE

SOURCE=('work/x1trade/religion-actions-source/4f0f6c5733ef917c414e8b963cae249725b291201c203b08c74ba104f0013af4.json',
        '4f0f6c5733ef917c414e8b963cae249725b291201c203b08c74ba104f0013af4')
_ENUMS={'PlayerOperations.ADD_BELIEF':4169305636,'PlayerOperations.PARAM_BELIEF_TYPE':2756389127,
        'PlayerOperations.PARAM_INSERT_MODE':2888817673,'PlayerOperations.VALUE_EXCLUSIVE':2550048198}


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
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Belief choices require the selected Rise and Fall engine')
    snapshot.verify_source(core_sha256)
    pantheon.verify_source(core_sha256)
    proof=_source(SOURCE)
    if (proof['schema']!='civ6-host.xp1-religion-actions-source.static.v1'
            or proof['image']['sha256']!=_XP1_PROFILE.image_sha256
            or any(proof['enums'][key]['u32']!=value for key,value in _ENUMS.items())
            or snapshot.SOURCE[1] not in {r['sha256'] for r in proof['references']}
            or proof['native_execution'] is not False or proof['native_coverage_complete'] is not False):
        raise ValueError('Installed ADD_BELIEF source differs')
    ui=proof['ui']
    if sha256(Path(ui['path']).read_bytes()).hexdigest()!=ui['sha256']:
        raise ValueError('Installed ReligionScreen source changed')
    return proof


def actions_qualified():
    proof=verify_source()
    qualification=proof['source_qualification']
    if not all(qualification[key] is True for key in (
            'numeric_request_route_identified','normalizer_and_selected_applicators_complete',
            'shared_request_transport_spans_match_installed_image','known_host_boundaries_reuse_existing_profiles')):
        return False
    if (qualification['native_acceptance_claimed'] is not False
            or qualification['new_host_or_rule_implementation_required_by_known_direct_boundaries'] is not False):
        return False
    for row in proof['references']:
        _source((row['path'],row['sha256']))
    # Reuse the installed source owners for logger, C0, history/era, city scalar,
    # synchronous script events and the existing request/queue lifecycle.
    pantheon.require_actions()
    from .a0_family_source import family_profile
    profile=family_profile()
    for kind,record in ((0x486d648e,0xc5),(0x059d6cc2,0x10e),(0x51c84cba,0x67),(0x55f15a7b,2)):
        if record not in profile.record_types_by_kind.get(kind,frozenset()):
            raise ValueError('Shared ADD_BELIEF event receiver differs')
    return True


def require_actions(image=None):
    if image is not None and image is not _XP1_PROFILE and image is not _PROFILE:
        raise ValueError('Unqualified saved religion execution image')
    if image is _PROFILE:
        from .xp2_direct_religion_source import verify_source as verify_direct
        xp2.require_actions('beliefs')
        verify_direct()
        return
    if not actions_qualified():
        raise ValueError('ADD_BELIEF action dependencies are not qualified')


def source_dependencies(image, *, reference=None):
    if image is _PROFILE:
        from .xp2_direct_religion_source import source_dependencies as direct_dependencies
        return direct_dependencies(image,reference=reference)
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    if image is not _XP1_PROFILE:
        raise ValueError('Belief choices require the exact installed Rise and Fall image')
    proof=verify_source()
    pins=snapshot.source_dependencies(image)
    for path,digest in pantheon.source_dependencies(image).items():
        if pins.setdefault(path,digest)!=digest:
            raise ValueError('Belief source dependency conflict')
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1])]+list(proof['references'])
    for row in refs:
        path=str(resolve_path(resource_root()/row['path']).resolve())
        if pins.setdefault(path,row['sha256'])!=row['sha256']:
            raise ValueError('Belief source dependency conflict')
    pins[str(Path(proof['ui']['path']).resolve())]=proof['ui']['sha256']
    verify_pinned_files(pins)
    return pins


def bind_prefix(prefix, *, action=False):
    if is_xp2(prefix):
        from .xp2_direct_religion_source import bind_prefix as bind_direct
        return bind_direct(prefix,family='beliefs',action=action)
    snapshot.bind_prefix(prefix)
    if action:
        require_actions()
    pantheon.bind_prefix(prefix,action=action)
    proof=verify_source()
    core=prefix.backend.core
    lifetime=(core,prefix,prefix.runtime)
    if getattr(prefix,'_xp1_religion_beliefs_lifetime',None)==lifetime:
        return
    spans=[fragment for body in proof['code_spans'].values() for fragment in body['fragments']]
    spans.extend(row for name,row in proof['data_spans'].items() if name not in proof['callable_vtables'])
    for row in spans:
        address=core._handle+int(row['rva'],16)
        raw=b''.join(prefix.backend.runtime.read(address+offset,min(4096,row['length']-offset))
                     for offset in range(0,row['length'],4096))
        if type(raw) is not bytes or sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Live installed ADD_BELIEF source differs')
    for row in proof['callable_vtables'].values():
        expected=b''.join((core._handle+int(rva,16)).to_bytes(8,'little') for rva in row['target_rvas'])
        raw=prefix.backend.runtime.read(core._handle+int(row['rva'],16),len(expected))
        if raw!=expected:
            raise ValueError('Live installed religion signal callable differs')
    prefix._xp1_religion_beliefs_lifetime=lifetime

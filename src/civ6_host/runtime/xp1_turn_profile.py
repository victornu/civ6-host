"""Selected native turn-transport ABI; this does not admit an XP1 turn loop.

Only already generated messages are delivered. The Core decides whether a
request is allowed and performs its effects; UI gates and first-turn callback
coverage remain the owning session's separate qualification.
"""
from dataclasses import dataclass
import hashlib
import struct

from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE=('work/host-extensions/xp1-turn-static/turn-transport-source-v1.json',
        '375df1eb251627e64b6f697a40ea980a4cff6a284c32a4218181ace3490f9e0d')


@dataclass(frozen=True)
class TurnProfile:
    core_sha256: str
    request_rva: int
    unready_wrapper_rva: int
    unready_wrapper_sha256: str
    tree_ctor_rva: int
    tree_dtor_rva: int
    tree_vtable_rva: int
    tree_lookup_rva: int
    vector_ctor_rva: int
    vector_dtor_rva: int
    vector_vtable_rva: int
    vector_lookup_rva: int
    string_setter_rva: int
    string_storage_rva: int
    reason_converter_rva: int
    processor_flags_rva: int
    completion_guard_description: str


BASE=TurnProfile(BASE_CORE_SHA256,0x42e5c0,0x42e570,
    'ee8f2e38aca1e97745e13c6fd920431480e8f351b3cee8d43d23b13314a0598d',
    0x744b80,0x744ca0,0x81cfa0,0x745d00,0x74b870,0x74b8f0,0x81d838,0x74c5f0,
    0x74d760,0x74d8a0,0x48f440,0x8bb800,'Core02C040 returns while8BB801 is set')
XP1=TurnProfile(XP1_CORE_SHA256,0x4bd6c0,0x4bd670,
    '0bfc6dd50126c7597cfc4da25f5b6071052a41ed615036f2d630f4bf70373c6f',
    0x844460,0x844580,0x93f590,0x845540,0x84b420,0x84b4a0,0x93fe28,0x84c240,
    0x84d300,0x84d430,0x522510,0x9f26e0,'XP1 Core02CDF0 returns while9F26E1 is set')


def source(*, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown turn transport source engine')
    p=_source(SOURCE)
    r=p['profile']
    if (p['schema']!='civ6_host.xp1_turn_transport.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['native_execution'] is not False
            or p['validation']['all_instruction_bytes_match_pinned_images'] is not True
            or p['validation']['all_slots_match_pinned_xp1'] is not True
            or p['validation']['pair_count']!=14
            or r['completion_echo_flags']!=(1,1,0,0)
            or r['turn_loop_admitted'] is not False
            or r['ui_gates_admitted'] is not False
            or r['host_callback_closure_admitted'] is not False):
        raise ValueError('XP1 turn transport source differs')
    for name in XP1.__dataclass_fields__:
        if name in r and r[name]!=getattr(XP1,name):
            raise ValueError('XP1 turn transport address differs: '+name)
    for name in ('tree_ctor','tree_dtor','tree_lookup','vector_ctor','vector_dtor',
                 'vector_lookup','string_setter','string_storage','reason_converter',
                 'unready_wrapper','unready_handler','completion_constructor','completion_guard'):
        if p['comparisons'][name]['equal_after_address_normalization'] is not True:
            raise ValueError('XP1 shared turn primitive differs: '+name)
    # The non-ignored completion branch uses a different Player field in XP1.
    # It remains official code; the host only admits the prior ignore phase.
    guard=p['functions']['xp1']['completion_guard']
    rows=[i for f in _body(guard)['fragments'] for i in f['instructions']]
    if tuple(rows[0]['rip_targets'])!=('0x1809f26e1',) or rows[-1]['text']!='ret':
        raise ValueError('XP1 completion ignore gate differs')
    return p


def turn_profile(core_sha256=BASE_CORE_SHA256):
    if core_sha256==BASE_CORE_SHA256:return BASE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import ABI,source as selected
        selected()
        return ABI
    if core_sha256==XP1_CORE_SHA256:
        source()
        return XP1
    raise ValueError('Native turn transport engine is not qualified')


def require_profile(profile, core_sha256):
    expected=turn_profile(core_sha256)
    if profile is not expected:
        raise ValueError('Native turn transport profile does not belong to this engine')
    return expected


def source_dependencies(*, core_sha256=XP1_CORE_SHA256, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown turn transport source engine')
    if execution_image is not None:raise ValueError('XP1 turn source does not accept an XP2 execution image')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source()
    rows=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references']]
    pins={}
    for row in rows:
        path=resolve_path(resource_root()/row['path']).resolve()
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:
                raise ValueError('Turn transport source dependency changed: '+str(path))
        pins[str(path)]=row['sha256']
    return pins


def verify_live(base, context, read, *, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import verify_live as selected
        return selected(base,read,family='turn',context=context)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown turn transport source engine')
    p=source()
    if int.from_bytes(read(context,8),'little')!=base+0x8a8df0:
        raise ValueError('XP1 turn transport outer interface differs')
    for name,b in p['functions']['xp1'].items():
        for fragment in _body(b)['fragments']:
            for row in fragment['instructions']:
                raw=bytes.fromhex(row['bytes'])
                if read(base+int(row['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 turn transport native body differs: '+name)
    for vt,slots in p['tables'].values():
        for slot,target in slots.items():
            if read(base+vt+int(slot),8)!=struct.pack('<Q',base+target):
                raise ValueError('XP1 turn transport native slot differs')


def prepare_transport(transport):
    """Verify this transport's selected primitive once, before any native call."""
    profile=turn_profile(transport.transport_abi.core_sha256)
    current=getattr(transport,'_turn_abi',None)
    if current is not None and current is not profile:
        raise ValueError('Native turn transport profile was replaced')
    if current is None:
        if profile is not BASE:
            verify_live(transport.core._handle,transport.context,transport.read,
                        core_sha256=profile.core_sha256)
        transport._turn_abi=profile
    return profile


def forced_body_guards(profile, base_guards):
    require_profile(profile,profile.core_sha256)
    if profile is BASE:return base_guards
    if profile.core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import FORCED_BODY_GUARDS
        return FORCED_BODY_GUARDS
    return ((0x84d300,138,'243b799dd9998593e48d36363e43b676b7548dd1f6e40c842d5714acd65453fc'),
            (0x522510,81,'70fa2f46ebc82ce35d29511d2958ba74e4b3fc7834373524bcd10f36cbcc7b24'))


def verify_parameter_source(core_sha256):
    profile=turn_profile(core_sha256)
    if profile is BASE:
        from .native.native_player_operation_request import verify_source_evidence
        verify_source_evidence()
    else:
        source(core_sha256=core_sha256)

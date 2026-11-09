"""Pinned XP2 Culture bindings for the shared government query and request."""
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-policy-controls/government-source.json',
          'bc6a6c88b3ad3ac315fb40df3e25c5249d2d3b4279c508d04d3e32c41f619860')
APPLICATION_SOURCE = ('work/host-extensions/xp2-government-application/application-source-v1.json',
                      'e4ff1d4f4e9b7afcc5c218bfa08896f76d6b101411aab234d1c5b8ca6d61f7ed')
CALLBACKS = {
    'GetCurrentGovernment':0x6acbc0,'IsInAnarchy':0x6ada60,
    'IsGovernmentUnlocked':0x6ad9f0,'GetAnarchyTurns':0x6ac610,
    'GetAnarchyEndTurn':0x6ac5c0,'CanChangeGovernment':0x6ac2e0,
    'CanChangeGovernmentAtAll':0x6ac350,'RequestChangeGovernment':0x6adc50,
    'GovernmentChangeMade':0x6ad7f0,'GovernmentChangeConsidered':0x6ad7a0,
    'SetGovernmentChangeConsidered':0x6ae360,
}


def source():
    proof=_source(SOURCE)
    if (proof['schema']!='civ6-host.xp2-government-api.static.v1'
            or proof['image']['sha256']!=XP2_CORE_SHA256
            or proof['registrar_rva']!=0x6ab780
            or proof['ui']['sha256']!='6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or {key:row['callback_rva'] for key,row in proof['callbacks'].items()}!=CALLBACKS):
        raise ValueError('XP2 government API source differs')
    return proof


def application_source():
    proof=_source(APPLICATION_SOURCE)
    packet=proof['packet']
    targets=[(r['slot'],int(r['target_rva'],16)) for r in packet['vtable_targets']]
    if (proof['schema']!='civ6-host.xp2-government-application.static.v1'
            or proof['image']['sha256']!=XP2_CORE_SHA256
            or proof['reference_profile']['sha256']!=SOURCE[1]
            or packet['constructor_rva']!='0x34630'
            or packet['message_type']!='0xE57882AF' or packet['vtable_rva']!='0x9bdcc0'
            or targets!=[(0,0x346d0),(1,0x34720),(2,0x9b1040),(3,0x34840),
                         (4,0x349e0),(5,0x34c10),(6,0x347a0)]):
        raise ValueError('XP2 government packet/application source differs')
    return proof


def source_dependencies(*, execution_image=None):
    from .a0_family_source import verify_pinned_files
    from .execution_images import runtime_source_pins
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp2_policy_controls_source import source_dependencies as policy_dependencies
    from .native import native_government_actions as government
    from .native import native_government_consideration as consideration
    government.verify_source()
    consideration.verify_source()
    proof=source()
    application=application_source()
    rows=(dict(path=SOURCE[0],sha256=SOURCE[1]),proof['image'],proof['ui'],*proof['references'])
    rows=(*rows,dict(path=APPLICATION_SOURCE[0],sha256=APPLICATION_SOURCE[1]),
          application['capture_script'],application['capture_helper'])
    pins=dict(policy_dependencies(execution_image=execution_image))
    own_pins={str(resolve_path(resource_root()/row['path']).resolve()):row['sha256'] for row in rows}
    pins.update(runtime_source_pins(own_pins, execution_image=execution_image))
    for path,digest in ((government._PROOF,government.PINNED_EVIDENCE_SHA256),
            (government._CURRENT_GOVERNMENT_PROOF,government._CURRENT_GOVERNMENT_PIN),
            (government._TRANSPORT_PROOF,government.TRANSPORT_PROOF_SHA256),
            (consideration._PROOF,consideration.PINNED_EVIDENCE_SHA256)):
        pins[str(resolve_path(path).resolve())]=digest
    verify_pinned_files(pins)
    return pins


def bind_owner(saved):
    backend=saved.backend
    backend.check_thread()
    if backend.load_abi.core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Government inputs require the exact XP2 owner')
    identity=(backend.core._handle,SOURCE[1])
    previous=getattr(backend,'_xp2_government_source',None)
    if previous is not None:
        if previous!=identity: raise ValueError('Government source owner changed')
        return
    from .xp2_policy_source import bind_owner as bind_policy
    bind_policy(saved)
    proof=source()
    application=application_source()
    bodies=list(proof['functions'].values())
    bodies.extend(row['body'] for row in application['packet']['functions'].values())
    bodies.extend(row['body'] for row in application['subtype1_application']['functions'].values())
    for body in bodies:
        for fragment in body['fragments']:
            raw=bytes.fromhex(fragment['raw_hex'])
            rva=int(fragment['start_rva'],16)
            for offset in range(0,len(raw),4096):
                block=raw[offset:offset+4096]
                if backend.runtime.read(backend.core._handle+rva+offset,len(block))!=block:
                    raise ValueError('Live XP2 government binding differs from source')
    table=int(application['packet']['vtable_rva'],16)
    for row in application['packet']['vtable_targets']:
        target=backend.core._handle+int(row['target_rva'],16)
        if backend.runtime.read(backend.core._handle+table+8*row['slot'],8)!=target.to_bytes(8,'little'):
            raise ValueError('Live XP2 government packet vtable differs from source')
    backend._xp2_government_source=identity

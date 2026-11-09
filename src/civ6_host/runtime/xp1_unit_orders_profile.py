"""XP1 source selection for shared official parameterless unit orders.

This verifies bindings and transport source, not a full unit-command surface.
Other orders and the espionage cancellation dialogue remain unqualified.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp1-unit-orders-static/unit-orders-source-v1.json',
        'af79a05f7d352284dbbab6f2846935bc3effd0f4fe1d6eec564692329cd11587')
TRANSPORT_SOURCE=('work/host-extensions/xp1-unit-orders-static/command-transport-v1.json',
                  '2d64b5e911321172f659af920162a6b62732b54812462b18c5f568db2473873e')
UI_SOURCE=('work/host-extensions/xp1-unit-orders-static/ui-resolution-v1.json',
           '95510afa620bb0a0551aae9e07b1cbeb5ff0030c393265116264f283a5d778fd')
CALLBACKS={'Unit.GetFortifyTurns':0x5d8850,'Unit.IsReadyToSelect':0x5d96c0,
 'Unit.GetMovesRemaining':0x5d8bf0,'Unit.GetType':0x5d91c0,
 'UnitManager.GetActivityType':0x5dc340,'UnitManager.CanStartCommand':0x5dbb50,
 'UnitManager.RequestCommand':0x5de980}
REGISTRARS={'Unit':0x5d7410,'UnitManager':0x5db5b0}
COMMAND_TABLE=(0x864420,(0x31180,0x311c0,0x6d8820,0x31270,0x31310,0x31380,0x31250))


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_orders_source import verify_source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unit-order profile requires its exact XP1 engine')
    proof=_source(SOURCE)
    if (proof['schema']!='civ6_host.xp1_unit_orders.static.v1'
            or proof['image']['sha256']!=core_sha256
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['validation']['exact_registration_pairs']!=len(CALLBACKS)
            or proof['validation']['all_instruction_bytes_match_image'] is not True
            or proof['validation']['conditional_branches_included'] is not True
            or set(proof['bindings'])!=set(CALLBACKS)):
        raise ValueError('XP1 unit-order binding source changed')
    for name,rva in CALLBACKS.items():
        row=proof['bindings'][name]
        if (row['callback_rva']!=hex(rva)
                or row['registrar_rva']!=hex(REGISTRARS[name.split('.')[0]])
                or row['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'
                or not proof['functions'][hex(rva)]['instructions']
                or not proof['functions']['registration:'+name]['instructions']):
            raise ValueError('XP1 unit-order binding changed: '+name)
    transport=_source(TRANSPORT_SOURCE)
    if (transport['schema']!='civ6_host.xp1_unit_orders.command_transport.v1'
            or transport['image']!=proof['image'] or transport['native_execution'] is not False
            or transport['process_memory_read'] is not False
            or transport['validation']['all_instruction_bytes_match_image'] is not True
            or transport['table']['rva']!=hex(COMMAND_TABLE[0])
            or tuple(transport['table']['entries'])!=tuple(hex(v) for v in COMMAND_TABLE[1])
            or transport['contracts']['host_send_slot']!='0x70'
            or transport['contracts']['command_message']!='0x493830af'):
        raise ValueError('XP1 unit command archive source changed')
    for reference in (*proof['references'],*transport['references']):
        _source((reference['path'],reference['sha256']))
    from .resource_resolution import resolve_path
    ui=_source(UI_SOURCE)
    if (ui['schema']!='civ6_host.xp1_unit_orders.ui_resolution.v1'
            or ui['replacement_criteria']!='Expansion1' or ui['only_base_include'] is not True
            or ui['replacement_has_overrides'] is not False
            or ui['sources']['base']!=proof['official_ui']):
        raise ValueError('Official XP1 UnitPanel delegation changed')
    for row in ui['sources'].values():
        if hashlib.sha256(resolve_path(Path(row['path'])).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Official unit-order UI source changed')
    return proof


def selected_proof(base_proof,core_sha256):
    if core_sha256==BASE_CORE_SHA256:return base_proof
    verify_source(core_sha256)
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_orders_source import SOURCE as selected
        return selected[1]
    return SOURCE[1]


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_orders_source import source_dependencies as selected
        return selected(execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 unit-order ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown unit-order engine')
    from .resource_resolution import resolve_path
    from .paths import resource_root
    from .xp1_status_profiles import source_dependencies as status
    from .unit_operation_ui_profile import source_dependencies as operation
    proof=verify_source();transport=_source(TRANSPORT_SOURCE);ui=_source(UI_SOURCE)
    refs=[dict(path=p,sha256=s) for p,s in (SOURCE,TRANSPORT_SOURCE,UI_SOURCE)]
    refs += [*proof['references'],*transport['references'],proof['image'],
             *ui['sources'].values(),ui['capture'],ui['capture_content_vectors']]
    result={str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}
    for provider in (status,operation):
        for path,sha in provider().items():
            if path in result and result[path]!=sha:raise ValueError('Conflicting unit-order source pins')
            result[path]=sha
    return result


def verify_live(base,read,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_orders_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown unit-order engine')
    if type(base) is not int or base<=0 or not callable(read):raise ValueError('Expected XP1 module and reader')
    from .xp1_status_profiles import _instruction_spans
    proof=verify_source();spans=(*_instruction_spans(proof),*_instruction_spans(_source(TRANSPORT_SOURCE)))
    for rva,raw in spans:
        if read(base+rva,len(raw))!=raw:raise ValueError('XP1 unit-order instructions changed at '+hex(rva))
    for name,row in proof['bindings'].items():
        text=name.split('.')[1].encode('ascii')+b'\0'
        if read(base+int(row['name_va'],16)-0x180000000,len(text))!=text:
            raise ValueError('XP1 unit-order binding name changed: '+name)
    table,entries=COMMAND_TABLE
    raw=b''.join(struct.pack('<Q',base+rva) for rva in entries)
    if read(base+table,len(raw))!=raw:raise ValueError('XP1 command message vtable changed')
    return len(spans)


@dataclass(frozen=True)
class VerifiedUnitOrderSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    transport_sha256:str
    instruction_read_spans:int


def bind_owner(owner,core,read):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_unit_orders_source import bind_owner as selected
        return selected(owner,core,read)
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0):
        raise ValueError('XP1 unit-order source owner mismatch')
    from .xp1_status_profiles import bind_owner as bind_status
    bind_status(owner,core,read)
    prior=getattr(owner,'_xp1_unit_orders_source_receipt',None)
    if prior is not None:
        if (type(prior) is not VerifiedUnitOrderSource or prior.owner is not owner
                or prior.core is not core or prior.base!=core._handle
                or prior.source_sha256!=SOURCE[1] or prior.transport_sha256!=TRANSPORT_SOURCE[1]):
            raise ValueError('Unit-order source receipt belongs to another lifetime')
        return prior
    from .unit_operation_ui_profile import verify_live as verify_operation
    verify_operation(core._handle,read,core_sha256=XP1_CORE_SHA256)
    receipt=VerifiedUnitOrderSource(owner,core,core._handle,SOURCE[1],TRANSPORT_SOURCE[1],verify_live(core._handle,read))
    owner._xp1_unit_orders_source_receipt=receipt
    return receipt

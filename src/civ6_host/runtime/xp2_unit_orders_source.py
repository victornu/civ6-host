"""Exact XP2 source selection for shared parameterless orders and ordinary cancel.

Native Lua performs argument conversion, legality and requests. The original
command archive and shared host transport retain serialization and ownership;
this profile neither executes commands nor grants arbitrary order capability.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/host-extensions/xp2-unit-orders-static/unit-orders-source-v1.json',
        'df5c61d3c79fa061efaa7e77a7891fbc0c49e02ad0dfe75b2736f46e610ee902')
TRANSPORT_SOURCE=('work/host-extensions/xp2-unit-orders-static/command-transport-v1.json',
                  'd0966318a4227023b87141923edffe12a771d6307f6920f3ec21f1a634083c8e')
UI_SOURCE=('work/host-extensions/xp2-unit-orders-static/ui-resolution-v1.json',
           'cdf5401077c164bb8e0069d19ead22062fd4d20f601181f9f85aec4237fed24b')
SKIP_OPERATIONS_SHA256='00c3c77e74f571471299564c4f6c1a277c9f09d650420dbb01314c27ba8b698f'
CALLBACKS={'Unit.GetFortifyTurns':0x6bcde0,'Unit.IsReadyToSelect':0x6bdc50,
    'Unit.GetMovesRemaining':0x6bd180,'Unit.GetType':0x6bd750,
    'UnitManager.GetActivityType':0x6c0850,'UnitManager.CanStartCommand':0x6c0060,
    'UnitManager.RequestCommand':0x6c2e90}
REGISTRARS={'Unit':0x6bb990,'UnitManager':0x6bfac0}
COMMAND_TABLE=(0x9bef90,(0x3a470,0x3a4b0,0x9b1040,0x3a560,0x33fc0,0x3a600,0x3a540))
_DELEGATED=('GetUnitActionsTable','OnUnitActionClicked','OnUnitActionClicked_CancelSpyMission',
            'LateCheckActionBeforeAdd')
_COMMANDS=('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL')
_OPERATIONS=('UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY','UNITOPERATION_HEAL','UNITOPERATION_RELIGIOUS_HEAL')


def _rows(body):
    return [row for fragment in body['fragments'] for row in fragment['instructions']]


def _bodies(proof):
    for body in proof['functions'].values():
        starts=set();raw_parts=[]
        if body['all_conditional_targets_captured'] is not True:
            raise ValueError('XP2 unit-order body is incomplete')
        for fragment in body['fragments']:
            cursor=int(fragment['start_rva'],16);raw=bytes.fromhex(fragment['raw_hex'])
            copied=b''.join(bytes.fromhex(r['bytes']) for r in fragment['instructions'])
            if (raw!=copied or len(raw)!=fragment['length']
                    or hashlib.sha256(raw).hexdigest()!=fragment['sha256']
                    or cursor+len(raw)!=int(fragment['end_rva_exclusive'],16)):
                raise ValueError('XP2 unit-order fragment bytes differ')
            for row in fragment['instructions']:
                if int(row['rva'],16)!=cursor:raise ValueError('XP2 unit-order instruction boundary differs')
                starts.add(cursor);cursor+=len(bytes.fromhex(row['bytes']))
            raw_parts.append(raw)
        raw=b''.join(raw_parts)
        if len(raw)!=body['bytes'] or hashlib.sha256(raw).hexdigest()!=body['sha256']:
            raise ValueError('XP2 unit-order complete body digest differs')
        for row in _rows(body):
            if (re.fullmatch(r'j(?!mp)[a-z]+ 0x[0-9a-f]+',row['text'])
                    and int(row['text'].split()[-1],16)-0x180000000 not in starts):
                raise ValueError('XP2 unit-order conditional successor is absent')


def _require_instructions(proof, expected):
    for rva,required in expected.items():
        actual={row['text'] for row in _rows(proof['functions'][hex(rva)])}
        if not set(required)<=actual:raise ValueError('XP2 unit-order native caller contract differs')


def _file(reference):
    path=resolve_path(resource_root()/reference['path']).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
        raise ValueError('XP2 unit-order source file changed: '+str(path))
    return path


def source():
    proof=_source(SOURCE);transport=_source(TRANSPORT_SOURCE);ui=_source(UI_SOURCE)
    for p,schema in ((proof,'static'),(transport,'command_transport')):
        if (p['schema']!='civ6_host.xp2_unit_orders.'+schema+'.v1'
                or p['image']['sha256']!=XP2_CORE_SHA256 or p['image']['base']!='0x180000000'
                or p['native_execution'] is not False or p['process_memory_read'] is not False
                or p['validation']['all_instruction_bytes_match_image'] is not True
                or p['validation']['conditional_branches_included'] is not True):
            raise ValueError('XP2 unit-order source identity differs')
        _bodies(p)
    if transport['image']!=proof['image'] or set(proof['bindings'])!=set(CALLBACKS):
        raise ValueError('XP2 unit-order image/binding set differs')
    for name,rva in CALLBACKS.items():
        binding=proof['bindings'][name];registrar=REGISTRARS[name.split('.')[0]]
        actual={row['rva']:row for row in _rows(proof['functions'][hex(registrar)])}
        window=binding['registration_instructions']
        loads=[r for r in window if r['text'].startswith('lea rdx, [rip')]
        names=[r for r in window if r['text'].startswith('lea r8, [rip')]
        if (binding['callback_rva']!=hex(rva) or binding['registrar_rva']!=hex(registrar)
                or binding['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'
                or not _rows(proof['functions'][hex(rva)])
                or any(actual.get(row['rva'])!=row for row in window)
                or len(loads)!=1 or tuple(loads[0]['rip_targets'])!=(hex(0x180000000+rva),)
                or len(names)!=1 or tuple(names[0]['rip_targets'])!=(binding['name_va'],)
                or not {'call 0x1809afd88','call 0x18000dab0'}<={r['text'] for r in window}):
            raise ValueError('XP2 unit-order exact registration differs: '+name)
    if (proof['validation']['exact_registration_pairs']!=7
            or proof['contracts']['manager_slots']!=dict(convert=0x90,can_start=0x48,execute=0x58,deserialize=0x98)
            or tuple(proof['contracts']['lock_slots'])!=(0x40,0x38)
            or proof['contracts']['aux_result_slot']!=0xb0
            or proof['contracts']['native_request_lua_returns']!=0
            or proof['contracts']['spy_cancel_dialogue_admitted'] is not False
            or proof['contracts']['rules_reimplemented'] is not False
            or transport['table']['rva']!=hex(COMMAND_TABLE[0])
            or tuple(transport['table']['entries'])!=tuple(map(hex,COMMAND_TABLE[1]))
            or transport['contracts']['command_message']!='0x493830af'
            or transport['contracts']['host_send_slot']!='0x70'
            or transport['contracts']['shared_send_rva']!='0x366b0'
            or tuple(transport['contracts']['wire_prefix_widths'])!=(4,2,2,4,4,4)):
        raise ValueError('XP2 unit-order command/service ABI differs')
    _require_instructions(proof,{
        0xd0140:('call qword ptr [rax + 0x40]','call qword ptr [rax + 0x38]',
                 'call qword ptr [r10 + 0x90]','call qword ptr [r10 + 0x48]'),
        0x6c0060:('call 0x1800d0140','call qword ptr [rax + 0xb0]'),
        0x6c2e90:('call 0x1800d1a30','movzx eax, word ptr [rsi + 0xec]',
                  'mov eax, dword ptr [rsi + 0xd0]','xor eax, eax'),
        0xd1a30:('call 0x18003a2b0','call 0x180033f70','call 0x1800366b0','call 0x18003a300')})
    _require_instructions(transport,{
        0x3a2b0:('mov dword ptr [rcx + 8], 0x493830af',),
        0x366b0:('call qword ptr [rax + 0x70]',),
        0x3a560:('call qword ptr [r10 + 0x48]','call qword ptr [r9 + 0x58]'),
        0x3a390:('call qword ptr [r8 + 0x98]',)})
    if (ui['schema']!='civ6_host.xp2_unit_orders.ui_resolution.v1'
            or ui['replacement_criteria']!='Expansion2' or ui['replacement_has_overrides'] is not True
            or ui['delegate_only_base_include'] is not True
            or tuple(ui['delegated_functions'])!=_DELEGATED
            or set(ui['replacement_overrides'])&set(_DELEGATED)
            or tuple(ui['parameterless_commands'])!=_COMMANDS
            or tuple(ui['parameterless_operations'])!=_OPERATIONS
            or ui['ordinary_cancel_only'] is not True or ui['spy_cancel_dialogue_admitted'] is not False
            or ui['sources']['base']!=proof['official_ui']):
        raise ValueError('XP2 UnitPanel parameterless delegation differs')
    for row in ui['sources'].values():_file(row)
    for ref in (*proof['references'],*transport['references']):_source((ref['path'],ref['sha256']))
    return proof


def verify_source(core_sha256=XP2_CORE_SHA256):
    if core_sha256!=XP2_CORE_SHA256:raise ValueError('Unit-order source requires its exact XP2 engine')
    return source()


def source_dependencies(*, execution_image=None):
    from .xp1_status_profiles import source_dependencies as status
    from .unit_operation_ui_profile import source_dependencies as operation
    proof=source();transport=_source(TRANSPORT_SOURCE);ui=_source(UI_SOURCE)
    refs=[dict(path=p,sha256=s) for p,s in (SOURCE,TRANSPORT_SOURCE,UI_SOURCE)]
    refs.extend((*proof['references'],*transport['references'],*proof['extractors'],*transport['extractors'],
                 proof['image'],*ui['sources'].values(),*ui['references'],ui['extractor']))
    base_assets = Path(ui['sources']['base']['path']).parents[2]
    refs.append(dict(path=str(base_assets/'Gameplay/Data/UnitOperations.xml'),
                     sha256=SKIP_OPERATIONS_SHA256))
    inventory=_source(tuple(proof['references'][-1][k] for k in ('path','sha256')))
    refs.extend(inventory['references'])
    if execution_image is not None:
        image_path=Path(resolve_path(resource_root()/proof['image']['path'])).resolve()
        if (str(image_path)!=str(Path(execution_image.path).resolve())
                or proof['image']['sha256']!=execution_image.reference_core_sha256):
            raise ValueError('XP2 unit-order provenance differs from the selected execution/reference pair')
    pins={}
    for ref in refs:
        path=Path(resolve_path(resource_root()/ref['path'])).resolve()
        if execution_image is None or ref != proof['image']:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
                raise ValueError('XP2 unit-order source dependency changed: '+str(path))
        pins[str(path)]=ref['sha256']
    from .runtime_source_dependencies import materialize_runtime_source_pins
    pins=materialize_runtime_source_pins(pins, execution_image=execution_image,
        provenance_images=(proof['image'],))
    execution_options = ({'execution_image': execution_image}
                         if execution_image is not None else {})
    for provider in (status,operation):
        for path,digest in provider(core_sha256=XP2_CORE_SHA256, **execution_options).items():
            if path in pins and pins[path]!=digest:raise ValueError('Conflicting XP2 unit-order source pins')
            pins[path]=digest
    from .a0_family_source import verify_pinned_files
    verify_pinned_files(pins)
    return pins


def verify_live(base,read):
    """Check full retained bodies, names and relocated table; execute no native code."""
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('Expected exact XP2 module and checked reader')
    proof=source();count=0
    def equal(rva,raw,label):
        nonlocal count
        for offset in range(0,len(raw),4096):
            chunk=raw[offset:offset+4096];actual=read(base+rva+offset,len(chunk))
            if type(actual) is not bytes or actual!=chunk:
                raise ValueError('XP2 unit-order '+label+' changed at '+hex(rva+offset))
            count+=1
    for p in (proof,_source(TRANSPORT_SOURCE)):
        for body in p['functions'].values():
            for f in body['fragments']:equal(int(f['start_rva'],16),bytes.fromhex(f['raw_hex']),'body')
    for name,row in proof['bindings'].items():
        equal(int(row['name_va'],16)-0x180000000,name.split('.')[1].encode('ascii')+b'\0','binding name')
    for rva,row in proof['literals'].items():equal(int(rva,16),bytes.fromhex(row['raw_hex']),'native literal')
    table,entries=COMMAND_TABLE
    equal(table,b''.join(struct.pack('<Q',base+rva) for rva in entries),'command vtable')
    return count


@dataclass(frozen=True)
class VerifiedUnitOrderSource:
    owner:object
    core:object
    base:int
    source_sha256:str
    transport_sha256:str
    instruction_read_spans:int
    core_sha256:str=XP2_CORE_SHA256


def bind_owner(owner,core,read):
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0):
        raise ValueError('XP2 unit-order source owner mismatch')
    from .xp1_status_profiles import bind_owner as bind_status
    bind_status(owner,core,read)
    prior=getattr(owner,'_xp2_unit_orders_source_receipt',None)
    if prior is not None:
        if (type(prior) is not VerifiedUnitOrderSource or prior.owner is not owner or prior.core is not core
                or prior.base!=core._handle or prior.source_sha256!=SOURCE[1]
                or prior.transport_sha256!=TRANSPORT_SOURCE[1] or prior.core_sha256!=XP2_CORE_SHA256):
            raise ValueError('XP2 unit-order source receipt belongs to another lifetime')
        return prior
    from .unit_operation_ui_profile import verify_live as verify_operation
    verify_operation(core._handle,read,core_sha256=XP2_CORE_SHA256)
    result=VerifiedUnitOrderSource(owner,core,core._handle,SOURCE[1],TRANSPORT_SOURCE[1],verify_live(core._handle,read))
    owner._xp2_unit_orders_source_receipt=result
    return result

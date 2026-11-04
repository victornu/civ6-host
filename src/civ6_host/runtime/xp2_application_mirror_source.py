"""XP2 native bodies for the existing bounded EXE mirror/prelude algorithm.

This is source selection, not session admission or a replacement Game rule.
All provider calls remain native; ownership and failure handling remain shared.
"""
import hashlib
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source, _body

SOURCE=('work/host-extensions/xp2-application-mirror/source-profile-v1.json',
        'e1241f8dcab67dee4166b9f818f55d070fee5cf53ef79a755cb4eb77a6c7cce8')
METHODS=dict(constructor=0x99e4b0,allocate=0x990900,hash=0x9a0000,integer=0x99fee0,
    owned_map=0x9a0240,allocator_set=0x99fbe0,allocator_get=0x989d0,
    finish=0x9a4290,delete=0x99e8b0,lookup=0x99f570,notify=0x9a4460,tree_next=0x994d90)
ALIASES={'provider_allocator':'allocator_get','provider_notify':'notify',
         'source_scalar_setter':'integer'}
PRELUDE_NAMES=(*METHODS,'base_constructor','destructor','base_destructor',
    'variant_clone_assign','variant_release','variant_temporary_constructor',
    'variant_temporary_destructor','variant_move_assign','tree_insert','tree_successor')


def fragments(proof):
    for name,body in proof['bodies'].items():
        parts=[]
        for fragment in body['fragments']:
            raw=bytes.fromhex(fragment['raw_hex']);parts.append(raw)
            if (len(raw)!=fragment['length'] or hashlib.sha256(raw).hexdigest()!=fragment['sha256']
                    or ''.join(i['bytes'] for i in fragment['instructions'])!=raw.hex()
                    or any(int(i['va'],16)!=0x180000000+int(i['rva'],16)
                           for i in fragment['instructions'])):
                raise ValueError('XP2 application source fragment differs: '+name)
            yield name,int(fragment['start_rva'],16),raw
        raw=b''.join(parts)
        if (raw.hex()!=body['raw_hex'] or len(raw)!=body['bytes']
                or hashlib.sha256(raw).hexdigest()!=body['sha256']
                or body['all_conditional_targets_captured'] is not True
                or body['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2',
                                                   'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 application complete body differs: '+name)


def source():
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp2-application-mirror.source.v1'
            or p['native_execution'] is not False or p['core_sha256']!=XP2_CORE_SHA256
            or p['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or dict(p['method_rvas'])!=METHODS or len(p['bodies'])!=41
            or len(p['comparisons'])!=24
            or any(row['normalized_instructions_equal'] is not True for row in p['comparisons'].values())):
        raise ValueError('XP2 application source identity/comparison differs')
    expected=dict(host_slot=0x130,argument_vtable_rva=0xabf918,argument_getter_rva=0x9a5da0,
        phase_key_rva=0xb8c424,phase_key=0x24084b20,notification_gate_rva=0xb68d40,
        host_global_rva=0xb8aa80,argument_missing_sentinel_rva=0xb90c60,
        provider_nonnullable_sentinel_rva=0xb90808,game_kind=0x2e6f8494,player_kind=0x6d134254,
        property_key=0xa1e5a149,player_index_key=0xf06a2af2,game_argument_count=1,
        player_argument_count=2,property_tag=3,index_tag=2,prelude_map_bytes=88,
        prelude_owned_map_tag=10,prelude_owned_map_flags=0x05000000,
        copy_creates_absent_destination=False,assignment_return_ignored=True,
        borrowed_success_has_no_provider_release=True,
        failed_expansion_allocations_retained_not_speculatively_freed=True,
        closed_B_requires_null_observer_control=True,player_copy_appends_actual_journal=True,
        game_copy_has_no_journal=True,unknown_shapes_or_reentry_refused=True,
        common_exe_algorithm_reused=True,game_rules_reimplemented=False,
        native_validation_required=True,full_exe_application_equivalence=False)
    if any(p['contract'][k]!=v for k,v in expected.items()):
        raise ValueError('XP2 application ownership/dispatch contract differs')
    layouts=dict(argument_vector=dict(begin=40,end=48,capacity=56,stride=32,key=0,variant=8),
        provider_header=dict(size=88,vtable=0,parent=8,observer=16,control=24,allocator=32),
        variant=dict(size=24,tag=0,payload=8,count=16,flags=20),
        tree=dict(sentinel=48,first=56,root=64,count=80,key=32,variant=40,right=0,left=8,parent=16))
    if any(dict(p['contract'][k])!=v for k,v in layouts.items()):
        raise ValueError('XP2 application object layout differs')
    list(fragments(p))
    return p


def _pins(proof):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    pins={}
    refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*proof['references'],
          *(proof[k] for k in ('generator','boundary_helper','extractor'))]
    for ref in refs:
        path=resolve_path(resource_root()/ref['path']).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('XP2 application source dependency differs: '+str(path))
        pins[str(path)]=ref['sha256']
    return pins


def source_dependencies():
    p=source();pins=_pins(p)
    # The owner source independently authenticates the actual A/B provider,
    # player key namespace, and retained complete lookup/copy functions.
    from .xp2_configuration_profile import source_dependencies as owner_dependencies
    pins.update(owner_dependencies())
    return pins


def body(name):
    return _body(source()['bodies'][ALIASES.get(name,name)])


def prelude_source():
    p=source()
    functions={name:_body(p['bodies'][name]) for name in PRELUDE_NAMES}
    starts={int(f['instructions'][0]['rva'],16) for b in functions.values() for f in b['fragments']}
    if not set(METHODS.values())<=starts:
        raise ValueError('XP2 prelude directly invoked method is not captured')
    return dict(core_functions=functions,method_rvas=dict(METHODS),source_sha256=SOURCE[1],static_only=True)


def verify_live(base,read,*,prelude_only=False):
    p=source();count=0
    for name,rva,raw in fragments(p):
        if prelude_only and name not in PRELUDE_NAMES:continue
        if read(base+rva,len(raw))!=raw:
            raise ValueError('Loaded XP2 application instruction differs: '+name)
        count+=len(raw)
    for key,target in p['slots'].items():
        table,slot=(int(v,16) for v in key.split('+'))
        if read(base+table+slot,8)!=struct.pack('<Q',base+int(target,16)):
            raise ValueError('Loaded XP2 application virtual target differs')
    if not prelude_only:
        if read(base+0xb8c424,4)!=struct.pack('<I',0x24084b20):
            raise ValueError('Loaded XP2 LAST_TURN_PHASE_TYPE selector differs')
        if read(base+0xb68d40,1)!=b'\1':
            raise ValueError('XP2 application notification publication is disabled')
    return dict(source_sha256=SOURCE[1],code_bytes_checked=count,selector=0x24084b20,
                saved_game_load_admitted=False,native_callback_observed=False)

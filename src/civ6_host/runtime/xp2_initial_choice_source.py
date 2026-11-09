"""Exact XP2 initial-choice source selection; native rules remain native.

One private proof covers existing status, research and ordinary production
interfaces. It is source/ABI verification, not native effect admission.
"""
import hashlib
import re
from types import MappingProxyType
from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-initial-choices/source-profile-v2.json',
 'dd224972c1d91878fc14ce79bf7ebb31ecb78c572a4b43304da151eabd97060a')
CURRENT_LITERAL_SOURCE = (
 'work/bbg751-turn-source-scope/actual-core-092-integration/initial-choice-literal-compatibility-v1.json',
 '5a3b5632b6f45aac87f87b0910a2e0aef672cee681d90d10d0d03acf287da185')


def _execution_literal_spans(proof, execution_image):
    """Expected bytes for five exact current-image spans; never rewrite memory."""
    if execution_image is None:
        return {}
    from .execution_images import identity
    image = identity(execution_image)
    supplement = _source(CURRENT_LITERAL_SOURCE)
    if (supplement['schema'] != 'civ6-host.xp2-initial-choice-literal-compatibility.v1'
            or supplement['reference']['proof_sha256'] != SOURCE[1]
            or supplement['reference']['image_sha256'] != image['reference_core_sha256']
            or supplement['current']['image_sha256'] != image['image_sha256']
            or supplement['current']['image_path'] != image['path']
            or supplement['comparison'] != dict(literal_count=2009, exact_matches=2004,
                                                mismatches=5, unmapped=0)):
        raise ValueError('Initial-choice literal supplement differs from the selected image')
    result = {}
    for row in supplement['mismatches']:
        rva = int(row['rva'], 16) if isinstance(row['rva'], str) else row['rva']
        original = proof['literals'][hex(rva)]
        before, after = bytes.fromhex(row['old_raw_hex']), bytes.fromhex(row['new_raw_hex'])
        if (rva in result or original['raw_hex'] != row['old_raw_hex']
                or original['bytes'] != row['length'] or len(after) != row['length']
                or hashlib.sha256(before).hexdigest() != row['old_raw_sha256']
                or hashlib.sha256(after).hexdigest() != row['new_raw_sha256']):
            raise ValueError('Initial-choice paired literal bytes differ')
        result[rva] = after
    if set(result) != {0x9be590, 0xac0b70, 0xabfb20, 0xabf2b0, 0x9bdc20}:
        raise ValueError('Initial-choice exact literal span set differs')
    return result
CALLBACKS = {'status': {'Game.GetCurrentGameTurn': 6926160,
            'Game.GetLocalPlayer': 6928560,
            'Game.GetLocalObserver': 6928496,
            'Game.GetWinningTeam': 6933408,
            'Game.IsAllowStrategicCommands': 6933600,
            'Player.GetID': 6986720,
            'Player.GetTeam': 6988016,
            'Player.IsAlive': 6988944,
            'Player.WasEverAlive': 6989952,
            'Player.IsHuman': 6989232,
            'Player.IsTurnActive': 6989664,
            'Player.IsTurnActiveComplete': 6989808,
            'Player.CanUnreadyTurn': 6984768,
            'Map.GetGridSize': 6956080,
            'PlayerManager.GetAliveMajorIDs': 7021776,
            'gameplay/Player.IsHuman': 7266912,
            'gameplay/Game.GetCurrentGameTurn': 7170928,
            'gameplay/Map.GetGridSize': 97904,
            'gameplay/PlayerManager.GetAliveMajorIDs': 7292496},
 'research': {'Player.GetTechs': 6988160,
              'Player.GetCulture': 6985808,
              'Techs.CanResearch': 7033968,
              'Techs.GetResearchingTech': 7034992,
              'Culture.CanProgress': 6996896,
              'Culture.GetProgressingCivic': 7000464},
 'production': {'Player.GetCities': 6985536,
                'PlayerCities.Members': 6992592,
                'City.GetID': 6859792,
                'City.GetOwner': 6860256,
                'City.GetBuildQueue': 6858592,
                'City.GetBuildings': 6859088,
                'CityBuildings.IsPillaged': 6871920,
                'BuildQueue.GetSize': 6867504,
                'BuildQueue.GetCurrentProductionTypeHash': 6866624,
                'BuildQueue.GetPreviousProductionTypeHash': 6867120,
                'BuildQueue.GetProductionYield': 6867200,
                'BuildQueue.HasProductionProgress': 6868496,
                'BuildQueue.GetTurnsLeft': 6867584,
                'BuildQueue.GetUnitProgress': 6868272,
                'BuildQueue.GetUnitCost': 6868160,
                'BuildQueue.GetBuildingProgress': 6866048,
                'BuildQueue.GetBuildingCost': 6865936,
                'BuildQueue.GetDistrictProgress': 6866896,
                'BuildQueue.GetDistrictCost': 6866784,
                'BuildQueue.GetProjectProgress': 6867392,
                'BuildQueue.GetProjectCost': 6867280,
                'BuildQueue.GetCurrentProductionTypeModifier': 6866704,
                'BuildQueue.GetUnitCorpsCost': 6868048,
                'BuildQueue.GetUnitArmyCost': 6867936,
                'BuildQueue.CanProduce': 6863328,
                'CityManager.CanStartOperation': 6885936,
                'CityManager.RequestOperation': 6888320}}
REGISTRARS = {'Game': 6922832,
 'Player': 6982800,
 'Map': 6952272,
 'PlayerManager': 7019808,
 'gameplay/Game': 7167104,
 'gameplay/Player': 7261136,
 'gameplay/Map': 92208,
 'gameplay/PlayerManager': 7290208,
 'Techs': 7033024,
 'Culture': 6993792,
 'PlayerCities': 6991264,
 'City': 6856544,
 'CityBuildings': 6868960,
 'BuildQueue': 6862064,
 'CityManager': 6884832}
ENTRIES = {'parameter_ctor': 10112864,
 'parameter_dtor': 10112992,
 'set_u32': 10118384,
 'lookup': 10116432,
 'reason_ctor': 10085552,
 'reason_dtor': 10085840,
 'can_start': 5831728,
 'request': 5838096}
VTABLES = {'outer': 10551784, 'parameters': 11270424, 'reasons': 11268224}
ENUMS = {'PlayerOperationTypes.RESEARCH': 1848062833,
 'PlayerOperationTypes.PROGRESS_CIVIC': 2678441256,
 'PlayerOperationTypes.PARAM_INSERT_MODE': 2888817673,
 'PlayerOperationTypes.VALUE_EXCLUSIVE': 2550048198,
 'PlayerOperationTypes.PARAM_TECH_TYPE': 347601064,
 'PlayerOperationTypes.PARAM_CIVIC_TYPE': 2786034420,
 'CityOperationTypes.BUILD': 739199558,
 'CityOperationTypes.PARAM_BUILDING_TYPE': 3040219410,
 'CityOperationTypes.PARAM_DISTRICT_TYPE': 1605245423,
 'CityOperationTypes.PARAM_UNIT_TYPE': 2395106579,
 'CityOperationTypes.PARAM_PROJECT_TYPE': 2818811211,
 'CityOperationTypes.MILITARY_FORMATION_TYPE': 2126768863,
 'CityOperationTypes.PARAM_INSERT_MODE': 2888817673,
 'CityOperationTypes.VALUE_EXCLUSIVE': 2550048198,
 'CityOperationTypes.PARAM_QUEUE_DESTINATION_LOCATION': 2688392346,
 'CityOperationTypes.VALUE_REPLACE_AT': 2912129934,
 'MilitaryFormationTypes.STANDARD_FORMATION': 0,
 'MilitaryFormationTypes.CORPS_FORMATION': 1,
 'MilitaryFormationTypes.ARMY_FORMATION': 2}
SLOTS = ((10551784, 536, 5838096),
 (10551784, 544, 5831728),
 (11270424, 96, 10116432),
 (11270424, 304, 10118384),
 (11270424, 0, 10113392),
 (11270424, 384, 10113728),
 (11270424, 448, 10086176),
 (11268224, 0, 10086576),
 (11268224, 96, 10089920),
 (11268224, 304, 10092256),
 (11268224, 384, 10087664),
 (11268224, 448, 10086176),
 (10677744, 0, 6845632),
 (10684968, 0, 6884832),
 (10686384, 0, 6896000),
 (10686792, 0, 6898336),
 (10701040, 0, 7019808),
 (10705368, 0, 7043168),
 (10705696, 0, 7045120),
 (10711880, 0, 7076544),
 (10713016, 0, 7091760),
 (10720448, 0, 7189360),
 (10739672, 0, 7409872),
 (10740024, 0, 7414224),
 (10740376, 0, 7416448),
 (10741000, 0, 7418144),
 (10754776, 0, 7591488),
 (10754944, 0, 7592000),
 (10755120, 0, 7592336),
 (10755344, 0, 7602704),
 (10755688, 0, 7605552),
 (10755816, 0, 7605696),
 (10756104, 0, 7607760),
 (10756264, 0, 7608032),
 (10756640, 0, 7609568),
 (10757032, 0, 7610656),
 (10757264, 0, 7611120),
 (10757456, 0, 7611408),
 (10758064, 0, 7612832),
 (10758576, 0, 7614048),
 (10758776, 0, 7615312),
 (10740160, 0, 7415872),
 (10692968, 0, 6982800),
 (10214376, 0, 239744),
 (10214376, 8, 213712),
 (10214376, 16, 10162240),
 (10214376, 24, 213936),
 (10214376, 32, 214208),
 (10214376, 40, 214272),
 (10214376, 48, 213872),
 (11270424, 56, 10110048))

_VALIDATED_BODY_PROFILE = None


def _validate_complete_bodies(p):
    """Check expensive complete-body structure once per frozen proof object."""
    global _VALIDATED_BODY_PROFILE
    if type(p) is MappingProxyType and _VALIDATED_BODY_PROFILE is p:
        return
    starts=set()
    for b in p['functions'].values():
        parts=[]
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(r['bytes'] for r in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 complete native fragment changed')
            cursor=int(f['start_rva'],16)
            for r in f['instructions']:
                if int(r['rva'],16)!=cursor:raise ValueError('XP2 instruction boundary changed')
                starts.add(cursor);cursor+=len(bytes.fromhex(r['bytes']))
        raw=b''.join(parts)
        if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
            raise ValueError('XP2 complete native body changed')
    for b in p['functions'].values():
        for f in b['fragments']:
            for r in f['instructions']:
                if re.fullmatch(r'j(?!mp)[a-z]+ 0x[0-9a-f]+',r['text']):
                    if int(r['text'].split()[-1],16)-0x180000000 not in starts:
                        raise ValueError('XP2 conditional successor missing from selected source')
    if type(p) is MappingProxyType:
        _VALIDATED_BODY_PROFILE=p


def source(family):
    if type(family) is not str or family not in CALLBACKS:
        raise ValueError('Unknown XP2 initial-choice source family')
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp2-initial-choices.static.v2'
            or p['image']['sha256']!=XP2_CORE_SHA256
            or any(p[k] is not False for k in ('native_execution','process_memory_read','runtime_modified'))
            or p['validation']['function_count']!=304 or p['validation']['total_bytes']!=112790
            or p['validation']['all_bytes_match_installed_image'] is not True
            or p['validation']['explicit_conditional_targets_closed'] is not True
            or tuple(p['validation']['code_relocations']) or dict(p['vtables'])!=VTABLES
            or tuple((r['table_rva'],r['offset'],r['target_rva']) for r in p['slots'])!=SLOTS
            or {k:p['entries'][k] for k in ENTRIES}!=ENTRIES
            or {k:v['u32_value'] for k,v in p['enums'].items()}!=ENUMS
            or p['contracts']['player_operation']['parameter_storage_bytes']!=72
            or p['contracts']['player_operation']['reason_storage_bytes']!=96
            or p['contracts']['native_effects_verified'] is not False):
        raise ValueError('XP2 initial-choice source contract changed')
    for group,names in CALLBACKS.items():
        if tuple(p['families'][group])!=tuple(names):raise ValueError('XP2 getter family changed')
        for name,rva in names.items():
            b=p['bindings'][name]
            if (b['callback_rva']!=rva or b['registrar_rva']!=REGISTRARS[name.split('.')[0]]
                    or b['lua_callback_abi']!='int __cdecl(LuaState*) / Windows x64'
                    or hex(rva) not in p['functions']):raise ValueError('XP2 named registration changed')
    _validate_complete_bodies(p)
    return p


def source_dependencies(family="status", *, execution_image=None):
    from .xp1_ui_binding import source_dependencies as ui_dependencies
    p=source(family);pins=dict(ui_dependencies(core_sha256=XP2_CORE_SHA256))
    if execution_image is not None:
        _execution_literal_spans(p, execution_image)
        pins[str(resolve_path(resource_root()/CURRENT_LITERAL_SOURCE[0]).resolve())] = CURRENT_LITERAL_SOURCE[1]
    if family in ('research','production'):
        from .xp2_action_transport_source import source_dependencies as transport_dependencies
        pins.update(transport_dependencies(execution_image=execution_image))
    for ref in (dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'],*p['extractors']):
        path=resolve_path(resource_root()/ref['path']).resolve(strict=True)
        actual=hashlib.sha256(path.read_bytes()).hexdigest();name=str(path)
        if actual!=ref['sha256'] or name in pins and pins[name]!=actual:
            raise ValueError('XP2 initial-choice dependency changed: '+name)
        pins[name]=actual
    return pins


def verify_live(base,read,family,*,execution_image=None):
    """Guard all selected complete bodies, slots and names without calling Core."""
    if type(base) is not int or base<=0 or not callable(read):
        raise ValueError('XP2 initial-choice source requires an exact module/reader')
    p=source(family);count=0
    for b in p['functions'].values():
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);rva=int(f['start_rva'],16)
            for offset in range(0,len(raw),4096):
                chunk=raw[offset:offset+4096]
                if bytes(read(base+rva+offset,len(chunk)))!=chunk:
                    raise ValueError('XP2 initial-choice native body changed at '+hex(rva+offset))
                count+=1
    for table,offset,target in SLOTS:
        if bytes(read(base+table+offset,8))!=(base+target).to_bytes(8,'little'):
            raise ValueError('XP2 initial-choice native slot changed')
    for name,b in p['bindings'].items():
        raw=name.split('.')[1].encode('ascii')+b'\0'
        if bytes(read(base+b['name_rva'],len(raw)))!=raw:raise ValueError('XP2 getter literal changed')
    literal_spans = _execution_literal_spans(p, execution_image)
    for rva,b in p['literals'].items():
        expected = literal_spans.get(int(rva,16), bytes.fromhex(b['raw_hex']))
        if bytes(read(base+int(rva,16),b['bytes']))!=expected:
            selected = execution_image.id if execution_image is not None else 'reference-only'
            raise ValueError('XP2 native owner/type literal changed at '+rva+' ('+selected+')')
    for name,b in p['enums'].items():
        raw=name.split('.')[1].encode('ascii')+b'\0'
        if bytes(read(base+b['name_rva'],len(raw)))!=raw:raise ValueError('XP2 operation enum name changed')
    return count

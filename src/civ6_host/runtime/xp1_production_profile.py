"""Source selection for official XP1 production readers and command submission.

No production rule or native callback is recreated. Source verification is not
native command qualification, and this profile never claims every production
interface (placement, queue editing, formations and purchases remain separate).
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib

from .configuration_profiles import XP1_CORE_SHA256, _source

from .configuration_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp1-production-static/production-source-v1.json',
          'f7c6082a8053360ebadfdf510fc572fa9b05c8f7a33d01013e6071de287e5e57')
CALLBACKS = {
    'Player.GetCities': 0x5c51b0, 'PlayerCities.Members': 0x5c6d50,
    'City.GetID': 0x5a6560, 'City.GetOwner': 0x5a6730,
    'City.GetBuildQueue': 0x5a60f0, 'City.GetBuildings': 0x5a62a0,
    'CityBuildings.IsPillaged': 0x5a94c0,
    'BuildQueue.GetSize': 0x5a8380, 'BuildQueue.GetCurrentProductionTypeHash': 0x5a8010,
    'BuildQueue.GetPreviousProductionTypeHash': 0x5a8200,
    'BuildQueue.GetProductionYield': 0x5a8250, 'BuildQueue.HasProductionProgress': 0x5a8760,
    'BuildQueue.GetTurnsLeft': 0x5a83d0, 'BuildQueue.GetUnitProgress': 0x5a8680,
    'BuildQueue.GetUnitCost': 0x5a8610, 'BuildQueue.GetBuildingProgress': 0x5a7dd0,
    'BuildQueue.GetBuildingCost': 0x5a7d60, 'BuildQueue.GetDistrictProgress': 0x5a8120,
    'BuildQueue.GetDistrictCost': 0x5a80b0, 'BuildQueue.GetProjectProgress': 0x5a8310,
    'BuildQueue.GetProjectCost': 0x5a82a0,
    'BuildQueue.GetCurrentProductionTypeModifier': 0x5a8060,
    'BuildQueue.GetUnitCorpsCost': 0x5a85a0, 'BuildQueue.GetUnitArmyCost': 0x5a8530,
    'BuildQueue.CanProduce': 0x5a7330, 'CityManager.CanStartOperation': 0x5acb80,
    'CityManager.RequestOperation': 0x5ad4d0,
}
REGISTRARS = {'Player': 0x5c4630, 'PlayerCities': 0x5c6820, 'City': 0x5a58f0,
              'CityBuildings': 0x5a8930, 'BuildQueue': 0x5a6e40, 'CityManager': 0x5ac730}
CITY_MESSAGE = (0x863078, (0x31690, 0x2b1b0, 0x6d8820, 0x2b290, 0x2b3a0, 0x2b3e0, 0x2b250))


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import SOURCE as selected
        return selected
    raise ValueError('Unknown initial-choice source engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import source
        return source('production')
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Production profile requires its exact XP1 engine')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.xp1_production.static.v1'
            or proof['image']['sha256'] != core_sha256
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['validation']['exact_registration_pairs'] != len(CALLBACKS)
            or proof['validation']['all_instruction_bytes_match_image'] is not True
            or proof['validation']['conditional_branches_included'] is not True
            or set(proof['bindings']) != set(CALLBACKS)):
        raise ValueError('XP1 production binding source changed')
    for name, rva in CALLBACKS.items():
        binding = proof['bindings'][name]
        if (binding['callback_rva'] != hex(rva)
                or binding['registrar_rva'] != hex(REGISTRARS[name.split('.')[0]])
                or binding['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'
                or not proof['functions'][hex(rva)]['instructions']):
            raise ValueError('XP1 production getter contract changed: ' + name)
    table, entries = CITY_MESSAGE
    if tuple(int(value,16) for value in proof['tables'][hex(table)]['entries']) != entries:
        raise ValueError('XP1 city-operation message ABI changed')
    if len(proof['references']) != 4:
        raise ValueError('XP1 production source closure is incomplete')
    for reference in proof['references']:
        _source((reference['path'], reference['sha256']))
    from .resource_resolution import resolve_path
    ui = proof['official_ui']
    if hashlib.sha256(resolve_path(Path(ui['path'])).read_bytes()).hexdigest() != ui['sha256']:
        raise ValueError('Official production interface source changed')
    return proof


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import source_dependencies as selected
        return selected('production', execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 production source ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError("Unknown production source engine")
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_status_profiles import source_dependencies as status_dependencies
    from .unit_operation_ui_profile import source_dependencies as operation_dependencies
    proof = verify_source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), *proof['references'],
            proof['image'], proof['official_ui']]
    result = {str(resolve_path(resource_root()/r['path'])): r['sha256'] for r in refs}
    for provider in (status_dependencies, operation_dependencies):
        for path, sha in provider().items():
            if path in result and result[path] != sha:
                raise ValueError('Conflicting production source dependencies')
            result[path] = sha
    return result


def verify_live(base, read, core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import verify_live as selected
        return selected(base,read,'production',execution_image=execution_image)
    if execution_image is not None:raise ValueError('Selected production image requires the XP2 source ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError("Unknown production live source engine")
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Expected XP1 module base and memory reader')
    proof = verify_source()
    from .xp1_status_profiles import _instruction_spans
    spans = _instruction_spans(proof)
    for rva, raw in spans:
        if read(base+rva, len(raw)) != raw:
            raise ValueError('XP1 production instruction bytes changed at ' + hex(rva))
    table, entries = CITY_MESSAGE
    expected = b''.join((base+entry).to_bytes(8,'little') for entry in entries)
    if read(base+table, len(expected)) != expected:
        raise ValueError('XP1 city message table changed')
    for name, binding in proof['bindings'].items():
        value = name.split('.')[1].encode('ascii')+b'\0'
        if read(base+int(binding['name_va'],16)-0x180000000, len(value)) != value:
            raise ValueError('XP1 production binding literal changed: '+name)
    return len(spans)


@dataclass(frozen=True)
class VerifiedProductionSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    instruction_read_spans: int


def bind_owner(owner, core, read):
    """Verify immutable code once per exact live saved backend, never cache state."""
    owner.check_thread()
    core_sha=owner.load_abi.core_sha256
    if core_sha==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import SOURCE as selected_source
    elif core_sha==XP1_CORE_SHA256:selected_source=SOURCE
    else:raise ValueError("Unknown production source owner engine")
    if (owner.core is not core
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('XP1 production source owner mismatch')
    from .xp1_status_profiles import bind_owner as bind_status
    bind_status(owner, core, read)
    existing = getattr(owner, '_xp1_production_source_receipt', None)
    if existing is not None:
        if (type(existing) is not VerifiedProductionSource or existing.owner is not owner
                or existing.core is not core or existing.base != core._handle
                or existing.source_sha256 != selected_source[1]):
            raise ValueError('XP1 production receipt belongs to another lifetime')
        return existing
    image=getattr(core,'_civ6_host_execution_image',None)
    receipt = VerifiedProductionSource(owner, core, core._handle, selected_source[1],
        verify_live(core._handle, read,core_sha256=core_sha,
                    **({'execution_image':image} if image is not None else {})))
    owner._xp1_production_source_receipt = receipt
    return receipt

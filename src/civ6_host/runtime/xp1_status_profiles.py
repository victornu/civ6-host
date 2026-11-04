"""XP1 reader source profile; no native invocation or protocol policy.

Call bind_owner with the OfficialLoadBackend retained by SavedLoadOwner after
its engine identity was verified. Its immutable
receipt is owner/module bound; Lua reads reuse that receipt, never cached data.
"""
from dataclasses import dataclass
from collections.abc import Mapping

from civ6_host.runtime.configuration_profiles import _source, XP1_CORE_SHA256

from .configuration_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp1-session-status-static/status-source-v2.json',
          'c4d85cd54747bff54712c4ff5b88da3eb49b1a2ab276b782b4263e710c8e2c66')
CALLBACKS = {
    'Game.GetCurrentGameTurn': 0x5b68a0, 'Game.GetLocalPlayer': 0x5b7200,
    'Game.GetLocalObserver': 0x5b71c0, 'Game.GetWinningTeam': 0x5b84f0,
    'Game.IsAllowStrategicCommands': 0x5b85b0,
    'Player.GetID': 0x5c5650, 'Player.GetTeam': 0x5c5b60,
    'Player.IsAlive': 0x5c5f00, 'Player.WasEverAlive': 0x5c62f0,
    'Player.IsHuman': 0x5c6020, 'Player.IsTurnActive': 0x5c61d0,
    'Player.IsTurnActiveComplete': 0x5c6260, 'Player.CanUnreadyTurn': 0x5c4ea0,
    'Map.GetGridSize': 0x5bddd0, 'PlayerManager.GetAliveMajorIDs': 0x5cdf50,
    'gameplay/Player.IsHuman': 0x6073c0,
    'gameplay/Game.GetCurrentGameTurn': 0x5f2650,
    'gameplay/Map.GetGridSize': 0x016c80,
    'gameplay/PlayerManager.GetAliveMajorIDs': 0x60d7b0,
}
REGISTRARS = {'Game': 0x5b5ba0, 'Player': 0x5c4630,
              'Map': 0x5bcea0, 'PlayerManager': 0x5cd7a0,
              'gameplay/Game': 0x5f1760, 'gameplay/Player': 0x605d30,
              'gameplay/Map': 0x015690, 'gameplay/PlayerManager': 0x60cec0}
SLOTS = ((0x8d4cd8, 0, 0x62b360), (0x8d4e28, 0, 0x62b780),
         (0x8d4eb0, 0, 0x62bdf0))


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import SOURCE as selected
        return selected
    raise ValueError('Unknown initial-choice source engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import source
        return source('status')
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('XP1 status source refuses another engine')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.xp1_session_status.static.v2'
            or proof['image']['sha256'] != core_sha256
            or proof['native_execution'] is not False
            or proof['process_memory_read'] is not False
            or proof['runtime_modified'] is not False
            or proof['validation']['all_captured_instruction_bytes_match_image'] is not True
            or proof['validation']['exact_name_callback_pairs_verified'] != 19
            or proof['validation']['conditional_leaf_branches_retained'] is not True):
        raise ValueError('XP1 status source identity changed')
    bindings = proof['bindings']
    if not isinstance(bindings, Mapping) or set(bindings) != set(CALLBACKS):
        raise ValueError('XP1 status getter set changed')
    for name, rva in CALLBACKS.items():
        row = bindings[name]
        if (row['callback_rva'] != hex(rva)
                or row['registrar_rva'] != hex(REGISTRARS[name.split('.')[0]])
                or row['source_body'] != hex(rva)
                or row['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'
                or not proof['functions'][hex(rva)]['instructions']):
            raise ValueError('XP1 status getter contract changed: '+name)
    if bindings['Game.GetWinningTeam']['result'] != 'zero values or (number,number)':
        raise ValueError('XP1 winning result arity changed')
    slots = tuple((int(row['table_rva'],16), row['offset'], int(row['target_rva'],16))
                  for row in proof['registration_slots'])
    if slots != SLOTS:
        raise ValueError('XP1 status registration service slots changed')
    for ref in proof['references']:
        _source((ref['path'],ref['sha256']))
    return proof


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError("Unknown status source engine")
    """Exact private source join; ordinary runtime source files are pinned separately."""
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    proof = verify_source()
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]), *proof['references']]
    # The retained UI and configuration proofs carry their own exact source refs.
    # Reuse those providers to close their existing dependencies, rather than
    # duplicate their ownership/layout verification in this getter profile.
    from civ6_host.runtime.xp1_ui_binding import source_dependencies as ui_dependencies
    result = dict(ui_dependencies())
    from civ6_host.runtime.configuration_profiles import OWNERSHIP_SOURCE
    ownership = _source(OWNERSHIP_SOURCE)
    for row in ownership['source_refs'].values():
        _source((row['path'],row['sha256']))
        refs.append(row)
    for row in refs:
        result[str(resolve_path(resource_root()/row['path']).resolve())] = row['sha256']
    return result


def _instruction_spans(proof):
    """Coalesce adjacent instructions; one read per span, not per instruction."""
    data = {}
    for body in proof['functions'].values():
        for row in body['instructions']:
            address = int(row['va'],16)-0x180000000
            raw = bytes.fromhex(row['bytes'])
            if not raw or not 0 <= address < 0x1000000:
                raise ValueError('Invalid XP1 source instruction')
            for offset, value in enumerate(raw):
                previous = data.setdefault(address+offset,value)
                if previous != value:
                    raise ValueError('Conflicting overlapping XP1 source body')
    spans = []
    for address in sorted(data):
        if not spans or address != spans[-1][0] + len(spans[-1][1]):
            spans.append((address, bytearray()))
        spans[-1][1].append(data[address])
    return tuple((address,bytes(raw)) for address,raw in spans)


def verify_live(base, read, core_sha256=XP1_CORE_SHA256):
    """Read-only guards, intended once per actual owner/module lifetime.

    Caller has already verified the full loaded engine SHA. Does not execute
    getters, establish a player perspective, or certify a victory transition.
    """
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import verify_live as selected
        return selected(base,read,'status')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError("Unknown status live source engine")
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Expected native XP1 module base and reader')
    proof = verify_source()
    spans = _instruction_spans(proof)
    for rva, raw in spans:
        if read(base+rva,len(raw)) != raw:
            raise ValueError('XP1 status instruction bytes changed at '+hex(rva))
    for table, offset, target in SLOTS:
        if read(base+table+offset,8) != (base+target).to_bytes(8,'little'):
            raise ValueError('XP1 status registration slot changed')
    for name,row in proof['bindings'].items():
        text = name.split('.')[1].encode('ascii')+b'\0'
        if read(base+int(row['name_va'],16)-0x180000000,len(text)) != text:
            raise ValueError('XP1 status getter literal changed: '+name)
    return len(spans)


@dataclass(frozen=True)
class VerifiedStatusSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    core_sha256: str
    instruction_read_spans: int


def bind_owner(owner, core, read):
    """Reuse immutable source verification only for this exact live owner/core."""
    owner.check_thread()
    core_sha=owner.load_abi.core_sha256
    if core_sha==XP2_CORE_SHA256:
        from .xp2_initial_choice_source import SOURCE as selected_source
    elif core_sha==XP1_CORE_SHA256:selected_source=SOURCE
    else:raise ValueError("Unknown status source owner engine")
    if (owner.core is not core
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('XP1 status source owner mismatch')
    existing = getattr(owner,'_xp1_status_source_receipt',None)
    if existing is not None:
        if (type(existing) is not VerifiedStatusSource or existing.owner is not owner
                or existing.core is not core or existing.base != core._handle
                or existing.source_sha256 != selected_source[1]
                or existing.core_sha256 != core_sha):
            raise ValueError('XP1 status source receipt belongs to another lifetime')
        return existing
    spans = verify_live(core._handle,read,core_sha256=core_sha)
    result = VerifiedStatusSource(owner,core,core._handle,selected_source[1],core_sha,spans)
    owner._xp1_status_source_receipt = result
    return result

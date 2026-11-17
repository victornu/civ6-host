"""Explicit stock Rise and Fall custom-icon foundation, on the saved owner."""

from copy import deepcopy
from pathlib import Path

from civ6_host.contracts import religion_custom_names as contract

from . import xp1_religion_founding_source as foundation_source
from . import xp1_religion_name_transport as transport
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .locale_text import attach as attach_locale, source_files as locale_sources
from .native import native_religion_founding as founding
from .native import native_saved_religion as religion
from .native.native_locale_diagnostic import _native_string_bytes
from .native.native_player_observation import observe_player
from .native.native_player_operation_request import request_player_operation
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1trade/religion-custom-name-edit-mode-stage/editbox-input-contract.json',
          '78912a80ac6533209f759104abe94178bae3f1597a489e4a4d582942fdec437f')
_PROGRAMMATIC_SOURCE = ('work/x1trade/religion-custom-name-edit-mode-stage/programmatic-set-text.json',
                        '1eceb91e5e388847da2d2bd38783c957d6f9beffb294ba4f28a3a8dc64e447e2')
KIND = contract.KIND
UI_INVALID = 'religion_custom_name_invalid'
NATIVE_REFUSED = 'native_religion_foundation_can_start_false'
_MAX_WIRE = 2 * 1024**2
_DEFAULT = 'LOC_RELIGION_CUSTOM'
_PROGRAMMATIC_COPY_BYTES = 255
_FORMAT = b'{1: upper}'
_CONSTRUCTOR = 0xbfb0
_HEX_LUA = br"""
local function hex(text)
 assert(type(text)=='string','Religion text is missing')
 return (text:gsub(".",function(c) return string.format("%02x",string.byte(c)) end))
end
"""
_CONTEXT_LUA = br"""
local function context()
 assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and
        Game.GetCurrentGameTurn()==expectedTurn,'foreign or stale religion name boundary')
end
context()
"""
_CATALOG_LUA = br"""
assert(religion:GetReligionTypeCreated()==expectedCreated,'own religion changed')
local caps=assert(GameInfo.GameCapabilities,'religion capability table missing')
local canRename=caps.CAPABILITY_RENAME~=nil
local lookup=assert(Locale.Lookup,'native Locale lookup missing')
local placeholder=hex(lookup("LOC_UI_RELIGION_CHOOSE_RELIGION_NAME"))
local own='-'
if expectedCreated>=0 then
 local row=nil
 local published=Game.GetReligion():GetReligions()
 assert(type(published)=='table' and #published<=4096,'invalid religion list')
 for _,r in ipairs(published) do
  if r.Founder==pid then
   assert(not row and r.Religion==expectedCreated,'own religion row mismatch')
   row=r
  end
 end
 assert(row,'own religion row missing')
 if row.CustomName~=nil then own=hex(row.CustomName) end
end
local visits=0
local rows={}
if due then
 assert(bits(PlayerOperations.PARAM_RELIGION_CUSTOM_NAME,'custom name parameter')==182311263,
        'custom name operation enum changed')
 for row in GameInfo.Religions() do
  visits=visits+1
  assert(visits<=4096,'religion catalogue exceeded transport bound')
  if row.Pantheon==false and row.RequiresCustomName and
     gameReligion:HasBeenFounded(row.Index)==false then
   local h=bits(row.Hash,'custom religion hash')
   assert(type(row.Index)=='number' and row.Index%1==0 and row.Index>=0 and
          row.Index<=2147483647,'custom religion index outside native domain')
   -- The captured stock profile has this same source key for every custom icon.
   assert(row.Name=="LOC_RELIGION_CUSTOM",'unqualified custom religion default source')
   rows[#rows+1]={index=row.Index,hash=h,name=hex(lookup(row.Name))}
  end
 end
end
table.sort(rows,function(a,b) return a.index<b.index end)
local out={canRename and '1' or '0',placeholder,own}
for _,r in ipairs(rows) do
 out[#out+1]=string.format('%.0f',r.index)..':'..string.format('%.0f',r.hash)..':'..r.name
end
assert((caps.CAPABILITY_RENAME~=nil)==canRename and religion:GetReligionTypeCreated()==expectedCreated,
       'religion name context changed')
context()
return table.concat(out,'|')
"""
_OWN_LUA = br"""
local religion=assert(Players[pid]:GetReligion(),'own religion unavailable')
assert(religion:GetReligionTypeCreated()==expectedCreated,'own religion changed')
local own=nil
local rows=Game.GetReligion():GetReligions()
assert(type(rows)=='table' and #rows<=4096,'invalid religion list')
for _,row in ipairs(rows) do
 if row.Founder==pid then
  assert(not own and row.Religion==expectedCreated,'own religion row mismatch')
  own=row
 end
end
assert((expectedCreated>=0)==(own~=nil),'own religion row missing')
context()
if not own or own.CustomName==nil then return '-' end
return hex(own.CustomName)
"""
_EFFECT_LUA = br"""
assert(gameReligion:HasBeenFounded(expectedCreated)==true,'native founded icon is not published')
local row=GameInfo.Religions[expectedCreated]
assert(row and row.Index==expectedCreated and row.Pantheon==false and row.RequiresCustomName and
       bits(row.Hash,'custom religion hash')==expectedHash,'published custom religion definition changed')
"""


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def require_actions():
    proof = _source(SOURCE)
    programmatic = _source(_PROGRAMMATIC_SOURCE)
    capture, uppercase = proof['capture'], proof['uppercase']
    if (proof['schema'] != 'civ6-host.xp1-religion-name-edit-mode.static.v1'
            or proof['native_execution'] is not False
            or proof['name_contract']['typed_max_scalar_count'] != contract.MAX_INPUT_SCALARS
            or uppercase['native_format'].encode('ascii') != _FORMAT
            or uppercase['explicit_source_byte_length'] != len(_FORMAT)
            or uppercase['toUTF8_mode'] != 1
            or uppercase['imports']['??0String@Localization@@QEAA@PEBDI@Z']['export_rva'] != _CONSTRUCTOR
            or (capture['locale'], capture['dictionary_flag']) != ('fr_FR', False)
            or _DEFAULT not in capture['localization_sql_witness']
            or capture['files'][0]['sha256'] != REFERENCE[1]
            or programmatic['schema'] != 'civ6-host.xp1-religion-name-programmatic-copy.static.v1'
            or programmatic['parent']['sha256'] != SOURCE[1]
            or programmatic['default_scope']['safe_content_bytes_max'] != _PROGRAMMATIC_COPY_BYTES
            or programmatic['locale_constructor_storage']['rva'] != _CONSTRUCTOR
            or programmatic['locale_constructor_storage']['library']['sha256'] != uppercase['localization_dll']['sha256']):
        raise ValueError('Rise and Fall custom religion input source differs')
    foundation_source.require_actions()
    transport.verify_source()
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Custom religion foundation requires the installed Rise and Fall image')
    proof = require_actions()
    locale_pins, _ = locale_sources(execution_image=image)
    pins = {}
    for source in (foundation_source.source_dependencies(image), transport.source_dependencies(image), locale_pins):
        for path, digest in source.items():
            if pins.setdefault(path, digest) != digest:
                raise ValueError('Conflicting Rise and Fall custom religion dependencies')
    refs = [dict(path=p, sha256=h) for p,h in (SOURCE, _PROGRAMMATIC_SOURCE)]
    refs += [proof['exe'], *proof['lua'],
            proof['uppercase']['localization_dll'], *proof['capture']['files']]
    for ref in refs:
        path = Path(ref['path'])
        path = str(resolve_path(path if path.is_absolute() else resource_root() / path).resolve())
        if pins.setdefault(path, ref['sha256']) != ref['sha256']:
            raise ValueError('Conflicting Rise and Fall custom religion source pins')
    verify_pinned_files(pins)
    return pins


def _bind(saved, *, action=False):
    if action:
        saved._check_active()
    else:
        saved._check_query()
    prefix = saved.prefix
    if (getattr(saved, 'xp1_religion_custom_names', False) is not True
            or not supports(saved.backend.captured_bundle.reference,
                getattr(prefix.core, '_civ6_host_execution_image', None))):
        raise ValueError('Custom religion naming requires the exact Rise and Fall saved owner')
    foundation_source.bind_prefix(prefix, action=action)
    if prefix.ui_child is None or prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Custom religion naming requires a published actor and drained queues')
    return prefix


def _identity(observation):
    from .xp1_religion_founding import _identity as founding_identity
    return founding_identity(observation)


def _context(pid, turn, own, *, catalogue=False):
    created = own['religion_type_created']
    due = religion.applicability(own)['foundation'] and own['num_beliefs_earned'] > 0
    if catalogue and due:
        source = founding._context_prefix(pid, turn, core_sha256=XP1_CORE_SHA256)
        source += b'local religion=playerReligion\n'
    else:
        source = f'local pid,expectedTurn={pid},{turn}\n'.encode('ascii') + _CONTEXT_LUA
        if catalogue:
            source += b'local religion=assert(Players[pid]:GetReligion())\n'
    return (source + f"local expectedCreated,due={created},{str(due).lower()}\n".encode('ascii')
            + _HEX_LUA)


def _text(value):
    raw = bytes.fromhex(value.decode('ascii'))
    if raw.hex().encode('ascii') != value or b'\0' in raw:
        raise ValueError('Malformed native religion name bytes')
    return raw.decode('utf-8', errors='strict')


def _parse_catalog(wire, own):
    if type(wire) is not bytes or not 0 < len(wire) < _MAX_WIRE:
        raise ValueError('Malformed native custom religion catalogue payload')
    rename, placeholder, name, *rows = wire.split(b'|')
    if rename not in (b'0', b'1'):
        raise ValueError('Invalid native religion rename capability')
    icons = []
    for item in rows:
        index, bits, default = item.split(b':')
        default_name = _text(default)
        if not default_name:
            raise ValueError('Native custom religion default is empty')
        if rename == b'0' and len(default_name.encode('utf-8')) > _PROGRAMMATIC_COPY_BYTES:
            # Only the installed programmatic SetText path's non-growing pool
            # branch is proved. This is never an input/action contract limit.
            raise ValueError('Unqualified programmatic religion default text')
        icons.append(dict(index=founding._parse_uint(index, 'custom icon index', 0x7fffffff),
                          hash=founding._parse_uint(bits, 'custom icon hash'), default_name=default_name))
    return dict(own=own, own_custom_name=None if name == b'-' else _text(name),
        status='catalog' if icons else 'not_due', rename_allowed=rename == b'1',
        placeholder=_text(placeholder), custom_icons=icons)


def _catalogue(prefix, observation):
    pid, turn = _identity(observation)
    own = religion.validate_observation(prefix.inspect_own_religion_snapshot(pid), pid, turn,
                                        core_sha256=XP1_CORE_SHA256)
    attach_locale(prefix)
    localization = prefix.runtime.service_owner.manifest.get('localization_bootstrap')
    if (not isinstance(localization, dict) or localization.get('locale') != 'fr_FR'
            or localization.get('dictionary_flag') is not False):
        raise ValueError('Rise and Fall custom religion localization profile differs')
    wire = prefix.runtime.evaluate_text(prefix.ui_child, _context(pid, turn, own, catalogue=True) + _CATALOG_LUA,
        b'@explicit_xp1_custom_religion_catalogue', capacity=_MAX_WIRE)
    result = _parse_catalog(wire, own)
    contract.project(result, pid, turn, observation=observation)
    return result


def catalogue(saved, observation):
    result = _catalogue(_bind(saved), observation)
    saved.explicit_religion_custom_names = deepcopy(result)
    return result


def _public(value):
    if 'schema' in value:
        return value
    own = value['own']
    return contract.project(value, own['player_id'], own['current_game_turn'])


def actions(value):
    return contract.actions(None if value is None else _public(value))


def choose(value, template, parameters=None):
    return contract.choose(_public(value), template, parameters)


def _read_own_custom_name(prefix, own, pid, turn, *, expected_hash=None):
    if expected_hash is None:
        source = _context(pid, turn, own)
    else:
        source = founding._context_prefix(pid, turn, require_unfounded=False, core_sha256=XP1_CORE_SHA256)
        source += f"local expectedCreated,expectedHash={own['religion_type_created']},{expected_hash}\n".encode('ascii')
        source += _HEX_LUA + _EFFECT_LUA
    wire = prefix.runtime.evaluate_text(prefix.ui_child, source + _OWN_LUA,
        b'@explicit_xp1_own_custom_religion_name', capacity=_MAX_WIRE)
    return None if wire == b'-' else _text(wire)


def read_own_custom_name(saved, observation):
    prefix = _bind(saved)
    pid, turn = _identity(observation)
    own = religion.validate_observation(prefix.inspect_own_religion_snapshot(pid), pid, turn,
                                        core_sha256=XP1_CORE_SHA256)
    return _read_own_custom_name(prefix, own, pid, turn)


def _uppercase(prefix, value):
    native = prefix.runtime.service_owner.localization_library
    return _native_string_bytes(native, _FORMAT, (value.encode('utf-8'),),
        explicit_length=True, constructor_rva=_CONSTRUCTOR)


def _refusal(before, code, request=None):
    return dict(status='refused', observation=deepcopy(before), refusal_code=code,
                request=request, source_sha256=SOURCE[1])


def apply(saved, action, before):
    prefix = _bind(saved, action=True)
    contract.validate_action(action)
    pid, turn = _identity(before)
    fresh = _catalogue(prefix, before)
    selected = {k: action[k] for k in ('kind', 'index', 'hash')}
    if fresh != getattr(saved, 'explicit_religion_custom_names', None) or selected not in actions(fresh):
        raise RuntimeError('Custom religion choice is stale or unavailable')
    name = action['custom_name']
    parameters = {'name': name} if fresh['rename_allowed'] else None
    if choose(fresh, selected, parameters) != action:
        raise ValueError('Custom religion choice differs from the official localized default')
    if fresh['rename_allowed'] and _uppercase(prefix, name) == _uppercase(prefix, fresh['placeholder']):
        return _refusal(before, UI_INVALID)

    native_parameters = {transport.PARAM_INSERT_MODE: transport.VALUE_EXCLUSIVE,
                         transport.PARAM_RELIGION_TYPE: action['hash'],
                         transport.PARAM_RELIGION_CUSTOM_NAME: name.encode('utf-8')}
    result = request_player_operation(prefix.core, prefix.context, pid, transport.FOUND_RELIGION,
        native_parameters, core_sha256=XP1_CORE_SHA256, read=prefix.backend.runtime.read,
        allow_religion_name=True)
    prefix.emit('native_player_operation_request_returned', kind='found-custom-religion', **result)
    if not result['can_start']:
        if result['request_invoked'] or prefix.actions.pending or prefix.deferred_events.pending:
            raise RuntimeError('Refused custom religion foundation queued native effects')
        return _refusal(before, NATIVE_REFUSED, result)
    if not result['request_invoked'] or len(prefix.actions.pending) != 1:
        raise RuntimeError('Custom religion foundation must emit one native request archive')
    archive = transport.verify_archive(prefix.actions.pending[0], pid, native_parameters)
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()

    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    if _identity(after) != (pid, turn):
        raise RuntimeError('Custom religion foundation crossed actor/turn')
    own = religion.validate_observation(prefix.inspect_own_religion_snapshot(pid), pid, turn,
                                        core_sha256=XP1_CORE_SHA256)
    expected = dict(founder=pid, religion_index=action['index'], belief_indices=[])
    if (own['religion_type_created'] != action['index'] or own['own_religion'] != expected
            or own['holy_city'] != fresh['own']['holy_city']
            or own['num_beliefs_earned'] != fresh['own']['num_beliefs_earned']
            or _read_own_custom_name(prefix, own, pid, turn, expected_hash=action['hash']) != name):
        raise RuntimeError('Custom religion native readback differs from the selected name and icon')
    saved.explicit_religion_custom_names = None
    prefix.emit('official_explicit_religion_custom_name_effect', action=action, archive=archive,
        source_sha256=SOURCE[1], religion_before=fresh, religion_after=own)
    return dict(status='completed', observation=after, selected_index=action['index'],
                selected_hash=action['hash'], custom_name=name, source_sha256=SOURCE[1])

"""Declared content in a serialized official configuration, never activation.

The saved records use MOD_ID/MOD_VERSION, not the ModId member of the separate
runtime mod registry. Preserve record order and unknown fields; a missing list
is not an empty list. No installed mod or database is substituted here.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from civ6_host.runtime.native.official_configuration import read_provider
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash
KEYS = {'GAME_ROOT': 2266848099, 'RULESET': 883024472, 'ENABLED_MODS': 462213576, 'MOD_ID': 79978324, 'MOD_VERSION': 4099409680, 'MOD_TITLE_KEY': 808771954, 'MOD_SUBSCRIPTION_ID': 1840313746}
MAX_MODS = 256

def _map(value, name):
    if (value.tag, value.extra, value.flags, value.size) != (10, 0, 83886080, 0):
        raise ValueError(name + ' is not the serialized property-map profile')
    return {v.key: v for v in value.children}

def _string(value, name, *, max_bytes=65536, empty=False):
    if value is None:
        raise ValueError('Missing saved ' + name)
    if value.tag != 5 or value.extra != 0 or len(value.payload) > max_bytes:
        raise ValueError('Saved ' + name + ' is not a bounded narrow string')
    text = value.scalar()
    if not isinstance(text, str) or '\x00' in text or (not empty and (not text)):
        raise ValueError('Invalid saved ' + name)
    return text

def inspect_content(configuration: bytes):
    """Read one complete provider; return declarations with provenance only."""
    if type(configuration) is not bytes or not 0 < len(configuration) <= 1024 * 1024:
        raise ValueError('Expected bounded immutable configuration bytes')
    if any((game_configuration_hash(name) != key for name, key in KEYS.items())):
        raise RuntimeError('Saved content field hashes changed')
    values, end = read_provider(configuration)
    if end != len(configuration):
        raise ValueError('Trailing bytes after saved content provider')
    roots = {v.key: v for v in values}
    if KEYS['GAME_ROOT'] not in roots:
        raise ValueError('Missing saved GAME_ROOT')
    game = _map(roots[KEYS['GAME_ROOT']], 'GAME_ROOT')
    ruleset = _string(game.get(KEYS['RULESET']), 'RULESET', max_bytes=256)
    mods = game.get(KEYS['ENABLED_MODS'])
    rows = None
    if mods is not None:
        if (mods.tag, mods.extra, mods.flags, mods.size) != (11, 0, 285212672, 0):
            raise ValueError('Saved ENABLED_MODS is not the serialized vector profile')
        if len(mods.children) > MAX_MODS:
            raise ValueError('Saved mod count exceeds bound')
        rows = []
        seen = set()
        for index, value in enumerate(mods.children):
            members = _map(value, 'saved mod record')
            mod_id = _string(members.get(KEYS['MOD_ID']), 'MOD_ID', max_bytes=256)
            try:
                mod_id.encode('ascii')
            except UnicodeEncodeError as exc:
                raise ValueError('Saved MOD_ID is not ASCII') from exc
            if mod_id.lower() in seen:
                raise ValueError('Duplicate saved MOD_ID')
            seen.add(mod_id.lower())
            version = _string(members.get(KEYS['MOD_VERSION']), 'MOD_VERSION', max_bytes=256)
            optional = {}
            for name in ('MOD_TITLE_KEY', 'MOD_SUBSCRIPTION_ID'):
                if KEYS[name] in members:
                    optional[name] = _string(members[KEYS[name]], name, empty=True)
            known_fields = {KEYS[n] for n in ('MOD_ID', 'MOD_VERSION', 'MOD_TITLE_KEY', 'MOD_SUBSCRIPTION_ID')}
            unknown = [dict(key=hex(v.key), tag=v.tag, extra=v.extra, flags=hex(v.flags), size=v.size, serialized_sha256=hashlib.sha256(configuration[v.offset:v.end]).hexdigest()) for v in value.children if v.key not in known_fields]
            rows.append(dict(mod_id=mod_id, version=version, optional=optional, unknown_fields=unknown, serialized_index=index, record_offset=value.offset))
    identity = dict(ruleset=ruleset, mods=None if rows is None else [dict(mod_id=r['mod_id'], version=r['version']) for r in rows])
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(schema='civ6rl.saved_content_declaration926.v1', configuration_sha256=hashlib.sha256(configuration).hexdigest(), configuration_bytes=len(configuration), declared_ruleset=ruleset, enabled_mods_property_present=mods is not None, declared_mods=rows, identity=identity, identity_sha256=digest, order_meaning='Serialized record order only; not activation or execution order.', native_activation_verified=False, script_selection_verified=False, database_binding_verified=False, strategic_training_ready=False)

def compare_content(before: bytes, after: bytes):
    """Compare declared identity across a native provider roundtrip.

    The existing provider comparator separately verifies every byte apart from
    its proven empty-string normalization; this identity check is not its replacement.
    """
    left, right = (inspect_content(before), inspect_content(after))
    if left['identity'] != right['identity']:
        raise ValueError('Native provider changed declared ruleset or mod identities')
    return dict(source=left, restored=right, declared_identity_equal=True, native_activation_verified=False, database_binding_verified=False)

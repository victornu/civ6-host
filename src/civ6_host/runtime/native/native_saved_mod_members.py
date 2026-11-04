"""Read official MOD_ID/MOD_VERSION cells without the historical ModId guess.

Only the proven vector/variant layout helpers are shared with the historical
reader. Its synthetic key and its selection/admission logic are not reused.
These are configuration declarations, never a substitute for active mods.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
from civ6_host.runtime.native import native_enabled_mods_reader as layout
from civ6_host.runtime.native.native_application_configuration import NativeApplicationConfiguration
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.official_saved_content import inspect_content
from civ6_host.runtime.native.official_saved_content import KEYS
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_mod_members.py')))).resolve().parents[1]
PROOF_SHA = '75275cd22006b7bade8e7a81421ba109eeec24b21dcfe8774751f0722c8c2313'
PROOF_PATH = ROOT / 'work/official-content927/saved-mod-member-source.json'

def verify_source():
    proof = load_pinned_json(PROOF_PATH, PROOF_SHA)
    if proof['schema'] != 'civ6rl.native_saved_mod_members927.static.v1' or {r['name']: r['key'] for r in proof['keys']} != {n: KEYS[n] for n in ('MOD_ID', 'MOD_VERSION', 'MOD_TITLE_KEY', 'MOD_SUBSCRIPTION_ID')}:
        raise ValueError('Official saved-mod member source changed')
    helper = proof['reused_layout_helpers']
    if hashlib.sha256(_resolve_resource_path(ROOT / helper['path']).read_bytes()).hexdigest() != helper['sha256']:
        raise ValueError('Borrowed native layout helpers changed')
    load_pinned_json(layout.CAPTURE715_PATH, layout.CAPTURE715_SHA256)
    load_pinned_json(layout.CAPTURE736_PATH, layout.CAPTURE736_SHA256)
    return proof

def read_saved_members(owner, configuration: bytes, *, stopped_configuration_phase=False):
    if not isinstance(owner, NativeApplicationConfiguration):
        raise TypeError('Expected native application owner')
    if stopped_configuration_phase is not True or owner.new_game_entered is not False:
        raise ValueError('Saved member read requires a stopped pre-Load configuration boundary')
    verify_source()
    expected = inspect_content(configuration)
    owner._check_guard()
    owner.require_context(owner.base, owner.context)
    before = owner.snapshot()
    base = owner.base
    root = before['normalized']
    observed = []

    def read(address, size):
        value = layout._read(owner.read, address, size)
        observed.append((address, value))
        return value

    def lookup(pointer, key):
        return layout._lookup_existing(base, pointer, key, read, owner.call)

    def cell(pointer, tag, flags):
        item = layout._variant(read(pointer, 24))
        if (item['tag'], item['extra'], item['size'], item['flags']) != (tag, 0, 0, flags) or not item['payload']:
            raise ValueError('Saved member container shape differs')
        return item['payload']

    def string(pointer, name):
        address = lookup(pointer, KEYS[name])
        if not address:
            raise ValueError('Missing official ' + name + ' cell; no ModId fallback')
        v = layout._variant(read(address, 24))
        length = v['flags'] & 16777215
        if (v['tag'], v['extra'], v['size'], v['flags'] & 4278190080) != (5, 0, 1, 553648128) or not 1 < length <= 256 or (not v['payload']):
            raise ValueError('Saved ' + name + ' is outside the counted-string profile')
        raw = read(v['payload'], length)
        if raw[-1:] != b'\x00' or b'\x00' in raw[:-1]:
            raise ValueError('Saved string termination differs')
        return raw[:-1].decode('ascii', 'strict')
    mods = lookup(root, KEYS['ENABLED_MODS'])
    records = None
    if mods:
        vector = cell(mods, 11, 285212672)
        header, begin, end, capacity, count = layout._vector_header(base, vector, read)
        records = []
        children = set()
        ids = set()
        for index in range(count):
            child = cell(begin + 24 * index, 10, 83886080)
            mod_id = string(child, 'MOD_ID')
            version = string(child, 'MOD_VERSION')
            if child in children or mod_id.lower() in ids:
                raise ValueError('Duplicate official mod record')
            children.add(child)
            ids.add(mod_id.lower())
            records.append(dict(mod_id=mod_id, version=version))
    if records != expected['identity']['mods']:
        raise ValueError('Native saved members differ from serialized declarations')
    if lookup(root, KEYS['ENABLED_MODS']) != mods or owner.snapshot() != before:
        raise RuntimeError('Native declaration owner changed during read')
    for address, raw in observed:
        if layout._read(owner.read, address, len(raw)) != raw:
            raise RuntimeError('Native saved member changed during read')
    owner._check_guard()
    owner.require_context(base, owner.context)
    return dict(schema='civ6rl.native_saved_mod_members927.readback.v1', configuration_sha256=expected['configuration_sha256'], source_proof_sha256=PROOF_SHA, property_present=mods is not None, records=records, serialized_declarations_match=True, member_key=KEYS['MOD_ID'], read_only=True, borrowed_boundaries_stable=True, manifest_version_identity_inferred=False, native_activation_verified=False, strategic_training_ready=False)

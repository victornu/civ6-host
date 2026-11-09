"""Closed installed-Base AppOwnership profile, not a license-service substitute.

Only the source branch with no matching numeric CAPABILITY entry is supported.
Every present/restricted or unknown request fails. This module never answers
Steam ownership, never loads the graphical executable, and is not a complete
AppOwnership implementation.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
import struct
from civ6_host.runtime.native import native_configuration_finalization as config
from civ6_host.runtime.native import native_host_capability_status as abi
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PRODUCER_PROOF_SHA256 = 'a59edd6e13041d1c458444e40a805c05401a5d664590a76c6a8a39e90b214fcf'
HOTSEAT = 208129763
SINGLEPLAYER = 3915931367
SINGLE_MODE_PROOF = '84cdd1c7622e6e24231e9209bac884426a06bec10aa1c7baf64ac1cf47bb1a75'
CACHE_COMPARISON_SHA = '7d3a6874c34a82cc8179cf77c6c76399f89e5d33d6179bb38be8aa8d89fa84f3'
CACHE_GAMEPLAY_SHA = '4abe921833989c6c6f44f5a894de796c3b811ff7c0447d4858285c5fcf2bcd09'
CACHE_CONFIGURATION_SHA = 'b86a6eeaf917865417a3718961cf4c3470923a3c344b7feb718a8973355ec590'
BASE_CONFIGURATION_SHA = 'abe7c77954f598bcc63d24c75c83fad4362ebdb8fc45677ea500efd12ebbb612'
CURRENT_XP2_INVENTORY_PATH = 'evidence/native-app-ownership-current-inventory/092abfbb.json'
CURRENT_XP2_INVENTORY_SHA256 = '5b2b319ba96f3bf8041019a66284cd6bf9896b2e091f93ff05e0f4d5d937b625'
CURRENT_XP2_IMAGE_IDENTITY = {
    'profile_id': 'xp2-gamecore-current-092abfbb',
    'image_sha256': '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f',
    'reference_core_sha256': '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c',
    'path': r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll",
}
CURRENT_XP2_CHANGED_BLP_FIRST_COMPONENTS = {
    ('Base/Assets/Civ6_9ae5ab5ed97dd296.xml', 6): 'F3B8C333D68AE286A998A9096A090EE8885DF3E6',
    ('Base/Assets/Civ6_9ae5ab5ed97dd296.xml', 7): '583C8AE23049AAB4AE7A9138FD35B3FD10942210',
    ('Base/Assets/Civ6_a445179b5a244001.xml', 0): '5BD6F91200A6CCCF9312380E4051B97A737E0BC7',
}
CURRENT_XP2_CHANGED_BLP_FILES = frozenset(path for path, _index in CURRENT_XP2_CHANGED_BLP_FIRST_COMPONENTS)


def _execution_image_for_ownership(candidate_backend):
    """Return only the canonical selected XP2 runtime identity, or legacy None."""
    if candidate_backend is None:
        return None
    image = getattr(getattr(candidate_backend, 'core', None),
                    '_civ6_host_execution_image', None)
    if image is None:
        return None
    from civ6_host.runtime.execution_images import identity
    selected = identity(image)
    if selected != CURRENT_XP2_IMAGE_IDENTITY:
        raise ValueError('AppOwnership current inventory requires the canonical XP2 execution image')
    return selected


def _validate_current_xp2_inventory_receipt(receipt, original_rows, selected_image,
                                             host_proof, producer_proof):
    """Validate the narrow, source-backed inventory transition; no entitlement scope."""
    from civ6_host.runtime.native.native_session_resume import plain
    receipt = plain(receipt)
    original_rows = plain(original_rows)
    host_proof = plain(host_proof)
    producer_proof = plain(producer_proof)
    if (type(receipt) is not dict
            or receipt.get('schema') != 'civ6-host.app-ownership.current-inventory-transition.v1'
            or receipt.get('execution_image') != CURRENT_XP2_IMAGE_IDENTITY
            or selected_image != CURRENT_XP2_IMAGE_IDENTITY):
        raise ValueError('AppOwnership current inventory receipt or image identity differs')
    source_proofs = [
        {'path': 'evidence/native-host-capability-status/77ed09ed4c69e5f23c83e72e45bad0d0ee5aec62bcebc66dfe3d4dff526ba620.json',
         'sha256': abi.PROOF_SHA256},
        {'path': 'evidence/native-app-ownership-capability-catalogue/' + PRODUCER_PROOF_SHA256 + '.json',
         'sha256': PRODUCER_PROOF_SHA256},
    ]
    if (receipt.get('source_proofs') != source_proofs
            or host_proof.get('schema') != 'civ6rl.native_host_capability_status.static.v1'
            or producer_proof.get('schema') != 'civ6rl.native_app_ownership_capability_catalogue.static.v1'):
        raise ValueError('AppOwnership current inventory source proofs differ')
    registry = producer_proof['registry_model']
    functions = host_proof['exe_functions']
    literals = host_proof['literals']
    expected_dataflow = receipt.get('source_dataflow')
    type_domain_instructions = [instruction
        for fragment in functions['xml_type_domain']['fragments']
        for instruction in fragment['instructions']]
    type_domain_pairs = {
        (instruction['va'], instruction['text'])
        for instruction in type_domain_instructions}
    if not {
            ('0x14003ed32', 'lea rdx, [rip + 0xf5f30f]'),
            ('0x14003ed39', 'mov rcx, rbx'),
            ('0x14003ed3c', 'call 0x140983740'),
            ('0x14003ed45', 'mov eax, 0xc9e7d17c'),
            ('0x14003ed50', 'lea rdx, [rip + 0xf5f2f9]'),
            ('0x14003ed5a', 'call 0x140983740'),
            ('0x14003ed61', 'mov edx, 0x62d100f0'),
            ('0x14003ed68', 'cmove ecx, edx'),
    }.issubset(type_domain_pairs):
        raise ValueError('AppOwnership BLP/CAPABILITY type-domain source path differs')
    if (type(expected_dataflow) is not dict
            or expected_dataflow.get('xml_type_domain') != {
                'start_va': functions['xml_type_domain']['start_va'],
                'end_va_exclusive': functions['xml_type_domain']['end_va_exclusive'],
                'code_sha256': functions['xml_type_domain']['code_sha256'],
                'blp_literal_va': '0x140f9e048', 'blp_domain_u32': '0xc9e7d17c',
                'capability_literal_va': '0x140f9e050', 'capability_domain_u32': '0x62d100f0'}
            or literals['0x140f9e048']['text'] != 'blp'
            or literals['0x140f9e050']['text'] != 'capability'
            or functions['xml_type_domain']['code_sha256'] != 'f8e2f84fff2bd548acc0fa7d138ccef1bb86706220ce746db347051007331c68'
            or functions['xml_value']['code_sha256'] != 'c2e73ff16432fb6ae6965594429b8955324c7e6dca301005bd35f8119fde2d92'
            or functions['numeric_entry_lookup']['code_sha256'] != '3a7d255df2c34921752c4dd9f2174f0b4f41fdb880157954cb27f5c8e7ed2e51'
            or functions['ownership_load_catalogues']['code_sha256'] != 'a3ff2f852129ffdfa0c0d8d5b059d306941ea86a0cc5a89e59ad60ee518bf22e'
            or expected_dataflow.get('xml_value', {}).get('code_sha256') != functions['xml_value']['code_sha256']
            or expected_dataflow.get('numeric_lookup', {}).get('code_sha256') != functions['numeric_entry_lookup']['code_sha256']
            or expected_dataflow.get('item_loader', {}).get('code_sha256') != functions['ownership_load_catalogues']['code_sha256']
            or registry['xml_value_path'] != '03ED80 special-cases MOD/CONTENT GUID and C9E7D17C only; CAPABILITY takes03EF75->7A1D80, writes tag5 string atentry+8 and F8690 CRC atentry+0.'
            or registry['lookup_numeric'] != '03DF40 matches domain entry+4 and only tag2/3 atentry+8, then exact DWORD. It never compares cached CRC entry+0.'
            or registry['other_producer'] != '0409C0 produces tag7 GUID entries; its only two callers pass CONTENT3E7F314C andMOD7EACEE3D, neverCAPABILITY.'
            or len(registry['capability_entries_possible_from_fixed_files']) != 6
            or any(row.get('domain_u32') != 0x62d100f0
                   or row.get('loaded_variant_tag') != 5
                   or row.get('eligible_for_numeric_lookup_03df40') is not False
                   for row in registry['capability_entries_possible_from_fixed_files'])
            or registry['numeric_capability_values_possible_from_known_initializers'] != []):
        raise ValueError('AppOwnership current inventory numeric-domain source correspondence differs')

    if (type(original_rows) is not list or len(original_rows) != 65
            or type(receipt.get('current_inventory')) is not list
            or len(receipt['current_inventory']) != 65
            or receipt.get('comparison', {}).get('old_inventory_rows') != 65
            or receipt['comparison'].get('current_inventory_rows') != 65
            or receipt['comparison'].get('unchanged_path_presence_size_and_sha_rows') != 63):
        raise ValueError('AppOwnership current inventory row counts differ')
    current_rows = receipt['current_inventory']
    changed = set()
    child_profiles = {
        'Base/Assets/Civ6_9ae5ab5ed97dd296.xml': ('512035', 9),
        'Base/Assets/Civ6_a445179b5a244001.xml': ('645401', 3),
    }
    for old, new in zip(original_rows, current_rows):
        path = old['installed_relative_path']
        if (new.get('installed_relative_path') != path
                or new.get('present') is not old['present']):
            raise ValueError('AppOwnership current inventory paths or presence differ')
        if old['present'] is False:
            if set(new) != {'installed_relative_path', 'present'}:
                raise ValueError('AppOwnership absent inventory entry gained data')
            continue
        if path not in CURRENT_XP2_CHANGED_BLP_FILES:
            if (new.get('byte_length') != old['byte_length']
                    or new.get('sha256') != old['sha256']
                    or set(new) != {'installed_relative_path', 'present', 'byte_length', 'sha256'}):
                raise ValueError('AppOwnership unchanged inventory input differs: ' + path)
            continue
        changed.add(path)
        if (new.get('byte_length') != old['byte_length']
                or set(new) != {'installed_relative_path', 'present', 'byte_length', 'sha256',
                                'parsed_items', 'parsed_children', 'private_copy'}):
            raise ValueError('AppOwnership changed inventory input shape differs: ' + path)
        if path.endswith('9ae5ab5ed97dd296.xml'):
            expected_sha = 'c5940fdd251272053ff536eb6db29b541c46275a557163893ab91442bd487ffb'
        else:
            expected_sha = '837f7986c71b0e627be876cd29d52aed6bfac207bcf237bab18549077fed0127'
        if new['sha256'] != expected_sha:
            raise ValueError('AppOwnership changed inventory input digest differs: ' + path)
        expected_items = [dict(item) for item in old['entries']]
        allowed_indexes = {index for item_path, index in CURRENT_XP2_CHANGED_BLP_FIRST_COMPONENTS
                           if item_path == path}
        for index, item in enumerate(expected_items):
            if item.get('type') != 'blp':
                raise ValueError('AppOwnership changed XML contains a non-BLP Item')
            if index in allowed_indexes:
                first, second = item['value'].split(';')
                item['value'] = CURRENT_XP2_CHANGED_BLP_FIRST_COMPONENTS[(path, index)] + ';' + second
        if (expected_items != new['parsed_items']
                or len(new['parsed_items']) != child_profiles[path][1]):
            raise ValueError('AppOwnership changed BLP Item projection differs: ' + path)
        steam_app, item_count = child_profiles[path]
        if len(new['parsed_children']) != item_count:
            raise ValueError('AppOwnership current BLP child projection count differs: ' + path)
        for children in new['parsed_children']:
            if children != [
                    {'tag': 'NonOwnerAllowance',
                     'attributes': {'type': 'host', 'mode': 'multiplayer'}, 'text': None},
                    {'tag': 'SteamApp', 'attributes': {'id': steam_app}, 'text': None}]:
                raise ValueError('AppOwnership current BLP child projection differs: ' + path)
        private = new['private_copy']
        if (type(private) is not dict or set(private) != {'path', 'byte_length', 'sha256'}
                or private.get('sha256') != new['sha256']
                or private.get('byte_length') != new['byte_length']):
            raise ValueError('AppOwnership current XML private copy pin differs: ' + path)
    if changed != CURRENT_XP2_CHANGED_BLP_FILES:
        raise ValueError('AppOwnership current inventory changed path set differs')
    return current_rows


def _read_current_xp2_fixed_inventory(root, original_rows, candidate_backend,
                                      host_proof, producer_proof):
    selected_image = _execution_image_for_ownership(candidate_backend)
    if selected_image is None:
        return read_fixed_inventory(root, original_rows)
    receipt = load_pinned_json(abi.ROOT / CURRENT_XP2_INVENTORY_PATH,
                               CURRENT_XP2_INVENTORY_SHA256)
    current_rows = _validate_current_xp2_inventory_receipt(
        receipt, original_rows, selected_image, host_proof, producer_proof)
    snapshots = read_fixed_inventory(root, current_rows)
    for row in current_rows:
        private = row.get('private_copy')
        if private is None:
            continue
        copy_path = _resolve_resource_path(abi.ROOT / private['path']).resolve()
        if (not copy_path.is_relative_to(abi.ROOT.resolve())
                or not copy_path.is_file()
                or copy_path.stat().st_size != private['byte_length']
                or sha256(copy_path.read_bytes()).hexdigest() != private['sha256']):
            raise ValueError('AppOwnership private current XML copy changed')
    return snapshots

def _verify_captured_bundle_profile(manifest, catalogue_gameplay_sha, captured_bundle, required_mode):
    """Join a validated PreparedBundle to its private worker database copies."""
    from civ6_host.runtime.native.native_official_bundle import DATABASE_PROFILE
    from civ6_host.runtime.native.native_official_bundle import PreparedBundle
    from civ6_host.runtime.native.native_official_load import HOTSEAT_FOUR_PROFILE
    from civ6_host.runtime.native.native_official_load import SINGLE_PROFILE
    from civ6_host.runtime.native.native_checkpoint_provider import CORE_SHA256
    if type(captured_bundle) is not PreparedBundle:
        raise ValueError('Official bundle ownership requires the exact validated PreparedBundle')
    fixture = captured_bundle.fixture
    dependencies = captured_bundle.dependencies
    if type(manifest) is not dict or type(fixture) is not dict or type(captured_bundle.content_profile) is not dict or (type(dependencies) is not dict) or (not hasattr(captured_bundle.inputs, 'profile')):
        raise ValueError('Official bundle ownership context is incomplete')
    profile = captured_bundle.inputs.profile
    if profile is SINGLE_PROFILE:
        profile_name, expected_mode = ('single', SINGLEPLAYER)
    elif profile is HOTSEAT_FOUR_PROFILE:
        profile_name, expected_mode = ('hotseat-four', HOTSEAT)
    elif profile is LAN_PROFILE:
        profile_name, expected_mode = ('lan', LAN)
    else:
        raise ValueError('Official ownership profile is outside Base Single/four-human Hotseat')
    if required_mode != expected_mode or manifest.get('input_profile') != profile_name or fixture.get('input_profile') != profile_name or (captured_bundle.inputs.official_bundle != captured_bundle.reference) or (type(captured_bundle.reference) is not tuple) or (len(captured_bundle.reference) != 2) or (type(captured_bundle.reference[0]) is not str) or (not captured_bundle.reference[0].startswith('work/')):
        raise ValueError('Official bundle input reference/profile/mode differs')
    path, bundle_sha = captured_bundle.reference
    if type(bundle_sha) is not str or len(bundle_sha) != 64 or any((c not in '0123456789abcdef' for c in bundle_sha)) or (manifest.get('official_bundle') != dict(path=path, sha256=bundle_sha)) or (fixture.get('official_bundle') != dict(path=path, sha256=bundle_sha)) or (manifest.get('eligible_for_training') is not False) or (fixture.get('eligible_for_training') is not False):
        raise ValueError('Official bundle manifest identity differs')
    bundle_manifest_path = _resolve_resource_path(abi.ROOT / path).resolve()
    if not bundle_manifest_path.is_relative_to(abi.ROOT / 'work') or dependencies.get(str(bundle_manifest_path)) != bundle_sha or (not _resolve_resource_path(bundle_manifest_path).is_file()):
        raise ValueError('Official capture manifest is not pinned by the PreparedBundle')
    bundle_manifest_bytes = _resolve_resource_path(bundle_manifest_path).read_bytes()
    if sha256(bundle_manifest_bytes).hexdigest() != bundle_sha:
        raise ValueError('Official capture manifest bytes changed')
    try:
        capture_manifest = json.loads(bundle_manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Official capture manifest is malformed') from exc
    engine_path = _resolve_resource_path(_resolve_resource_path(Path(captured_bundle.engine_path))).resolve()
    content = captured_bundle.content_profile
    if type(dependencies) is not dict or dependencies.get(str(engine_path)) != CORE_SHA256 or content.get('schema') != 'civ6rl.official_content_profile.v1' or (content.get('engine', {}).get('gamecore_sha256') != CORE_SHA256) or (type(content.get('engine', {}).get('executable_sha256')) is not str) or (len(content['engine']['executable_sha256']) != 64):
        raise ValueError('Official bundle engine identity is not the pinned Base engine')
    roles = {'gameplay', 'configuration', 'localization'}
    source_dbs = fixture.get('databases')
    private_dbs = manifest.get('databases')
    content_dbs = content.get('final_databases')
    if type(source_dbs) is not dict or set(source_dbs) != roles or type(private_dbs) is not dict or (set(private_dbs) != roles) or (type(content_dbs) is not dict) or (set(content_dbs) != roles):
        raise ValueError('Official bundle database role set differs')
    private_paths = []
    for role in ('gameplay', 'configuration', 'localization'):
        source, private, content_row = (source_dbs[role], private_dbs[role], content_dbs[role])
        if type(source) is not dict or type(private) is not dict or type(source.get('path')) is not str or (type(private.get('path')) is not str) or (type(source.get('sha256')) is not str) or (len(source['sha256']) != 64) or (type(source.get('size_bytes')) is not int) or (source['size_bytes'] <= 0) or (private.get('sha256') != source['sha256']) or (private.get('size_bytes') != source['size_bytes']) or (content_row != dict(sha256=source['sha256'], size_bytes=source['size_bytes'])):
            raise ValueError('Official bundle/private database hash or size differs: ' + role)
        source_path = _resolve_resource_path(_resolve_resource_path(Path(source['path']))).resolve()
        if dependencies.get(str(source_path)) != source['sha256']:
            raise ValueError('Official bundle source database pin differs: ' + role)
        private_path = _resolve_resource_path(_resolve_resource_path(Path(private['path']))).resolve()
        if not private_path.is_absolute() or not private_path.is_relative_to(abi.ROOT / 'work') or (not _resolve_resource_path(private_path).is_file()) or (_resolve_resource_path(private_path).stat().st_size != private['size_bytes']) or (private_path == source_path) or (private_path.parent != _resolve_resource_path(_resolve_resource_path(Path(private_dbs['gameplay'].get('path', '')))).resolve().parent):
            raise ValueError('Official bundle database is not a distinct private worker copy: ' + role)
        private_paths.append(private_path)
    if len(set(private_paths)) != 3:
        raise ValueError('Official bundle private database paths are not distinct')
    catalogue_sha = load_pinned_json(abi.ROOT / 'evidence/native-capability-catalogue' / (abi.CATALOGUE_SHA256 + '.json'), abi.CATALOGUE_SHA256)['fixture']['gameplay_database_sha256']
    if catalogue_sha != catalogue_gameplay_sha:
        raise ValueError('Pinned closed Base capability catalogue identity differs')
    localization = fixture.get('localization_bootstrap')
    if type(localization) is not dict or manifest.get('localization_bootstrap') != localization or type(localization.get('icu_data')) is not dict or (type(localization['icu_data'].get('path')) is not str) or (type(localization['icu_data'].get('sha256')) is not str) or (dependencies.get(str(_resolve_resource_path(_resolve_resource_path(Path(localization['icu_data']['path']))).resolve())) != localization['icu_data']['sha256']) or (content.get('localization_bootstrap') != dict(locale=localization.get('locale'), dictionary_flag=localization.get('dictionary_flag'), icu_sha256=localization.get('icu_data', {}).get('sha256'))):
        raise ValueError('Official bundle Localization identity differs')
    vectors = content.get('resolved_content_vectors')
    artifact_refs = capture_manifest.get('artifacts')
    expected_vectors = []
    for name in ('runtime-selections-before.json', 'runtime-selections-after.json'):
        reference = artifact_refs.get(name) if type(artifact_refs) is dict else None
        if type(reference) is not dict or type(reference.get('path')) is not str or type(reference.get('sha256')) is not str or (len(reference['sha256']) != 64) or (type(reference.get('bytes')) is not int) or (reference['bytes'] <= 0):
            raise ValueError('Official bundle runtime content references are incomplete')
        runtime_path = _resolve_resource_path(_resolve_resource_path(Path(reference['path']))).resolve()
        if not runtime_path.is_relative_to(abi.ROOT / 'work') or dependencies.get(str(runtime_path)) != reference['sha256'] or (not _resolve_resource_path(runtime_path).is_file()) or (_resolve_resource_path(runtime_path).stat().st_size != reference['bytes']):
            raise ValueError('Official bundle runtime content reference is not pinned')
        runtime_bytes = _resolve_resource_path(runtime_path).read_bytes()
        if sha256(runtime_bytes).hexdigest() != reference['sha256']:
            raise ValueError('Official bundle runtime content artifact changed')
        try:
            runtime_report = json.loads(runtime_bytes)
            snapshot = runtime_report['content929']['snapshot']
            row = {key: snapshot[key] for key in ('configured_mod_handles', 'active_mod_handles', 'ordered_component_handles')}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Official bundle runtime content artifact is malformed') from exc
        if any((type(value) is not list or len(value) > 65536 or any((type(handle) is not int or not 0 <= handle < 2 ** 32 for handle in value)) for value in row.values())):
            raise ValueError('Official bundle runtime content vectors are malformed')
        expected_vectors.append(row)
    if type(vectors) is not dict or set(vectors) != {'configured_mod_handles', 'active_mod_handles', 'ordered_component_handles'} or expected_vectors[0] != expected_vectors[1] or (vectors != expected_vectors[0]):
        raise ValueError('Official bundle content vectors differ from its pinned runtime artifacts')
    scripts = content.get('gameplay_scripts')
    if scripts != dict(selected_path_count=0, active_count=0, selected_and_active_empty=True, source_records=0, source_files=0):
        raise ValueError('Official bundle gameplay script state is not the closed empty Base profile')
    cross_capture_equivalent = all((not value for value in vectors.values()))
    if content.get('cross_capture_equivalence_supported') is not cross_capture_equivalent:
        raise ValueError('Official bundle cross-capture flag differs from its content vectors')
    return DATABASE_PROFILE

def verify_database_profile(manifest, catalogue_gameplay_sha, *, captured_bundle=None, required_mode=None):
    """Admit the legacy byte-pinned diagnostics or a joined validated Base bundle.

    The official cache has identical stored gameplay data and rowids. Its two
    extra configuration rows describe the opt-in combat fixture. They are not
    activation evidence and do not broaden this service's allowed capabilities.
    This service reads its mode from the native application, never those rows.
    """
    if captured_bundle is not None:
        return _verify_captured_bundle_profile(manifest, catalogue_gameplay_sha, captured_bundle, required_mode)
    pair = tuple((manifest['databases'][name]['sha256'] for name in ('gameplay', 'configuration')))
    if pair == (catalogue_gameplay_sha, BASE_CONFIGURATION_SHA):
        return 'reconstructed-base04'
    if pair != (CACHE_GAMEPLAY_SHA, CACHE_CONFIGURATION_SHA):
        raise ValueError('AppOwnership profile requires a pinned closed Base fixture')
    proof = load_pinned_json(abi.ROOT / 'work/official-cache912/database-comparison.json', CACHE_COMPARISON_SHA)
    game = proof['comparisons']['gameplay']
    config_db = proof['comparisons']['configuration']
    if game['stored_content_equivalent'] is not True or game['table_count'] != 318 or tuple((r['sha256'] for r in game['inputs'])) != (catalogue_gameplay_sha, CACHE_GAMEPLAY_SHA) or (tuple((r['sha256'] for r in config_db['inputs'])) != (BASE_CONFIGURATION_SHA, CACHE_CONFIGURATION_SHA)) or (tuple((t['table'] for t in config_db['tables'] if not t['equivalent'])) != ('GameModeItems', 'Parameters')) or (proof['same_save_database_binding_proven'] is not False):
        raise ValueError('Official cache comparison does not preserve the closed Base catalogue')
    return 'official-cache-phase23-diagnostic'

def verify_closed_mode(required_mode):
    if type(required_mode) is int and required_mode == LAN:
        verify_lan_source()
        return 'LAN'
    if type(required_mode) is not int or required_mode not in (HOTSEAT, SINGLEPLAYER):
        raise ValueError('Unsupported closed Base ownership mode')
    if required_mode == SINGLEPLAYER:
        proof = load_pinned_json(abi.ROOT / 'work/official-save909/singleplayer-capability-branch-proof.json', SINGLE_MODE_PROOF)
        if proof['mode']['serialized_numeric_value'] != '0xe9685ee7' or proof['source_proofs'][0]['sha256'] != abi.PROOF_SHA256 or proof['source_proofs'][1]['sha256'] != PRODUCER_PROOF_SHA256:
            raise ValueError('Single-player category-2 source proof differs')
    return 'HOTSEAT' if required_mode == HOTSEAT else 'SINGLEPLAYER'

def read_fixed_inventory(root, rows):
    """Read one closed input snapshot, including files expected to be absent."""
    root = _resolve_resource_path(_resolve_resource_path(Path(root))).resolve()
    seen, snapshots = (set(), [])
    for row in rows:
        relative = row['installed_relative_path']
        path = _resolve_resource_path(root / relative).resolve()
        if not path.is_relative_to(root) or path == root or relative in seen:
            raise ValueError('Ownership input escapes or duplicates the closed inventory')
        seen.add(relative)
        if row['present'] is False:
            if _resolve_resource_path(path).exists():
                raise ValueError('Previously absent ownership input is now present: ' + relative)
            snapshots.append({'path': relative, 'present': False})
            continue
        if row['present'] is not True or not _resolve_resource_path(path).is_file():
            raise ValueError('Ownership input is missing or not a file: ' + relative)
        before = _resolve_resource_path(path).stat()
        raw = _resolve_resource_path(path).read_bytes()
        after = _resolve_resource_path(path).stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(raw) != row['byte_length'] or sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Ownership input changed: ' + relative)
        snapshots.append({'path': relative, 'present': True, 'sha256': row['sha256']})
    return tuple(snapshots)

def read_capability_hashes(database):
    """Read the same SQL join as Core03E480 without modifying the private DB."""
    path = _resolve_resource_path(_resolve_resource_path(Path(database))).resolve()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.execute('PRAGMA query_only=ON')
        rows = connection.execute('SELECT T.Hash FROM GameCapabilities GC INNER JOIN Types T on GC.GameCapability = T.Type').fetchall()
    if any((type(row[0]) is not int or not -2147483648 <= row[0] <= 4294967295 for row in rows)):
        raise ValueError('Invalid native capability hash row')
    values = tuple(sorted((row[0] & 4294967295 for row in rows)))
    if not values or 0 in values or len(values) != len(set(values)):
        raise ValueError('Empty, zero or duplicate native capability hashes')
    return values

def read_application_mode(application, *, candidate_backend=None):
    if candidate_backend is not None:
        from civ6_host.runtime.xp1_load_capability import read_mode
        return read_mode(application, candidate_backend)
    "Read GAME_MODE freshly from B using EXE100820's scalar decoding."
    application._check_guard()
    base, read, call = (application.base, application.read, application.call)
    table = base + config.CONFIG_VTABLE
    if config._qword(read, application.pointer) != table or config._qword(read, table + 88) != base + config.LOOKUP_RVA or config._qword(read, table + 104) != base + 7626176 or (struct.unpack('<I', config._read(read, base + 9161816, 4))[0] != config.GAME_ROOT_KEY):
        raise ValueError('Application mode provider identity differs')
    child = config._invoke(call, base + config.LOOKUP_RVA, C.c_void_p, application.pointer, (C.c_uint32,), config.GAME_ROOT_KEY)
    if not child:
        raise ValueError('Application GAME_ROOT is absent')
    raw = config._read(read, child, 24)
    target = struct.unpack_from('<Q', raw, 8)[0]
    if struct.unpack_from('<H', raw)[0] != 10 or struct.unpack_from('<I', raw, 20)[0] != 83886080 or (not target) or (config._qword(read, target) != table):
        raise ValueError('Application GAME_ROOT is not the native owned map')
    variant = config._invoke(call, base + 7626176, C.c_void_p, target, (C.c_uint32,), 103015827)
    if not variant:
        raise ValueError('Native nonnullable mode getter returned NULL')
    raw = config._read(read, variant, 24)
    tag, flags = (struct.unpack_from('<H', raw)[0], struct.unpack_from('<I', raw, 20)[0])
    valid = tag <= 21 and 3145774 >> tag & 1 and (not flags & 1 << 29)
    return struct.unpack_from('<I', raw, 8)[0] if valid else 0

def verify_producer_source():
    proof = load_pinned_json(abi.ROOT / 'evidence/native-app-ownership-capability-catalogue' / (PRODUCER_PROOF_SHA256 + '.json'), PRODUCER_PROOF_SHA256)
    profile, model = (proof['closed_base_hotseat_profile'], proof['registry_model'])
    if proof['schema'] != 'civ6rl.native_app_ownership_capability_catalogue.static.v1' or proof['images'] != abi.verify_source()['images'] or proof['source_revalidation']['all_instruction_bytes_match_pinned_pe'] is not True or (profile['source_supported'] is not True) or (profile['required_game_mode_hash'] != HOTSEAT) or (profile['result_for_admitted_hash'] != 1) or (profile['admitted_capability_count'] != 93) or (model['numeric_capability_values_possible_from_known_initializers'] != ()) or (model['asset_processing_247330']['converts_capability_strings_to_numeric_keys'] is not False):
        raise RuntimeError('Closed AppOwnership producer contract differs')
    return proof

def numeric_entry(entries, capability):
    """EXE03DF40's numeric lookup; a string CRC is a different lookup."""
    for domain, tag, flags, payload in entries:
        if domain != 1657864432 or tag not in (2, 3):
            continue
        value = 0 if flags & 1 << 29 else payload & 4294967295
        if value == capability:
            return (domain, tag, flags, payload)
    return None

class ClosedBaseOwnership:
    """A closed projection for numeric lookup, not a live EXE singleton.

    Six string entries are an upper bound: failed XML/signature parsing may
    omit them. Every possible subset has the same absent numeric lookup for
    the admitted Base hashes; no parser success or ownership bool is assumed.
    """

    def __init__(self, application, installation, manifest, *, required_mode=HOTSEAT, captured_bundle=None, candidate_backend=None):
        self.candidate_backend = candidate_backend
        self.mode_name = verify_closed_mode(required_mode)
        self.required_mode = required_mode
        self.producer_proof = verify_producer_source()
        self.proof = abi.verify_source()
        catalogue = load_pinned_json(abi.ROOT / 'evidence/native-capability-catalogue' / (abi.CATALOGUE_SHA256 + '.json'), abi.CATALOGUE_SHA256)
        mode = load_pinned_json(abi.ROOT / 'evidence/native-game-mode.json', '6eb08daedc9c59f09c8d38a53bac51372a866482ede3af9adeb84ae37dbf6ead')
        if mode['key'] != {'literal_va': '0x140fbac28', 'literal': 'GAME_MODE', 'global_va': '0x1422d67d4', 'crc32_no_final_xor': '0x0623e593'}:
            raise ValueError('Application mode key source changed')
        if candidate_backend is None:
            self.database_profile = verify_database_profile(manifest, catalogue['fixture']['gameplay_database_sha256'], captured_bundle=captured_bundle, required_mode=required_mode)
            expected_count = 93
        else:
            from civ6_host.runtime.xp1_load_capability import captured_catalogue
            catalogue = captured_catalogue(candidate_backend, application, manifest, captured_bundle, required_mode)
            self.database_profile = catalogue.get('profile_name', 'official-captured-xp1-lan-candidate')
            expected_count = catalogue.get('admitted_count', 92)
        expected = tuple(sorted((row['hash_u32'] for row in catalogue['capabilities'])))
        if read_capability_hashes(manifest['databases']['gameplay']['path']) != expected:
            raise ValueError('Loaded Base capability catalogue differs')
        with closing(sqlite3.connect(_resolve_resource_path(_resolve_resource_path(Path(manifest['databases']['gameplay']['path']))).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('PRAGMA query_only=ON')
            count = connection.execute('SELECT Count(*) FROM GameCapabilities').fetchone()[0]
            actual_rows = connection.execute('SELECT GC.GameCapability,T.Type,T.Kind,T.Hash FROM GameCapabilities GC INNER JOIN Types T on GC.GameCapability=T.Type').fetchall()
        expected_rows = sorted(((row['name'], row['type'], row['kind'], row['hash_u32']) for row in catalogue['capabilities']))
        if count != expected_count or sorted(((a, b, c, d & 4294967295) for a, b, c, d in actual_rows)) != expected_rows:
            raise ValueError('Loaded Base capability names/types differ')
        fixed = self.proof['catalogue_evidence']['fixed_files']
        self.inventory = _read_current_xp2_fixed_inventory(
            installation, fixed, candidate_backend, self.proof, self.producer_proof)
        if len(self.inventory) != 65 or sum((row['present'] for row in self.inventory)) != 35:
            raise ValueError('Closed AppOwnership inventory is incomplete')
        restrictions = self.proof['catalogue_evidence']['capability_restrictions']
        self.restricted = frozenset((row['hash_u32'] for row in restrictions))
        self.allowed = frozenset(expected)
        if len(self.restricted) != 6 or len(self.allowed) != expected_count or self.restricted & self.allowed:
            raise ValueError('Closed Base catalogue overlaps ownership restrictions')
        self.entries = tuple(((1657864432, 5, None, row['name']) for row in restrictions))
        self.application = application
        if candidate_backend is not None:
            from civ6_host.runtime.xp1_load_capability import verify_candidate_live
            verify_candidate_live(candidate_backend)
        else:
            from civ6_host.runtime.native.native_application_property_copy import verify_source as getter_proof
            for fragment in getter_proof()['core_functions']['value_getter']['fragments']:
                for instruction in fragment['instructions']:
                    raw = bytes.fromhex(instruction['bytes'])
                    address = application.base + int(instruction['va'], 16) - 6442450944
                    if config._read(application.read, address, len(raw)) != raw:
                        raise ValueError('Loaded application mode value getter differs')
        if (read_application_mode(application, candidate_backend=candidate_backend) if candidate_backend is not None else read_application_mode(application)) != self.required_mode:
            raise ValueError('Closed AppOwnership profile requires actual ' + self.mode_name + ' mode')
        self.lan_branch = (ClosedLanBranch(application, captured_bundle, candidate_backend=candidate_backend) if candidate_backend is not None else ClosedLanBranch(application, captured_bundle)) if required_mode == LAN else None

    def status(self, player, capability):
        candidate_backend = getattr(self, 'candidate_backend', None)
        if candidate_backend is None:
            details = abi.request_details(player, capability)
            mode = read_application_mode(self.application)
        else:
            from civ6_host.runtime.xp1_load_capability import candidate_details
            details = candidate_details(candidate_backend, player, capability)
            mode = read_application_mode(self.application, candidate_backend=candidate_backend)
        if mode != self.required_mode:
            raise ValueError('AppOwnership mode changed outside its verified closed branch')
        if capability not in self.allowed or capability in self.restricted:
            raise ValueError('AppOwnership request requires an unsupported content/ownership path')
        if numeric_entry(self.entries, capability) is not None:
            raise ValueError('AppOwnership numeric entry needs its real constraint service')
        result, information = (1, {**details, 'capability_status_returned': True, 'status': 1, 'game_mode': mode, 'category': 2, 'branch': 'closed_base_absent_numeric_entry', 'registry_profile': 'installed-base-' + self.mode_name.lower() + '-v1', 'registry_reconstructed_from_verified_sources': True, 'live_exe_registry_observed': False, 'string_entries_are_source_upper_bound': True, 'active_ownership_registry_verified': False, 'steam_or_epic_entitlement_queried': False, 'numeric_match_present': False, 'producer_proof_sha256': PRODUCER_PROOF_SHA256, 'mode_branch_proof_sha256': SINGLE_MODE_PROOF if mode == SINGLEPLAYER else abi.PROOF_SHA256})
        if self.lan_branch is not None:
            information.update(self.lan_branch.details(player))
        if candidate_backend is not None:
            information.update(registry_profile='captured-' + details.get('candidate_family', 'xp1-lan') + '-absent-numeric-candidate', branch='captured_' + details.get('candidate_family', 'xp1-lan').replace('-', '_') + '_absent_numeric_entry_read_only_projection', public_session_admitted=False)
        return (result, information)

def install_closed_base_status(host, application, installation, *, required_mode=HOTSEAT, captured_bundle=None, candidate_backend=None):
    if not getattr(host, '_capability_status_probe_installed', False):
        raise ValueError('Pinned native capability consumer must be verified first')
    if hasattr(host, '_closed_base_app_ownership'):
        raise ValueError('Closed AppOwnership service is already installed')
    if getattr(host, 'core_base', None) != application.base or getattr(host, 'application_configuration', None) is not application:
        raise ValueError('Closed AppOwnership requires this host application provider')
    profile = ClosedBaseOwnership(application, installation, host.manifest, required_mode=required_mode, captured_bundle=captured_bundle, **{'candidate_backend': candidate_backend} if candidate_backend is not None else {})

    def query(this, player, capability):
        host._check(this)
        if getattr(host, 'application_configuration', None) is not application:
            raise ValueError('AppOwnership application provider changed')
        result, details = profile.status(player, capability)
        host.emit('native_app_ownership_capability_status', **details)
        return result
    host._bind(host.vtable, 360, C.c_uint32, [C.c_void_p, C.c_uint32, C.c_uint32], query)
    host._closed_base_app_ownership = profile
    host.emit('native_app_ownership_closed_profile_installed', source_proof_sha256=abi.PROOF_SHA256, producer_proof_sha256=PRODUCER_PROOF_SHA256, installed_present_files=35, installed_absent_files=30, base_capability_count=93 if candidate_backend is None else None, admitted_capability_count=len(profile.allowed), capability_string_entries_upper_bound=6, live_exe_registry_observed=False, required_mode=required_mode, mode_name=profile.mode_name, complete_ownership_service=False, eligible_for_training=False)
from civ6_host.runtime.capture_profiles import LAN_PROFILE
from civ6_host.runtime.lan_capabilities import LAN
from civ6_host.runtime.lan_capabilities import ClosedLanBranch
from civ6_host.runtime.lan_capabilities import verify_source as verify_lan_source

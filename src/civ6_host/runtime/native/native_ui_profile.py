"""Narrow, source-pinned admission for registered Base Hotseat UI profiles.

This admits only the exact saved configuration and the official UI source
profile established by the retained evidence. It does not certify Lua
bytecode equivalence, runtime source replacement, headless legality, or future
UI states.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from civ6_host.runtime.native import native_official_bundle
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_ui_profile.py')))).resolve().parents[1]
PROFILE_ID = 'base-standard-hotseat-capture09-ui-v1'
PROFILE_SOURCE_PATH = 'work/ui-profile-admission/standard-profile-source.json'
PROFILE_SOURCE_SHA256 = '21c06cccabf4019e94aee75253ca9f19a0659d8f9871f820349aa2dfab0bb8ad'
BUNDLE_PATH = 'work/official-capture/hotseat4-20261027-file09/manifest.json'
BUNDLE_SHA256 = '35234a1ff8420992b27753acd443313b35f5074b84318c08008cec5f9adc3b3a'
SAVE_SHA256 = '8a1ff0e51e79b3ca2dbf9a93b40f5a3ba46bb5b72395b8cd50eb6dab1d0cff35'
CAPTURE_EVIDENCE_PATH = 'evidence/phase1-official-ui-controls.json'
CAPTURE_EVIDENCE_SHA256 = 'd2934a2848a356c9cde64780dab43206d5448f7ce01ce7dddc3341fd7f7def36'
LOAD_LOG_PATH = 'work/ui-profile-admission/official-controls-20261027/Modding.log'
LOAD_LOG_SHA256 = 'c9f9c0a4dfe41d59232009c271903015b27805c512cbd6cd31650b58f0d5b0bc'
BRIDGE_MOD_ID = '29c609c4-0bfc-4b2d-9cdb-2e59556f4560'
LEGACY_GATE_NAMES = ('city_citizens', 'city_focus', 'production_queue', 'force_end_turn')
PLOT_PURCHASE_GATE = 'plot_purchase'
GATE_NAMES = LEGACY_GATE_NAMES + (PLOT_PURCHASE_GATE,)
FORCE_TURN_PROFILE_ID = 'base-standard-hotseat-capture10-ui-v1'
PLOT_PURCHASE_DELIVERY_PATH = 'work/plot-purchase/ui-delivery.json'
PLOT_PURCHASE_DELIVERY_SHA256 = 'c7af0b18cbfad7da7f989d28a3775faae3fcb54146940ac5264d3540a3b9fd75'
PLOT_PURCHASE_PROFILE_IDS = (PROFILE_ID, FORCE_TURN_PROFILE_ID)
FORCE_TURN_DELIVERY_PATH = 'work/ui-profile-admission/forced-turn/delivery.json'
FORCE_TURN_DELIVERY_SHA256 = '298bc83768aa42ad422297b493d8c375513e219699d7bff289ca70252793beb4'
FORCE_TURN_CAPTURE09_PATH = 'work/ui-profile-admission/forced-turn/capture09-availability.json'
FORCE_TURN_CAPTURE09_SHA256 = '3cede4f78e7d56e73513554d660993982cbe926ca27f0e49e94cf32430a09dd4'
FORCE_TURN_ROUTE = {'path': 'work/forced-endturn924/ui-route.json', 'sha256': 'a83eb79e0d70a4da8c04aa5b04507e9a346593c66a5d9d27517737511ee298a1'}
FORCE_TURN_OBSERVATIONS = {'forced_before': {'path': 'work/ui-profile-admission/controls-forced_before-9ec89f32/result.json', 'sha256': 'b4045a7d69074ee9294fda1d661355d8726de776d68c538205f4b4b6a5fe9c80', 'player_id': 0, 'turn': 1}, 'normal_after': {'path': 'work/ui-profile-admission/controls-normal_after-61ee5911/result.json', 'sha256': 'b2c14a851f8b12e4f418e62ddb8af7cf4c404b376ffed2696253e60a51e4c946', 'player_id': 0, 'turn': 1}, 'forced_after': {'path': 'work/ui-profile-admission/controls-forced_after-0dcd10ca/result.json', 'sha256': '471821884fa906a285af7b409a163ab9ff833e8933f359b348dcd3e075e67ff0', 'player_id': 1, 'turn': 1}}
FORCE_TURN_NATIVE_REFERENCE = {'path': 'evidence/phase1-independent-world-native-actions.json', 'sha256': 'fb35e3eb2337fb16228376f9c38589f536fd7bfc828c1166321bef112a024e53'}
SCOPE = 'For this exact Base four-human Hotseat profile, tutorial citizen/focus/queue gates are invariant across the episode; the native menu and legality are still recomputed for every action. This does not certify global future UI states, temporary selection/mode, Lua bytecode equivalence, runtime-context sources, or strategic readiness.'
PLOT_PURCHASE_SCOPE = SCOPE + ' Human plot purchase-button availability and displayed prices are retained for the registered Capture09/10 worlds; native price, request and ownership remain source-pinned separately.'
UI_RECEIPTS = ({'path': 'work/ui-profile-admission/controls-initial-641a6cf1/result.json', 'sha256': 'f9460877daa7f1675e19f6e03cfa271acecd5df52791131d90674a0a77f45824'}, {'path': 'work/ui-profile-admission/controls-citizens-f4323b8f/result.json', 'sha256': 'a292615f73bdfb43e6f17417d87493240d91a5674a825b28125862b9b26df510'}, {'path': 'work/ui-profile-admission/controls-queue-a93c0e50/result.json', 'sha256': 'b666077fba36129bf8bf038b2563bbe17fc8e75ca2d0405d955f1527d53742ce'})
BRIDGE_SOURCE_HASHES = {'mod/Civ6RL.modinfo': 'a1982dd8bd7e3a3a4acb74c09b70c984cb74cad17775afd5196b1edd2c8e7675', 'mod/UI/Civ6RL.lua': '08137b0157ba6293ddf00bd165b4d461f0fbde31a3fe5464ad06c13f1f560d66', 'mod/UI/Civ6RL.xml': 'a66349e924acf6d7be5105b3ed661ce9dd7f427bdc92420e788f07d091fb82fc', 'mod/UI/Civ6RLIncludeProbe.lua': '483929fa84361d1805ee6f6a35ea6ce74d06d05478c778d76bd45beaf8f891a4', 'mod/UI/Civ6RLFileTransport.lua': '333c5755b080fd7d00f53802c3ee606380fbd197a118411cf568662e082549c2', 'mod/UI/Civ6RLDatabaseCapture992.lua': '27be44c4bcb9e61fcc5188d6a3b18c1555540ee4aa2dc7688dd5d9055ba01709', 'mod/UI/Civ6RLUIAvailability.lua': '49730b0cba8fa75eaa44ef8ff936aadbbc17cf1a05eb789735e71518a8f05e50'}

@dataclass(frozen=True)
class ProfileSpec:
    profile_id: str
    source_path: str
    source_sha256: str
    bundle_path: str
    bundle_sha256: str
    save_sha256: str
    save_name: str
    evidence_path: str
    evidence_sha256: str
    load_log_path: str
    load_log_sha256: str
    ui_receipts: tuple
ADDITIONAL_PROFILES: dict[str, ProfileSpec] = {'base-standard-hotseat-capture10-ui-v1': ProfileSpec(profile_id='base-standard-hotseat-capture10-ui-v1', source_path='work/ui-profile-admission/capture10/standard-profile-source.json', source_sha256='855ad068155eddf8c9e1f6e5120827f7ffbd8f2d6a9d59ccd0e201547fe84087', bundle_path='work/official-capture/hotseat4-20261027-file10/manifest.json', bundle_sha256='0a370a465f8cca7241cd5d480b04e0231f27417fdc446a51335ca07f124c1515', save_sha256='562bfd56ed09c0a10a05b8a931e5cb94af840705285d8c967cadee32a4b16e71', save_name='Civ6RLLab_Base4_Capture10', evidence_path='evidence/phase1-official-ui-controls-capture10.json', evidence_sha256='11fcda8a13bcbc50626dbf2d306a8c922e98c8a6b31ef3552dc54144c39207bd', load_log_path='work/ui-profile-admission/capture10/Modding.log', load_log_sha256='ee3cfb3d89eb3cdd59538d0c254142377e34f3f455dde4d27bde045e47eb604f', ui_receipts=({'path': 'work/ui-profile-admission/controls-initial-8dcf44c5/result.json', 'sha256': '7fa122ae92ccba60a3e64342e7452070a7954710cecb4ea3579299f239516604'}, {'path': 'work/ui-profile-admission/controls-citizens-749997ee/result.json', 'sha256': '2da07f45f1442cfae844c7f26f5caf554a1c22f90f834ea271838004e36f2a16'}, {'path': 'work/ui-profile-admission/controls-queue-4b76cb8b/result.json', 'sha256': 'a02357b53358fc070763108ccf6c408a52c3d4c5a608ea1232efa97b6678460f'}))}

def _profile_spec(profile_id=None):
    if profile_id is None or profile_id == PROFILE_ID:
        return ProfileSpec(PROFILE_ID, PROFILE_SOURCE_PATH, PROFILE_SOURCE_SHA256, BUNDLE_PATH, BUNDLE_SHA256, SAVE_SHA256, 'Civ6RLLab_Base4_Capture09', CAPTURE_EVIDENCE_PATH, CAPTURE_EVIDENCE_SHA256, LOAD_LOG_PATH, LOAD_LOG_SHA256, UI_RECEIPTS)
    _need(type(profile_id) is str and profile_id in ADDITIONAL_PROFILES, 'unsupported UI profile')
    spec = ADDITIONAL_PROFILES[profile_id]
    _need(isinstance(spec, ProfileSpec) and spec.profile_id == profile_id, 'profile registration differs')
    return spec

def known_profile(profile_id):
    return type(profile_id) is str and (profile_id == PROFILE_ID or profile_id in ADDITIONAL_PROFILES)

def _need(ok, reason):
    if not ok:
        raise ValueError('UI profile admission: ' + reason)

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _read_pinned(relative: str, expected_sha: str) -> bytes:
    path = _resolve_resource_path(ROOT / relative).resolve()
    _need(path.is_relative_to(ROOT) and _resolve_resource_path(path).is_file(), 'pinned evidence is missing: ' + relative)
    raw = _resolve_resource_path(path).read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == expected_sha, 'pinned evidence changed: ' + relative)
    return raw

def _plot_delivery_file_ref(value, label):
    _need(type(value) is dict and set(value) == {'path', 'sha256'} and (type(value.get('path')) is str) and (type(value.get('sha256')) is str) and (re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None), 'malformed plot purchase ' + label + ' reference')
    _read_pinned(value['path'], value['sha256'])
    return {'path': value['path'], 'sha256': value['sha256']}

def _validate_plot_purchase_delivery(spec):
    """Validate the retained human UI click and same-state public receipt."""
    _need(spec.profile_id in PLOT_PURCHASE_PROFILE_IDS, 'plot purchase UI evidence exists only for Capture09/10')
    raw = _read_pinned(PLOT_PURCHASE_DELIVERY_PATH, PLOT_PURCHASE_DELIVERY_SHA256)
    proof = json.loads(raw)
    _need(type(proof) is dict and proof.get('schema') == 'civ6rl.plot_purchase_ui_delivery.v1' and (proof.get('status') == 'human_purchase_lens_observed_in_both_profiles'), 'plot purchase UI delivery schema or status differs')
    _need(proof.get('new_plot_purchases') == 0 and proof.get('new_optimizer_updates') == 0 and (proof.get('strategic_training_ready') is False) and (proof.get('runtime_context_sources_verified') is False), 'plot purchase UI proof overstates actions or training readiness')
    top_refs = ('official_source_analysis', 'native_route', 'native_execution_reference', 'capture09_load_screenshot', 'capture_wrapper')
    refs = [_plot_delivery_file_ref(proof.get(key), key) for key in top_refs]
    capture_wrapper_sha = proof['capture_wrapper']['sha256']
    _need(type(proof.get('profiles')) is list and len(proof['profiles']) == len(PLOT_PURCHASE_PROFILE_IDS), 'plot purchase UI proof must cover both registered worlds')
    profile_rows = proof['profiles']
    _need(type(profile_rows) is list and tuple((row.get('profile_id') for row in profile_rows if type(row) is dict)) == PLOT_PURCHASE_PROFILE_IDS, 'plot purchase UI profile set or order differs')
    for row, profile_id in zip(profile_rows, PLOT_PURCHASE_PROFILE_IDS):
        _need(type(row) is dict and set(row) == {'profile_id', 'bundle', 'capture', 'availability_receipt', 'screenshot', 'observation', 'ui', 'click', 'visual_values', 'control_evidence', 'new_gameplay_actions_for_context'}, 'plot purchase UI profile receipt fields differ')
        registered = _profile_spec(profile_id)
        _need(row['profile_id'] == registered.profile_id and row['bundle'] == {'path': registered.bundle_path, 'sha256': registered.bundle_sha256}, 'plot purchase UI proof is bound to another registered world')
        capture_ref = _plot_delivery_file_ref(row['capture'], 'capture')
        availability_ref = _plot_delivery_file_ref(row['availability_receipt'], 'availability receipt')
        screenshot_ref = _plot_delivery_file_ref(row['screenshot'], 'screenshot')
        refs.extend((capture_ref, availability_ref, screenshot_ref))
        capture = json.loads(_read_pinned(capture_ref['path'], capture_ref['sha256']))
        captured_manifest = capture.get('manifest', {})
        try:
            manifest_path_matches = _resolve_resource_path(_resolve_resource_path(Path(captured_manifest.get('path', '')))).resolve() == _resolve_resource_path(ROOT / registered.bundle_path).resolve()
        except (OSError, RuntimeError, ValueError):
            manifest_path_matches = False
        _need(capture.get('status') == 'correlated_capture_unqualified' and capture.get('exit_code') == 0 and manifest_path_matches and (captured_manifest.get('sha256') == registered.bundle_sha256) and (capture.get('save', {}).get('sha256') == registered.save_sha256), 'plot purchase UI capture identity differs')
        receipt = json.loads(_read_pinned(availability_ref['path'], availability_ref['sha256']))
        obs_ref = row['observation']
        _need(type(obs_ref) is dict and set(obs_ref) == {'player_id', 'turn', 'city_id'} and (type(obs_ref['player_id']) is int) and (type(obs_ref['turn']) is int) and (type(obs_ref['city_id']) is int), 'plot purchase observation identity is malformed')
        public = receipt.get('public_observation')
        _need(type(public) is dict and public.get('type') == 'observation' and (public.get('player_id') == obs_ref['player_id']) and (public.get('turn') == obs_ref['turn']) and (receipt.get('expected_identity') == {'player_id': obs_ref['player_id'], 'turn': obs_ref['turn']}), 'plot purchase public observation envelope differs from the UI proof')
        cities = public.get('observation', {}).get('cities')
        _need(type(cities) is list and sum((type(city) is dict and city.get('id') == obs_ref['city_id'] for city in cities)) == 1, 'selected plot purchase city is absent or ambiguous in public observation')
        _need(receipt.get('status') == 'current_ui_controls_observed' and receipt.get('label') == 'purchase_quotes' and (receipt.get('headless_qualified') is False) and (receipt.get('runtime_context_sources_verified') is False) and (receipt.get('actor_input') is False) and (receipt.get('native_gameplay_actions_by_capture') == 0) and (receipt.get('capture_source_sha256') == capture_wrapper_sha) and (receipt.get('save', {}).get('sha256') == registered.save_sha256) and (receipt.get('save_hash_after') == registered.save_sha256) and (receipt.get('process_before', {}).get('identity') == receipt.get('process_after', {}).get('identity')), 'plot purchase availability receipt overstates its scope')
        _need(type(row['ui']) is dict and set(row['ui']) == {'mode', 'tutorial_active', 'modal'} and (row['ui'] == {'mode': 'CITY_MANAGEMENT', 'tutorial_active': False, 'modal': False}), 'plot purchase screenshot does not show the admitted control context')
        _need(type(row['click']) is dict and row['click'] == {'control': 'purchase_plot', 'price_visible': True, 'completed': True}, 'plot purchase UI control was not clicked with a visible price')
        visual = row['visual_values']
        _need(type(visual) is dict and set(visual) == {'gold_displayed', 'plot_prices_displayed', 'unaffordable'} and (type(visual['gold_displayed']) is int) and (visual['gold_displayed'] >= 0) and (type(visual['plot_prices_displayed']) is list) and visual['plot_prices_displayed'] and all((type(price) is int and price >= 0 for price in visual['plot_prices_displayed'])) and (visual['unaffordable'] is True) and (min(visual['plot_prices_displayed']) > visual['gold_displayed']), 'displayed purchase prices do not prove the visible unaffordable case')
        evidence_text = row['control_evidence']
        _need(type(evidence_text) is str and 'Successful Computer Use click' in evidence_text and ('visible Acheter case control' in evidence_text) and ('No PurchaseTileCheck getter value is fabricated' in evidence_text), 'plot purchase human click or getter limitation is not recorded')
        _need(type(row['new_gameplay_actions_for_context']) is int and row['new_gameplay_actions_for_context'] in (0, 1), 'plot purchase UI context action count differs')
        ui = receipt.get('receipt', {}).get('diagnostics', {}).get('ui_availability')
        from civ6_host.runtime.native.native_ui_availability import validate_response
        validate_response(ui, {'expected_player_id': obs_ref['player_id'], 'expected_turn': obs_ref['turn']})
        selection = ui.get('selection', {})
        tutorial = ui.get('tutorial', {})
        turn_state = ui.get('turn_state', {})
        _need(selection.get('city_present') == {'status': 'observed', 'value': True} and selection.get('city_id') == {'status': 'observed', 'value': obs_ref['city_id']} and (selection.get('city_owner') == {'status': 'observed', 'value': obs_ref['player_id']}) and (selection.get('mode', {}).get('status') == 'observed') and (selection.get('mode', {}).get('value') == selection.get('city_management_mode', {}).get('value')), 'UI receipt does not match the selected owned city in City Management mode')
        _need(all((tutorial.get(key) == {'status': 'observed', 'value': False} for key in ('active', 'manager_active', 'overlay_enabled'))) and tutorial.get('any_multiplayer') == {'status': 'observed', 'value': True} and all((turn_state.get(key) == {'status': 'observed', 'value': True} for key in ('alive', 'active', 'active_complete'))), 'UI receipt tutorial or player readiness differs')
    return (proof, refs)

def _source_contract(spec=None):
    spec = spec or _profile_spec()
    raw = _read_pinned(spec.source_path, spec.source_sha256)
    proof = json.loads(raw)
    _need(type(proof) is dict and proof.get('schema') == 'civ6rl.ui_standard_profile_source.v1' and (proof.get('profile_id') == spec.profile_id), 'standard profile source contract differs')
    _need(proof.get('capture_evidence', {}).get('path') == spec.evidence_path and proof['capture_evidence'].get('sha256') == spec.evidence_sha256 and (proof['capture_evidence'].get('load_log') == {'path': spec.load_log_path, 'sha256': spec.load_log_sha256}), 'profile source refers to another world witness')
    from civ6_host.runtime.native.native_ui_availability import verify_source as verify_availability_source
    from civ6_host.runtime.native.native_ui_local_state import verify_source as verify_local_state_source
    verify_availability_source()
    verify_local_state_source()
    from civ6_host.runtime.native.official_application_configuration import verify_source as verify_configuration_source
    verify_configuration_source()
    availability = json.loads(_resolve_resource_path(ROOT / 'work/ui-availability/source-v2.json').read_bytes())
    local_state = json.loads(_resolve_resource_path(ROOT / 'work/ui-availability/local-state-source.json').read_bytes())
    official = {row['relative']: row for row in availability['sources'] + availability['additions']}
    official.update({row['relative']: row for row in local_state['official_ui']})
    _need(type(proof.get('required_official_sources')) is dict, 'official source inventory missing')
    for relative, expected_sha in proof['required_official_sources'].items():
        if relative == 'Tutorial_Config.xml':
            continue
        row = official.get(relative)
        _need(type(row) is dict and row.get('sha256') == expected_sha, 'official UI source pin differs: ' + relative)
    common = _resolve_resource_path(_resolve_resource_path(Path(official['Civ6Common.lua']['path']))).read_text(encoding='utf-8')
    production = _resolve_resource_path(_resolve_resource_path(Path(official['Panels/ProductionPanel.lua']['path']))).read_text(encoding='utf-8')
    city = _resolve_resource_path(_resolve_resource_path(Path(official['Panels/CityPanel.lua']['path']))).read_text(encoding='utf-8')
    tutorial_root = _resolve_resource_path(_resolve_resource_path(Path(official['TutorialUIRoot.lua']['path']))).read_text(encoding='utf-8')
    scenario = _resolve_resource_path(_resolve_resource_path(Path(official['TutorialScenarioBase.lua']['path']))).read_text(encoding='utf-8')
    config_path = _resolve_resource_path(Path(official['TutorialScenarioBase.lua']['path'])).parents[1] / 'Scenarios' / 'Tutorial' / 'Tutorial_Config.xml'
    _need(_resolve_resource_path(config_path).is_file() and _sha(config_path) == proof['required_official_sources']['Tutorial_Config.xml'], 'official Tutorial_Config.xml changed')
    config = ET.parse(config_path).getroot()
    tutorial_ruleset = config.findtext('./RuleSets/Row/RuleSetType')
    tutorial_multiplayer = config.findtext('./RuleSets/Row/SupportsMultiPlayer')
    _need((tutorial_ruleset, tutorial_multiplayer) == ('RULESET_TUTORIAL', '0'), 'official tutorial scenario configuration differs')
    _need(re.search('function\\s+IsTutorialRunning\\s*\\(\\)\\s*return\\s+Modding\\.IsModActive\\(TUTORIAL_UUID\\)', common), 'official tutorial activation source differs')
    source_lines = [line.strip() for line in production.splitlines()]
    running_assignments = [line for line in source_lines if re.match('(?:local\\s+)?m_isTutorialRunning\\s*(?::\\s*\\w+)?\\s*=', line)]
    test_assignments = [line for line in source_lines if re.match('(?:local\\s+)?m_tutorialTestMode\\s*(?::\\s*\\w+)?\\s*=', line)]
    _need(len(running_assignments) == 2 and any(('= false' in x for x in running_assignments)) and any(('= IsTutorialRunning()' in x for x in running_assignments)), 'ProductionPanel tutorial cache has an unpinned writer')
    _need(test_assignments == ['local m_tutorialTestMode:boolean = false;'], 'ProductionPanel tutorial test mode has an unpinned writer')
    city_lines = [line.strip() for line in city.splitlines()]
    lock_assignments = [line for line in city_lines if re.fullmatch('m_kTutorialDisabledControls\\s*=\\s*kIdsToDisable\\s*;?', line)]
    _need(len(lock_assignments) == 1 and 'contextName~="CityPanel"' in city, 'CityPanel tutorial lock producer differs')
    _need('return hmake TutorialDefinition' in scenario and re.search('if\\s+GameConfiguration\\.IsAnyMultiplayer\\(\\)\\s+then\\s+m_tutorialLevel\\s*=\\s*TUTORIAL_LEVEL_DISABLED', tutorial_root), 'Base/multiplayer tutorial sources differ')
    return proof

def _validate_bridge(manifest, proof):
    pinned = manifest['preflight'].get('installed_bridge')
    _need(type(pinned) is dict, 'capture has no installed bridge source pins')
    refs = []
    for relative in proof['bridge_source_paths']:
        row = pinned.get(relative.removeprefix('mod/'))
        _need(type(row) is dict and set(row) == {'source', 'installed'}, 'bridge source pin missing: ' + relative)
        source, installed = (row['source'], row['installed'])
        _need(source.get('sha256') == installed.get('sha256') and type(source.get('bytes')) is int and (source['bytes'] == installed.get('bytes')), 'source/installed bridge mismatch: ' + relative)
        for pin in (source, installed):
            path = _resolve_resource_path(Path(pin['path']))
            _need(_resolve_resource_path(path).is_file() and _resolve_resource_path(path).stat().st_size == pin['bytes'] and (_sha(path) == pin['sha256']), 'bridge source changed: ' + relative)
        refs.append({'path': relative, 'sha256': source['sha256']})
    modinfo = ET.parse(ROOT / 'mod/Civ6RL.modinfo').getroot()
    _need(modinfo.get('id') == BRIDGE_MOD_ID, 'project bridge identity differs')
    expected_files = {_resolve_resource_path(Path(path)).relative_to('mod').as_posix() for path in proof['bridge_source_paths'] if path != 'mod/Civ6RL.modinfo'} | set(proof['mutable_mailbox_files'])
    declared_files = {node.text.replace('\\', '/') for node in modinfo.findall('./Files/File')}
    imported_files = {node.text.replace('\\', '/') for node in modinfo.findall('./InGameActions/ImportFiles/File')}
    _need(declared_files == expected_files and imported_files == expected_files, 'bridge UI file inventory differs from pinned source set')
    return refs

def _validate_modding_log(evidence, spec=None):
    spec = spec or _profile_spec()
    raw = _read_pinned(spec.load_log_path, spec.load_log_sha256)
    log = raw.decode('utf-8')
    anchor = log.rfind('Stage: Loading a save')
    _need(anchor >= 0, 'latest Modding.log has no save-load block')
    block = log[anchor:]
    lines = [re.sub('^\\[[0-9.]+\\]\\s*', '', line).strip() for line in block.splitlines()]
    _need('Game Mode: HOTSEAT' in block and 'Human Players: 4' in block, 'latest official load is not four-player Hotseat')
    applied_header = 'Applied in-game actions (in order of application):'
    target_header = 'Target in-game actions (in order of application):'
    finish_header = 'Game content needs to change to match target config.'
    _need(all((x in lines for x in (applied_header, target_header, finish_header))), 'mod load sections missing')
    applied, target, finish = (lines.index(x) for x in (applied_header, target_header, finish_header))
    expected = [BRIDGE_MOD_ID + ' (Civ6 RL Lab - Experimental Bridge)', '* Civ6RL_UI (AddUserInterfaces)', '* Civ6RL_Files (ImportFiles)']
    _need(applied < target < finish and lines[applied + 1:target] in (['No active mods.'], expected), 'latest official load has a different active-mod profile')
    _need(lines[target + 1:finish] == expected and 'Applied all components of enabled mods.' in lines and ('Successfully reconfigured game.' in lines), 'latest official load did not apply the pinned bridge')
    return raw

def _validate_force_turn_delivery(spec):
    """Validate human shortcut availability, independently of native parity."""
    official_path = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\ActionPanel.lua"
    official_sha = '1a290b0e33c24c5b78515b58447768a6ecc3382387e0fdf6928b10f408875da3'
    route = json.loads(_read_pinned(FORCE_TURN_ROUTE['path'], FORCE_TURN_ROUTE['sha256']))
    source = next((row for row in route.get('source_files', []) if row.get('path') == official_path), None)
    handler = route.get('handler', {}).get('text', '')
    _need(type(source) is dict and source.get('sha256') == official_sha and all((token in handler for token in ('KeyEvents.KeyUp', 'Keys.VK_RETURN', 'IsShiftDown()', 'not IsTutorialRunning()', 'UI.RequestAction(ActionTypes.ACTION_ENDTURN, { REASON = "UserForced" }'))), 'official Shift+Enter handler differs')
    if spec.profile_id == PROFILE_ID:
        path = FORCE_TURN_CAPTURE09_PATH
        sha = FORCE_TURN_CAPTURE09_SHA256
        proof = json.loads(_read_pinned(path, sha))
        _need(type(proof) is dict and proof.get('schema') == 'civ6rl.forced_turn_ui_source_availability.v1' and (proof.get('profile_id') == PROFILE_ID) and (proof.get('bundle') == {'path': spec.bundle_path, 'sha256': spec.bundle_sha256}) and (proof.get('profile_source') == {'path': spec.source_path, 'sha256': spec.source_sha256}) and (proof.get('capture_evidence') == {'path': spec.evidence_path, 'sha256': spec.evidence_sha256}) and (proof.get('load_log') == {'path': spec.load_log_path, 'sha256': spec.load_log_sha256}) and (proof.get('action_panel_route') == FORCE_TURN_ROUTE) and (proof.get('official_action_panel') == {'path': official_path, 'sha256': official_sha}) and (proof.get('ui_receipts') == list(spec.ui_receipts)), 'Capture09 forced-turn source-availability witness differs')
        _need(proof.get('scope') == 'human UI source availability and tutorial predicate only' and proof.get('human_gesture_observed') is False and (proof.get('request_action_emission_instrumented') is False) and (proof.get('native_force_action_execution_claimed') is False) and (proof.get('production_stack_graphical_parity_verified') is False) and (proof.get('strategic_training_ready') is False), 'Capture09 source-availability witness overstates its evidence')
        return {'path': path, 'sha256': sha}
    if spec.profile_id != FORCE_TURN_PROFILE_ID:
        return None
    delivery = json.loads(_read_pinned(FORCE_TURN_DELIVERY_PATH, FORCE_TURN_DELIVERY_SHA256))
    _need(type(delivery) is dict and delivery.get('schema') == 'civ6rl.forced_turn_ui_availability.v1' and (delivery.get('profile_id') == FORCE_TURN_PROFILE_ID), 'forced-turn UI delivery profile differs')
    _need(delivery.get('bundle') == {'path': spec.bundle_path, 'sha256': spec.bundle_sha256}, 'forced-turn UI delivery names another official bundle')
    _need(delivery.get('action_panel_route') == FORCE_TURN_ROUTE and delivery.get('official_action_panel') == {'path': official_path, 'sha256': official_sha}, 'forced-turn UI source pin differs')
    _need(delivery.get('capture_evidence') == {'path': spec.evidence_path, 'sha256': spec.evidence_sha256}, 'forced-turn UI delivery names another capture')
    observations = delivery.get('observations')
    _need(type(observations) is dict and set(observations) == set(FORCE_TURN_OBSERVATIONS), 'forced-turn UI observation set differs')
    common_process = None
    common_capture_source = None
    common_save_path = None
    for label, expected in FORCE_TURN_OBSERVATIONS.items():
        _need(observations[label] == {key: expected[key] for key in ('path', 'sha256')}, 'forced-turn UI observation pin differs: ' + label)
        witness = json.loads(_read_pinned(expected['path'], expected['sha256']))
        ui = witness.get('receipt', {}).get('diagnostics', {}).get('ui_availability', {}).get('tutorial', {})
        observed = witness.get('public_observation', {})
        process_before = witness.get('process_before', {}).get('identity')
        process_after = witness.get('process_after', {}).get('identity')
        if common_process is None:
            common_process = process_before
            common_capture_source = witness.get('capture_source_sha256')
            common_save_path = witness.get('save', {}).get('path')
        _need(witness.get('status') == 'current_ui_controls_observed' and witness.get('label') == label and (witness.get('headless_qualified') is False) and (witness.get('runtime_context_sources_verified') is False) and (witness.get('actor_input') is False) and (witness.get('native_gameplay_actions_by_capture') == 0) and (witness.get('save', {}).get('sha256') == spec.save_sha256) and (witness.get('save_hash_after') == spec.save_sha256) and (process_before == process_after == common_process) and (witness.get('capture_source_sha256') == common_capture_source) and (witness.get('save', {}).get('path') == common_save_path) and (observed.get('player_id') == expected['player_id']) and (observed.get('turn') == expected['turn']) and (ui.get('active') == {'status': 'observed', 'value': False}) and (ui.get('any_multiplayer') == {'status': 'observed', 'value': True}), 'forced-turn UI observation does not match expected state: ' + label)
    _need(delivery.get('request_action_emission_instrumented') is False and delivery.get('scope') == 'availability/tutorial only' and (delivery.get('production_stack_graphical_parity_verified') is False) and (delivery.get('strategic_training_ready') is False) and (delivery.get('existing_native_reference') == FORCE_TURN_NATIVE_REFERENCE) and (delivery.get('existing_native_claim') == {'native_policy.action_kinds.force_end_turn': 1, 'new_native_run': False}) and (delivery.get('original_save_preserved') is True), 'forced-turn UI delivery overstates its evidence')
    return {'path': FORCE_TURN_DELIVERY_PATH, 'sha256': FORCE_TURN_DELIVERY_SHA256}

def _validate_capture_evidence(proof, expected_save_sha, spec=None):
    spec = spec or _profile_spec()
    raw = _read_pinned(spec.evidence_path, spec.evidence_sha256)
    evidence = json.loads(raw)
    _need(evidence.get('schema') == 'civ6rl.phase1_official_ui_controls.v1' and evidence.get('status') == proof['capture_evidence']['required_status'], 'official UI control evidence status differs')
    for key in proof['capture_evidence']['required_false_flags']:
        _need(evidence.get(key) is False, 'UI evidence overclaims ' + key)
    _need(evidence.get('save', {}).get('sha256') == expected_save_sha and evidence.get('original_save_unchanged') is True, 'control evidence belongs to another save')
    actions = evidence.get('desktop_actions', {})
    _need(actions.get('enabled_mod') == BRIDGE_MOD_ID and actions.get('loaded_save') == spec.save_name and (actions.get('player') == 0) and (actions.get('turn') == 1), 'official control actions belong to another profile')
    captures = evidence.get('captures')
    _need(type(captures) is list and [row.get('label') for row in captures] == ['initial', 'citizens', 'queue'], 'official control receipt set differs')
    from civ6_host.runtime.native.native_ui_availability import validate_response
    receipt_refs = []
    evidence_process = evidence.get('process', {}).get('identity', {})
    for capture in captures:
        ref = capture.get('artifact', {})
        path = ref.get('path')
        _need(type(path) is str and type(ref.get('sha256')) is str, 'malformed control receipt reference')
        receipt_raw = _read_pinned(path, ref['sha256'])
        receipt = json.loads(receipt_raw)
        ui = receipt.get('receipt', {}).get('diagnostics', {}).get('ui_availability')
        _need(type(ui) is dict, 'official control receipt is missing UI witness')
        validate_response(ui, {'expected_player_id': 0, 'expected_turn': 1})
        _need(receipt.get('headless_qualified') is False and receipt.get('runtime_context_sources_verified') is False, 'control receipt overclaims source or headless qualification')
        before = receipt.get('process_before', {}).get('identity', {})
        after = receipt.get('process_after', {}).get('identity', {})
        _need(before == after == evidence_process, 'control receipt process identity changed or differs from evidence')
        _need(receipt.get('save', {}).get('sha256') == expected_save_sha and receipt.get('save_hash_after') == expected_save_sha, 'control receipt save identity differs')
        tutorial = ui['tutorial']
        _need(tutorial['active'] == {'status': 'observed', 'value': False} and tutorial['manager_active'] == {'status': 'observed', 'value': False} and (tutorial['overlay_enabled'] == {'status': 'observed', 'value': False}) and (tutorial['any_multiplayer'] == {'status': 'observed', 'value': True}), 'control receipt tutorial/multiplayer state differs')
        locks = tutorial['context_locks']
        _need(locks['events_seen'] == 0 and locks['city_panel'] == {'status': 'unknown', 'reason': 'no_observed_event'}, 'control receipt no longer preserves the unknown initial lock state')
        _need(all((ui['controls'][name]['disabled'] == {'status': 'observed', 'value': False} for name in ('city_citizens', 'city_production', 'city_yields'))), 'a required CityPanel control was disabled or unknown in its UI receipt')
        _need(ui['controls']['production_queue_tab']['disabled'] == {'status': 'observed', 'value': False}, 'production queue tab was disabled or unknown in its UI receipt')
        if capture['label'] == 'queue':
            _need(ui['controls']['production_queue_tab']['hidden'] == {'status': 'observed', 'value': False} and ui['controls']['production_queue_container']['hidden'] == {'status': 'observed', 'value': False}, 'queue receipt does not show the queue tab and container visible')
        receipt_refs.append({'path': path, 'sha256': ref['sha256']})
    return (raw, receipt_refs)

def admit(profile_id, *, official_bundle, input_profile) -> dict:
    """Admit the exact standard four-human Hotseat source/configuration profile."""
    _need(known_profile(profile_id), 'unsupported UI profile')
    spec = _profile_spec(profile_id)
    _need(input_profile == 'hotseat-four', 'UI profile requires the hotseat-four input profile')
    normalized = native_official_bundle.normalize_reference({'path': official_bundle[0], 'sha256': official_bundle[1]} if type(official_bundle) is tuple and len(official_bundle) == 2 else official_bundle)
    _need(normalized == (spec.bundle_path, spec.bundle_sha256), 'official bundle is outside the admitted registered world profile')
    source = _source_contract(spec)
    reference, manifest = native_official_bundle._manifest(normalized)
    _need(reference == (spec.bundle_path, spec.bundle_sha256), 'registered world manifest identity differs')
    save = manifest.get('save', {}).get('source', {})
    _need(save.get('sha256') == spec.save_sha256, 'registered world save bytes differ')
    extraction = manifest['save']['extraction907']['manifest']
    extraction_path = _resolve_resource_path(ROOT / extraction).resolve()
    _need(extraction_path.is_relative_to(_resolve_resource_path((ROOT / spec.bundle_path).parent).resolve()) and _resolve_resource_path(extraction_path).is_file(), 'registered world extracted save escaped its bundle')
    raw_save = _resolve_resource_path(extraction_path.parent.joinpath('source.Civ6Save')).read_bytes()
    _need(hashlib.sha256(raw_save).hexdigest() == spec.save_sha256, 'registered world extracted save hash differs')
    native_official_bundle._configuration(raw_save, manifest, 'HOTSEAT')
    bridge_refs = _validate_bridge(manifest, source)
    _validate_modding_log(source['capture_evidence'], spec)
    _, ui_receipt_refs = _validate_capture_evidence(source, spec.save_sha256, spec)
    _need(ui_receipt_refs == list(spec.ui_receipts), 'control witnesses differ from registered world')
    force_turn_ref = _validate_force_turn_delivery(spec)
    plot_delivery_ref = None
    if spec.profile_id in PLOT_PURCHASE_PROFILE_IDS:
        _, _ = _validate_plot_purchase_delivery(spec)
        plot_delivery_ref = {'path': PLOT_PURCHASE_DELIVERY_PATH, 'sha256': PLOT_PURCHASE_DELIVERY_SHA256}
    refs = {'bundle': {'path': spec.bundle_path, 'sha256': spec.bundle_sha256}, 'source': {'path': spec.source_path, 'sha256': spec.source_sha256}, 'capture_evidence': {'path': spec.evidence_path, 'sha256': spec.evidence_sha256}, 'load_log': {'path': spec.load_log_path, 'sha256': spec.load_log_sha256}, 'ui_availability_source': source['official_source_contracts']['ui_availability'], 'ui_local_state_source': source['official_source_contracts']['ui_local_state'], 'ui_receipts': ui_receipt_refs, 'bridge_sources': bridge_refs, 'forced_turn_delivery': force_turn_ref}
    if plot_delivery_ref is not None:
        refs['plot_purchase_ui_delivery'] = plot_delivery_ref
    receipt = {'schema': 'civ6rl.ui_profile_admission.v2' if plot_delivery_ref is not None else 'civ6rl.ui_profile_admission.v1', 'profile_id': spec.profile_id, 'input_profile': input_profile, 'bundle': {'path': reference[0], 'sha256': reference[1]}, 'evidence': refs, 'gates': {**source['gates'], 'force_end_turn': force_turn_ref is not None, **({'plot_purchase': True} if plot_delivery_ref is not None else {})}, 'scope': PLOT_PURCHASE_SCOPE if plot_delivery_ref is not None else SCOPE, 'runtime_context_sources_verified': False, 'strategic_training_ready': False}
    _need(_valid_receipt(receipt), 'admitted profile receipt differs from registered contract')
    return receipt

def _valid_receipt(receipt):
    if type(receipt) is not dict:
        return False
    if not known_profile(receipt.get('profile_id')):
        return False
    spec = _profile_spec(receipt['profile_id'])
    schema = receipt.get('schema')
    version2 = schema == 'civ6rl.ui_profile_admission.v2'
    if schema not in ('civ6rl.ui_profile_admission.v1', 'civ6rl.ui_profile_admission.v2'):
        return False
    expected_keys = {'schema', 'profile_id', 'input_profile', 'bundle', 'evidence', 'gates', 'scope', 'runtime_context_sources_verified', 'strategic_training_ready'}
    if set(receipt) != expected_keys:
        return False
    if receipt.get('profile_id') != spec.profile_id or receipt.get('input_profile') != 'hotseat-four' or receipt.get('bundle') != {'path': spec.bundle_path, 'sha256': spec.bundle_sha256} or (receipt.get('runtime_context_sources_verified') is not False) or (receipt.get('strategic_training_ready') is not False) or (receipt.get('scope') != (PLOT_PURCHASE_SCOPE if version2 else SCOPE)):
        return False
    if version2 and spec.profile_id not in PLOT_PURCHASE_PROFILE_IDS:
        return False
    gates = receipt.get('gates')
    force_ref = None
    if spec.profile_id == PROFILE_ID:
        force_ref = {'path': FORCE_TURN_CAPTURE09_PATH, 'sha256': FORCE_TURN_CAPTURE09_SHA256}
    elif spec.profile_id == FORCE_TURN_PROFILE_ID:
        force_ref = {'path': FORCE_TURN_DELIVERY_PATH, 'sha256': FORCE_TURN_DELIVERY_SHA256}
    expected_gates = GATE_NAMES if version2 else LEGACY_GATE_NAMES
    if type(gates) is not dict or set(gates) != set(expected_gates) or (not all((gates.get(k) is True for k in LEGACY_GATE_NAMES[:3]))) or (gates.get('force_end_turn') is not (force_ref is not None)):
        return False
    if version2 and gates.get('plot_purchase') is not True:
        return False
    evidence = receipt.get('evidence')
    evidence_keys = {'bundle', 'source', 'capture_evidence', 'load_log', 'ui_availability_source', 'ui_local_state_source', 'ui_receipts', 'bridge_sources', 'forced_turn_delivery'}
    if version2:
        evidence_keys.add('plot_purchase_ui_delivery')
    if type(evidence) is not dict or set(evidence) != evidence_keys:
        return False
    fixed = {'bundle': {'path': spec.bundle_path, 'sha256': spec.bundle_sha256}, 'source': {'path': spec.source_path, 'sha256': spec.source_sha256}, 'capture_evidence': {'path': spec.evidence_path, 'sha256': spec.evidence_sha256}, 'load_log': {'path': spec.load_log_path, 'sha256': spec.load_log_sha256}, 'ui_availability_source': {'path': 'work/ui-availability/source-v2.json', 'sha256': '2a8c39b4e2e8ec2d80f607a721041ae29d444e6b4d9abdcb13ae5f0f2890589a'}, 'ui_local_state_source': {'path': 'work/ui-availability/local-state-source.json', 'sha256': 'd615e31517dd3d754095a99464cdd0a521908e782a5789e1d291b0255b3bf0fa'}, 'forced_turn_delivery': force_ref}
    if version2:
        fixed['plot_purchase_ui_delivery'] = {'path': PLOT_PURCHASE_DELIVERY_PATH, 'sha256': PLOT_PURCHASE_DELIVERY_SHA256}
    if any((evidence.get(key) != value for key, value in fixed.items())):
        return False
    ui_receipts = evidence.get('ui_receipts')
    bridge_sources = evidence.get('bridge_sources')
    return ui_receipts == list(spec.ui_receipts) and type(bridge_sources) is list and ({row.get('path'): row.get('sha256') for row in bridge_sources if type(row) is dict} == BRIDGE_SOURCE_HASHES) and (len(bridge_sources) == len(BRIDGE_SOURCE_HASHES))

def gate_admitted(owner, name) -> bool:
    """Check an already-admitted gate without rehashing files per menu/action."""
    if name not in GATE_NAMES:
        raise ValueError('UI profile admission: unknown gate ' + str(name))
    from civ6_host.runtime.capture_profiles import LAN_PROFILE
    if getattr(getattr(owner, 'inputs', None), 'profile', None) is LAN_PROFILE:
        from civ6_host.runtime.network_ui import gate_available
        return gate_available(owner, name)
    try:
        state = vars(owner)
    except TypeError:
        return False
    if 'ui_profile_admission' not in state or state['ui_profile_admission'] is None:
        return False
    receipt = state['ui_profile_admission']
    _need(_valid_receipt(receipt), 'explicit UI profile receipt is malformed')
    if name == PLOT_PURCHASE_GATE and receipt['schema'] == 'civ6rl.ui_profile_admission.v1':
        return False
    return receipt['gates'][name] is True

def dependencies(receipt) -> dict[str, str]:
    """Workspace source/evidence pins to include in the existing run closure."""
    _need(_valid_receipt(receipt), 'cannot pin dependencies for a malformed UI receipt')
    refs = receipt['evidence']
    result = {row['path']: row['sha256'] for key, row in refs.items() if type(row) is dict and 'path' in row}
    for key in ('ui_receipts', 'bridge_sources'):
        for row in refs[key]:
            result[row['path']] = row['sha256']
    result['work/ui-availability/source-v2.json'] = '2a8c39b4e2e8ec2d80f607a721041ae29d444e6b4d9abdcb13ae5f0f2890589a'
    result['work/official-bundle/application-configuration-source.json'] = '8abf5216307f4a0be408a7aca846ed1cc04e040254b41ee5f4ce584a633f987a'
    if receipt['gates']['force_end_turn'] is True:
        result[FORCE_TURN_ROUTE['path']] = FORCE_TURN_ROUTE['sha256']
        if receipt['profile_id'] == FORCE_TURN_PROFILE_ID:
            result[FORCE_TURN_NATIVE_REFERENCE['path']] = FORCE_TURN_NATIVE_REFERENCE['sha256']
            for row in FORCE_TURN_OBSERVATIONS.values():
                result[row['path']] = row['sha256']
    if receipt['gates'].get('plot_purchase') is True:
        proof, proof_refs = _validate_plot_purchase_delivery(_profile_spec(receipt['profile_id']))
        for row in proof_refs:
            result[row['path']] = row['sha256']
        for relative in ('civ6rl/native_saved_actions.py', 'civ6rl/native_saved_purchases.py', 'civ6rl/native_plot_purchases.py'):
            result[relative] = _sha(ROOT / relative)
    for relative in ('civ6rl/native_ui_profile.py', 'civ6rl/native_official_bundle.py', 'civ6rl/native_ui_availability.py', 'civ6rl/native_ui_local_state.py', 'civ6rl/official_application_configuration.py'):
        result[relative] = _sha(ROOT / relative)
    return result

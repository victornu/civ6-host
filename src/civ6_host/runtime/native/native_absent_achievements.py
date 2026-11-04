"""One source-proved optional achievement sink, without a platform connection.

This is an explicit host configuration, not a claim about the original EXE's
runtime pointer. Unknown users of host+20 still fail closed.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import ctypes as C
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = 'ad4201ebeadcb588ea80edbd75e1a437e4751c1251643e3cde88289836fdf0ff'
PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'evidence/native-host-slot20' / (PROOF_SHA256 + '.json')
CORE_MODULE = 'GameCore_Base_FinalRelease.dll'
CALLER_PREFIX = ('0x121508', '0x121c27', '0xf01e4')
SECONDARY_PROOF_SHA256 = 'bb72db87020709677e1f1e857c2d77be12a8b55a0b727e3fd3423a24a99e35e0'
SECONDARY_PROOF_PATH = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'evidence/native-absent-achievement-secondary' / (SECONDARY_PROOF_SHA256 + '.json')
SECONDARY_CALLER_PREFIX = ('0x121508', '0x11c0d7', '0x267883')
CITY_CONTINUATION_PROOF_SHA256 = '299362a46224f96a393232c55fde9ae5b05025dc32a09b1348ba0f9915701632'
CITY_CONTINUATION_PREFIX = ('0x121508', '0x11a0aa', '0xf01e4')
UNIT_CONTINUATION_PROOF_SHA256 = 'c18aa70660a1a9906aea73fde3488d27b67ac1da643e7fe02119c4c2e5541b5b'
UNIT_CONTINUATION_PREFIX = ('0x121508', '0x11d166', '0x1a409c')
LATE_CONTINUATION_PROOF_SHA256 = 'b0b9893a2789c0cc141ef2bee4615a8f7af81667d9b08437316aced304f19284'
LATE_CONTINUATION_PREFIX = ('0x121508', '0x121dca', '0x50b4c7')
INFLUENCE_CONTINUATION_PROOF_SHA256 = '91f806efc4d5b34d5a75d98695fbecad091450d6eb5a47f175d771e2eb4fac2d'
INFLUENCE_CONTINUATION_PREFIX = ('0x121508', '0x11630a', '0x11e437')
CALLER_PREFIXES = (CALLER_PREFIX, SECONDARY_CALLER_PREFIX, CITY_CONTINUATION_PREFIX, UNIT_CONTINUATION_PREFIX, LATE_CONTINUATION_PREFIX, INFLUENCE_CONTINUATION_PREFIX)
CALLER_PROOF_SHA256 = {CALLER_PREFIX: PROOF_SHA256, SECONDARY_CALLER_PREFIX: SECONDARY_PROOF_SHA256, CITY_CONTINUATION_PREFIX: CITY_CONTINUATION_PROOF_SHA256, UNIT_CONTINUATION_PREFIX: UNIT_CONTINUATION_PROOF_SHA256, LATE_CONTINUATION_PREFIX: LATE_CONTINUATION_PROOF_SHA256, INFLUENCE_CONTINUATION_PREFIX: INFLUENCE_CONTINUATION_PROOF_SHA256}
INFLUENCE_GROUP_PROOF_SHA256 = '6426410e0f59820d79d415ec6932d3c543de85f41fbf3244e7a3e23d78266cd3'
INFLUENCE_GROUP_PREFIXES = (('0x121508', '0x116cb0', '0x11e441'), ('0x121508', '0x117886', '0x11e44b'), ('0x121508', '0x118004', '0x11e455'), ('0x121508', '0x1181eb', '0x11e45f'), ('0x121508', '0x1185e6', '0x11e46c'))
CALLER_PREFIXES += INFLUENCE_GROUP_PREFIXES
CALLER_PROOF_SHA256.update({p: INFLUENCE_GROUP_PROOF_SHA256 for p in INFLUENCE_GROUP_PREFIXES})

def verify_source():
    proof = load_pinned_json(PROOF_PATH, PROOF_SHA256)
    expected = dict(core_return_address_prefix=CALLER_PREFIX, platform_service_installed=False, return_value=None, platform_success_reported=False, native_null_branch_used=True, real_exe_field_initialization_claimed=False, unknown_callers_supported=False, other_rulesets_supported=False, complete_captured_instructions_checked_against_pe=True)
    if proof['schema'] != 'civ6rl.native_host_slot20_920.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['explicit_absence_contract'] != expected) or (proof['host_vtable']['target_method']['raw_sha256'] != '01b97d2da374096b4359dfb781da44ea9eb61ba0541de9f2d557cfad9adef8d3') or (proof['achievement_tagged_core_caller']['tag_ascii'] != 'NEW_ACHIEVEMENT_4_13'):
        raise RuntimeError('Absent achievement sink source contract changed')
    for name, digest in {'consumer': '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b', 'achievement_wrapper': 'd945e05a5e408a85fef259c3c57185d38c8a3f09bb7f8188d77993543545ef9f', 'outer_dispatch': 'b98a02fc2fb7b375fcc82d2d5faf6d34717ce597bdf099d98f2343e43303a7ae', 'predicate': 'b2496f304b6c638de89c2e0479b37b749c679085be5c9b4e9d873a60a6d700d7'}.items():
        if proof['complete_captures'][name]['code_sha256'] != digest:
            raise RuntimeError('Achievement source body changed: ' + name)
    secondary = load_pinned_json(SECONDARY_PROOF_PATH, SECONDARY_PROOF_SHA256)
    secondary_hashes = {'consumer': '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b', 'achievement_4_20_caller': '4a046a521dd2411463299b8d49065fda131559ee72ba69480d15bbb4bb41585e', 'callback_container': 'c317984bf641d3b40332b64ab51c891a56809a1f96c86896983ed1d2d82c2097', 'outer_invoker': '9d604ab94fe8470e4a8cf549b60041927aaf36298e5270d348102b6d9dc8174f', 'achievement_wrapper': 'd945e05a5e408a85fef259c3c57185d38c8a3f09bb7f8188d77993543545ef9f'}
    if secondary.get('schema') != 'civ6rl.native_absent_achievement_secondary.static.v1' or secondary.get('native_execution') is not False or secondary.get('images', {}).get('core_sha256') != proof['images']['core_sha256'] or (secondary.get('prior_proof', {}).get('sha256') != PROOF_SHA256) or (tuple(secondary.get('contract', {}).get('core_return_address_prefix', ())) != SECONDARY_CALLER_PREFIX) or (secondary.get('contract', {}).get('achievement_callsite') != '0x18011c0d2') or (secondary.get('contract', {}).get('achievement_tag') != 'NEW_ACHIEVEMENT_4_20') or (secondary.get('contract', {}).get('consumer_returns_null_without_service') is not True) or (secondary.get('contract', {}).get('callback_return_consumed') is not False) or (secondary.get('contract', {}).get('outer_invoker_return_consumed') is not False) or (secondary.get('contract', {}).get('other_callsite_admitted') is not False) or any((secondary.get('captures', {}).get(name, {}).get('code_sha256') != digest for name, digest in secondary_hashes.items())):
        raise RuntimeError('Secondary absent achievement call path changed')
    continuation = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'work/city-continuation937/achievement-source.json', CITY_CONTINUATION_PROOF_SHA256)
    contract = dict(core_return_address_prefix=CITY_CONTINUATION_PREFIX, achievement_tag='NEW_ACHIEVEMENT_4_17', callsite='0x18011a0a5', native_null_branch_used=True, consumer_result_ignored_by_caller_and_dispatch=True, platform_service_installed=False, platform_success_reported=False, other_callers_admitted=False, other_rulesets_admitted=False)
    if continuation.get('schema') != 'civ6rl.achievement937.static.v1' or continuation.get('core_sha256') != proof['images']['core_sha256'] or continuation.get('contract') != contract or any((continuation['captures'][name]['code_sha256'] != digest for name, digest in {'consumer': '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b', 'caller': '30f67c485cd6eb19bcb4ba1d8744be28357a6e100a0251b89d930507e1a8806c', 'dispatch': 'b98a02fc2fb7b375fcc82d2d5faf6d34717ce597bdf099d98f2343e43303a7ae', 'outer': '3b49847fd84a88fbb95820e8938389d0db9ed6d893c2c9eab51b3de01381cca7'}.items())):
        raise RuntimeError('City-continuation achievement path changed')
    unit = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'work/queued-observation942/achievement-source.json', UNIT_CONTINUATION_PROOF_SHA256)
    if unit.get('schema') != 'civ6rl.achievement942.static.v1' or unit.get('core_sha256') != proof['images']['core_sha256'] or unit.get('contract') != dict(core_return_address_prefix=UNIT_CONTINUATION_PREFIX, achievement_tag='NEW_ACHIEVEMENT_4_14', callsite='0x18011d161', native_null_branch_used=True, consumer_result_ignored_by_caller_and_parent=True, platform_service_installed=False, platform_success_reported=False, other_callers_admitted=False, other_rulesets_admitted=False) or any((unit['captures'][name]['code_sha256'] != digest for name, digest in {'consumer': '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b', 'caller': '63b6e501fb32159b8d4fa785f496fd663efa2d312e561ab37ba5bcdc54dfae00', 'parent': '16550fef91bbf113fa5f384207b9f65956453d89e85ac7090ec431f02ab1898b'}.items())):
        raise RuntimeError('Unit-continuation achievement path changed')
    late = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'work/queued-observation942/achievement-second-source.json', LATE_CONTINUATION_PROOF_SHA256)
    if late.get('schema') != 'civ6rl.achievement_second942.static.v1' or late.get('core_sha256') != proof['images']['core_sha256'] or late.get('contract') != dict(core_return_address_prefix=LATE_CONTINUATION_PREFIX, achievement_tag='NEW_ACHIEVEMENT_4_23', callsite='0x180121dc5', native_null_branch_used=True, consumer_result_ignored_by_caller_and_parent=True, platform_service_installed=False, platform_success_reported=False, other_callers_admitted=False, other_rulesets_admitted=False) or any((late['captures'][name]['code_sha256'] != digest for name, digest in {'consumer': '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b', 'caller': '0a2554248b00d0ba6f01a8a1729648ff5725e3479350f24372a939c31c0c78b9', 'parent': '57d0c52b7f22fdbe4c48ad1b38bf194eefff5a87663d19a98564a833f4e7114a'}.items())):
        raise RuntimeError('Late-continuation achievement path changed')
    influence = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'work/greatpeople955/achievement-source.json', INFLUENCE_CONTINUATION_PROOF_SHA256)
    if influence.get('schema') != 'civ6rl.achievement955.static.v1' or influence.get('core_sha256') != proof['images']['core_sha256'] or influence.get('contract') != dict(core_return_address_prefix=INFLUENCE_CONTINUATION_PREFIX, callsite='0x180116305', native_null_branch_used=True, consumer_result_overwritten_before_use=True, caller_result_ignored_by_parent=True, platform_service_installed=False, platform_success_reported=False, other_callers_admitted=False, other_rulesets_admitted=False) or any((influence['captures'][name]['code_sha256'] != digest for name, digest in {'consumer': '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b', 'caller': '93d0e02468799f8f8d38ee26d8aa9cf1ddd221483145ffa95b1f348ad8615fef', 'parent': '77848c9250e6138a7ef919bbed6582e8fdafc0ef342a65c7bccca232b3578c55'}.items())):
        raise RuntimeError('Influence-continuation optional achievement path changed')
    group = load_pinned_json(_resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_absent_achievements.py')))).resolve().parents[1] / 'work/greatpeople955/achievement-group-source.json', INFLUENCE_GROUP_PROOF_SHA256)
    if group.get('schema') != 'civ6rl.achievement_group955.static.v1' or group.get('core_sha256') != proof['images']['core_sha256'] or tuple((tuple(r['core_return_address_prefix']) for r in group['contracts'])) != INFLUENCE_GROUP_PREFIXES or (not all((r['consumer_result_not_used'] is True and r['caller_result_not_used_by_parent'] is True for r in group['contracts']))) or (group.get('native_null_branch_used') is not True) or any((group.get(k) is not False for k in ('platform_service_installed', 'platform_success_reported', 'other_callers_admitted', 'other_rulesets_admitted', 'native_execution'))) or (group['captures']['0x1214d0']['code_sha256'] != '7e10390e0772dd1078d627e78089121bdd5e6f538c40f216a6ce45ef9f70d69b'):
        raise RuntimeError('Grouped influence optional achievement paths changed')
    return proof

def capture_stack():
    kernel = C.WinDLL('kernel32')
    capture = kernel.RtlCaptureStackBackTrace
    capture.argtypes, capture.restype = ([C.c_uint32, C.c_uint32, C.c_void_p, C.c_void_p], C.c_uint16)
    get_module = kernel.GetModuleHandleExW
    get_module.argtypes, get_module.restype = ([C.c_uint32, C.c_void_p, C.POINTER(C.c_void_p)], C.c_int)
    get_name = kernel.GetModuleFileNameW
    get_name.argtypes, get_name.restype = ([C.c_void_p, C.c_wchar_p, C.c_uint32], C.c_uint32)
    addresses = (C.c_void_p * 96)()
    count = capture(0, len(addresses), addresses, None)
    frames = []
    for address in addresses[:count]:
        module, name = (C.c_void_p(), C.create_unicode_buffer(32768))
        if get_module(6, address, C.byref(module)) and get_name(module, name, len(name)):
            frames.append(dict(module=_resolve_resource_path(Path(name.value)).name, rva=hex(address - module.value)))
    return frames

def select_contract(frames, *, service_installed):
    verify_source()
    if service_installed is not False:
        raise ValueError('Absent achievement adapter requires an explicitly uninstalled platform sink')
    if type(frames) is not list or not frames or any((type(f) is not dict or set(f) != {'module', 'rva'} or type(f['module']) is not str or (type(f['rva']) is not str) for f in frames)):
        raise ValueError('Achievement caller stack is incomplete')
    core = [f for f in frames if f['module'].startswith('GameCore_')]
    prefix = tuple((f['rva'] for f in core[:3]))
    if len(core) < 3 or any((f['module'] != CORE_MODULE for f in core)) or prefix not in CALLER_PREFIXES:
        raise ValueError('Unproved caller of the optional achievement interface')
    return CALLER_PROOF_SHA256[prefix]

def admitted_source_sha256(frames, *, service_installed):
    """Compatibility spelling for callers selecting the exact pinned contract."""
    return select_contract(frames, service_installed=service_installed)

def absent_service_result(frames, *, service_installed):
    select_contract(frames, service_installed=service_installed)
    return None

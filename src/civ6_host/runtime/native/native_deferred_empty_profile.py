"""Proof-gated handling for deferred records in the headless empty-subscriber profile.

This does not emulate the native profiling scope. It only proves that a record's
native handler has no pre/post hook or subscriber to invoke in this profile.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
_EVIDENCE_SHA256 = '8f93575f0641395046818b5d3af84cbb5ae113986b8f8411dd4bcee4c9d4e044'
_EVIDENCE = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_deferred_empty_profile.py')))).resolve().parents[1] / 'evidence' / 'native-deferred-empty-handlers' / f'{_EVIDENCE_SHA256}.json'
_ROWS: dict[int, dict[str, str]] = {}
_IMPROVEMENT_OWNER_SHA256 = '30f7abb2dadf857672e0f0e75c5f1cd9c732f809dbf4a5f7196b8e11f737fa36'
_IMPROVEMENT_ADDED_SHA256 = '271b025c3e906e6f11bc899d881a9a3aa6e762db4477b642db72616c69ae2466'
_OPERATION_SEGMENT_SHA256 = '338d7be6f5364de6365f37fecc0b016f9a4092d9bc1ada3dd5f6a9ee904a17b2'
_DIPLOMACY_MEET_SHA256 = 'b7c838284999c176668feb23d4ac92da65a5af71c5eed41c15197a0790c80275'
_DIPLOMACY_MAJOR_MINOR_SHA256 = 'd3d9f682412a1220e5b5d1788b4e497d4af6cf939b98ed7c4693fa958b944b66'
_DIPLOMACY_MAJORS_SHA256 = '7b1f3b0e5e0ec8da6ad9a6801ccbd7f61314117f7cc75055c14d4146708dcad2'
UNIT_DAMAGE_RECEIVER_SHA256 = '3a58b8f0cb86aa0735d981df5678b57e059ae84be88557cdd13336df2643c80a'
A479_RECEIVERS_SHA256 = '0877b2f30711709a8eaf22c571841e3f5b1e49257768e889e1ef8dd9ed1b7eaa'
STATUS_RECEIVER_SHA256 = '5dd6ed7a6e5c27af035d95cbd1cac1f0610d395e7bd9deb40d84ff17a5eb246b'
UNIT_DESCRIPTOR_RECEIVERS_SHA256 = '3fa800b838c32796317a7b9328ddc973558648e9552fe5e1edfc277711f74fc2'
UNIT_PAIR_RECEIVER_SHA256 = '1e72a04840bac400f35d7928946526f590f29cf3094179a49f91e2f388fea641'
UNIT_COMMAND_RECEIVER_SHA256 = '4997a0ca35c04ebda8acda903333a818b7545d85f2190fe6124a4f487e39673c'
TOKEN_HOOK_INSTALLER_PROOF_SHA256 = '200aecee4ba3ad1f5d26f02027cf65190dd0087a6a24d60acf183ad0f662be92'
UNIT_PROMOTION_RECEIVER_SHA256 = 'fac0b909683922b908409414a031f7bfcf909124a3db1d8a3e03258a2e67b48c'
SIMPLE_UNIT_ALIAS_RECEIVERS_SHA256 = '5c893fa164a3271fb46037a63432b1ebbb912f3f3525b166525e1a65b4bccd39'
F391_RECEIVER_SHA256 = 'eb5d6623704c7fa332a1505384767d068a363b2298814b5304037e9ab6ccffab'
D857_RECEIVER_SHA256 = 'f83c2f2e51cb134af0b059d3e99eb928fb88c2fedc6e8cd4c1a106cd259b7e57'
POSITION_VALUE_RECEIVERS_SHA256 = 'fbafe7f5ea650a3f63c10fe2524cacd5a052fc96628414b054f54011f8b6d20b'
E808_RECEIVER_SHA256 = 'd52cf1865f7d035c3af0cb15c01ad9eec2e037db2474bf6c5a4a37c9d85d6d7a'
THIRTY_AE_RECEIVER_SHA256 = '547aa179ba9e21336a8e14ddb159306501a418588ddf3c45377445eab23c10c2'
B19DD18B_RECEIVER_SHA256 = '69f66abb84d0f7d463d57b42dff29d20fd7ad8905c29ed3f9e1afe3b9524969b'
SIX_D_SELECTOR_RECEIVER_SHA256 = '6db4ee267e64ab27c542037b6b9352567af369b7e08c246078c5e92d7f591cc7'
FORTY_FIVE_B517D6_RECEIVER_SHA256 = '22bc8054f1f86b28fffa266c31aa02513e24a6d55fdc9420ecd79ed180a4f2fa'
UNIT_ENTER_FORMATION_RECEIVER_SHA256 = '17286b20aab4faed61b4ba59833ebf9c6f14866debc8a5716f0e4eac84896aa9'
BARBARIAN_RAID_RECEIVER_SHA256 = '92e1d152d256e6029ed8e025af1ae9546fcfe106b7ce638741b2f5c6e0de6710'
CITY_COMMAND_STARTED_RECEIVER_SHA256 = '915a73532cdee77c5053dcd94216dff7db40558f70b2428027819dad06d8c6c8'
_NATURAL_WONDER_PAIR_SHA256 = 'fd13cd7420166e587746f062eec5fac1f96fdb52037b74aadfb9503f92bcc0cd'
DISTRICT_COMBAT_RECEIVER_SHA256 = 'ebbc9790ca152a2abe4fd739bc379e74533b8ead8fa8f9f840dff3af843655c1'
F74_CONSUMER526_SHA256 = 'bb1ca5e52acffe29e0fb698c44ea10ec25da0460aebd465f94ead50f3c09b819'
E660_AA_CONSUMER558_SHA256 = 'cb193c021b4ff5964e071393c04379846c8375ba0ab03f2d61ace1c4dfdb09ff'

def _e660_building_pillaged_row() -> dict[int, dict]:
    """Admit only the pinned 0xAA receiver on its proven empty dispatch path."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_deferred_empty_profile.py')))).resolve().parents[1]
    proof = load_pinned_json(root / 'evidence' / 'native-e660-aa-consumer' / (E660_AA_CONSUMER558_SHA256 + '.json'), E660_AA_CONSUMER558_SHA256)
    e660_pin = '438979c637a2f619fe859ac783f9b0dc851bec20ff0089a2f222df482d3f2a60'
    e660 = load_pinned_json(root / 'evidence' / 'native-event-e66012a7' / (e660_pin + '.json'), e660_pin)
    expected_parents = {'empty': ('evidence/native-deferred-empty-handlers/8f93575f0641395046818b5d3af84cbb5ae113986b8f8411dd4bcee4c9d4e044.json', '8f93575f0641395046818b5d3af84cbb5ae113986b8f8411dd4bcee4c9d4e044'), 'e660': ('evidence/native-event-e66012a7/438979c637a2f619fe859ac783f9b0dc851bec20ff0089a2f222df482d3f2a60.json', '438979c637a2f619fe859ac783f9b0dc851bec20ff0089a2f222df482d3f2a60'), 'writer': ('work/native-e660-receiver552/selector51330671-writer-static.json', '857f3ea9a3b6ba0accc50517306661d240577bd39f70ce642345693dad6a12ad')}
    parent_rows = proof.get('parents', {})
    if proof.get('schema') != 'civ6rl.native_e660_aa_consumer.static.v1' or proof.get('image', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or any((parent_rows.get(key) != {'path': path, 'sha256': digest} for key, (path, digest) in expected_parents.items())):
        raise RuntimeError('E660 BuildingPillaged proof identity or source pins changed')
    profile_source = proof.get('current_empty_profile', {})
    if profile_source.get('path') != 'civ6rl/native_deferred_empty_profile.py' or profile_source.get('sha256') != '840156ad01d9bf5dea53bcd987f6a9b966a049fec9974e148b0c087a264b995d' or profile_source.get('admitted_record_type_count') != 188 or (profile_source.get('admits_type_aa') is not False):
        raise RuntimeError('E660 BuildingPillaged proof was not captured against the pinned 188-row profile')
    row = proof.get('receiver_row', {})
    shape = proof.get('record_shape', {})
    subscriber = proof.get('subscriber_dispatch', {})
    initialized = {'pre_hook': None, 'post_hook': None, 'row_10': 0, 'subscriber_state': 'allocated 0x38-byte state', 'count': 0, 'array': 0, 'sentinels': '0x0fffffff', 'state_flags_mask_fc': 0}

    def code_sha(body):
        instructions = [i for fragment in body.get('fragments', []) for i in fragment.get('instructions', [])]
        return hashlib.sha256(bytes.fromhex(''.join((i['bytes'] for i in instructions)))).hexdigest()
    callback = e660.get('captures', {}).get('callback', {})
    wrapper = e660.get('captures', {}).get('excluded_selector_writer', {})
    callback_texts = [i['text'] for fragment in callback.get('fragments', []) for i in fragment.get('instructions', [])]
    wrapper_texts = [i['text'] for fragment in wrapper.get('fragments', []) for i in fragment.get('instructions', [])]
    if e660.get('schema') != 'civ6rl.native_event_e66012a7.static.v2' or e660.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or e660.get('registration', {}).get('registry_sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (e660.get('registration', {}).get('kind') != 3865055911) or (e660.get('registration', {}).get('callback_va') != '0x14013fd70') or (callback.get('start_va') != '0x14013fd70') or (code_sha(callback) != '2b8443eadd74373e0b4ef49533509d74aae7cc17cb7155a404d02d346eaf4da7') or ('cmp r13d, 0x51330671' not in callback_texts) or ('call 0x14014cdc0' not in callback_texts) or (wrapper.get('start_va') != '0x14014cdc0') or (code_sha(wrapper) != 'defda32face541250a01acc48f87c076e601802b32cb7e0689f444ece3283614') or ('call 0x140136400' not in wrapper_texts):
        raise RuntimeError('E660 selector registry/callback-to-AA-writer proof changed')
    setup = row.get('setup_body', {})
    setup_texts = [i['text'] for fragment in setup.get('fragments', []) for i in fragment.get('instructions', [])]
    setup_guards = ('xor ebx, ebx', 'mov qword ptr [rcx], rbx', 'mov qword ptr [rcx + 8], rbx', 'mov qword ptr [rcx + 0x10], rbx', 'mov qword ptr [rcx + 0x18], rdx', 'mov dword ptr [rax + 0x20], ebx', 'mov dword ptr [rax + 0x24], 0xfffffff', 'mov dword ptr [rax + 0x28], 0xfffffff', 'and byte ptr [rax + 0x30], 0xfc')
    handler = row.get('handler_body', {})
    handler_calls = [i['text'] for fragment in handler.get('fragments', []) for i in fragment.get('instructions', []) if i['text'].startswith('call 0x')]
    fixed_shape = {'type': 170, 'size': 128, 'payload_offset': 80, 'payload_size': 48, 'writer_va': '0x140136400', 'source_writer_instruction_checks': ['mov dword ptr [rbx], 0x80', 'mov dword ptr [rbx + 4], 0xaa', 'movups xmmword ptr [rax], xmm0', 'movups xmmword ptr [rax + 0x10], xmm1', 'movups xmmword ptr [rax + 0x20], xmm0', 'mov dword ptr [rax], edi']}
    expected_gates = ['mov rbx, qword ptr [rdx + 0x18]', 'mov rax, qword ptr [rdx]', 'cmp dword ptr [rbx + 0x20], esi', 'jbe 0x1400dc16e', 'mov rax, qword ptr [r12 + 8]', 'test byte ptr [rbx + 0x30], 2']
    checks = {'row type': row.get('type') == '0xaa', 'event name': row.get('name', {}).get('text') == 'GameCoreEvent::BuildingPillaged', 'initializer ordinal': row.get('initializer_ordinal') == 145, 'setup address': row.get('setup_va') == '0x1400d01e0', 'row address': row.get('row_va') == '0x1412c8890', 'row stride': row.get('row_stride') == '0x30', 'row mapping': int(row.get('row_va', '0'), 16) - int(row.get('table_base', '0'), 16) == 170 * 48, 'handler address': row.get('handler_va') == '0x1400d9eb0', 'handler bytes': row.get('handler_sha256') == '427ff0fdc5c5030890fd76f1daac7f6fd0792d79f37cdbeaf13813c737961060' and code_sha(handler) == row.get('handler_sha256'), 'handler call order': handler_calls == ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0'], 'destructor address': row.get('destructor_va') == '0x1400ea0e0', 'destructor bytes': row.get('destructor_sha256') == '9502c0811a76c707c6ba5f7947348ad99625e2d3b9fbc52a4984d0fad8781c6b' and code_sha(row.get('destructor_body', {})) == row.get('destructor_sha256'), 'setup bytes': code_sha(setup) == '84ec4f809530ea21ed2208ddb24685ad665f2b7961ada3ae48fc1546e36a037b', 'setup guards': all((text in setup_texts for text in setup_guards)), 'initialized empty state': row.get('initialized_state') == initialized, 'record shape': all((shape.get(key) == value for key, value in fixed_shape.items() if key != 'source_writer_instruction_checks')) and tuple(shape.get('source_writer_instruction_checks', ())) == tuple(fixed_shape['source_writer_instruction_checks']), 'subscriber address': subscriber.get('va') == '0x1400dc0d0', 'subscriber bytes': subscriber.get('sha256') == '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca' and code_sha(subscriber.get('body', {})) == subscriber.get('sha256'), 'subscriber gates': tuple(subscriber.get('gates', ())) == tuple(expected_gates), 'baseline excluded AA': proof.get('current_empty_profile', {}).get('admits_type_aa') is False}
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError('E660 BuildingPillaged proof check failed: ' + ', '.join(failed))
    return {170: {'event_name': row['name']['text'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_sha256'], 'record_sizes': {128}}}

def _district_combat_receiver_row() -> dict[int, dict]:
    """Admit only the pinned A1/80 row; actual dispatch state is checked later.

    The source has profiling side effects. This closed receiver profile does
    not emulate its elapsed-time instrumentation or initialize native padding.
    The producer separately requires its row+10 hook to be absent.
    """
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    doc = load_pinned_json(_EVIDENCE.parents[1] / 'native-event-47261a7d-receiver' / (DISTRICT_COMBAT_RECEIVER_SHA256 + '.json'), DISTRICT_COMBAT_RECEIVER_SHA256)
    receiver, event, contract = (doc['receiver'], doc['event'], doc['contract'])
    row = receiver['row']
    binding = doc['registry']['binding']
    expected_state = dict(pre_hook_null=True, post_hook_null=True, producer_hook_null=True, subscriber_count=0, active_flag=False, dirty_flag=False, subscriber_state_required_nonnull=True)
    if doc['schema'] != 'civ6rl.native_47261a7d_receiver.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc['registry']['sha256'] != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc['registry']['kind'] != '0x47261a7d') or (binding['kind'] != 1193679485) or (binding['callback_va'] != '0x140144fd0') or (binding['mechanism'] != 'lookup_existing_or_node_value') or (binding['registration_order'] != 155) or (event['kind'] != 1193679485) or (event['callback_va'] != '0x140144fd0') or (event['writer']['va'] != '0x1401356b0') or (event['writer']['record_type'] != 161) or (event['writer']['record_size'] != 128) or (row['record_type'] != 161) or (row['record_size'] != 128) or (row['row_va'] != '0x1412c86e0') or (row['setup_va'] != '0x1400cfb20') or (row['handler_va'] != '0x1400d9b50') or (row['handler_body_sha256'] != 'b000254ec7f92b87c02e74dd37ba835b3409886ccd076b0f4d758ae8d45de47e') or (row['destructor_va'] != '0x1400ea0e0') or (row['event_name']['text'] != 'GameCoreEvent::DistrictCombatChanged') or (tuple(row['handler_direct_call_sequence']) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (receiver['subscriber_dispatch_va'] != '0x1400dc0d0') or (doc['empty_receiver_source']['initialized_state'] != expected_state) or (type(doc['empty_receiver_source']['initialized_state']['subscriber_count']) is not int) or (contract['record_type'] != 161) or (contract['record_size'] != 128) or (contract['payload_offset'] != 80) or (contract['payload_size'] != 48) or (tuple((tuple(r) for r in contract['live_payload_undefined_ranges'])) != ((4, 8), (12, 16), (36, 40))) or (tuple((tuple(r) for r in contract['null_payload_undefined_ranges'])) != ((4, 8), (12, 16), (32, 40))) or (tuple(contract['payload_fields_read_under_empty_profile']) != ()) or (contract['writer_copies_every_payload_byte'] is not True) or (contract['writer_zero_fill_does_not_make_copied_stack_gaps_defined'] is not True) or (contract['no_payload_reference_retained_by_empty_dispatch'] is not True) or (doc['verification']['native_execution'] is not False) or (doc['verification']['instructions'] != 2319):
        raise RuntimeError('DistrictCombatChanged receiver proof identity or contract changed')

    def checked_instructions(body, expected_sha256):
        instructions = [i for f in body['fragments'] for i in f['instructions']]
        code = bytes.fromhex(''.join((i['bytes'] for i in instructions)))
        if not instructions or hashlib.sha256(code).hexdigest() != expected_sha256:
            raise RuntimeError('DistrictCombatChanged captured body changed')
        rows = {i['va']: (i['bytes'], i['text']) for i in instructions}
        if len(rows) != len(instructions):
            raise RuntimeError('DistrictCombatChanged captured instruction addresses repeat')
        return rows
    setup = checked_instructions(row['setup_body'], '8d8dcf100df561d42c5f27bbac690d58039377eda38da158d2c54fe02ecdc585')
    checked_instructions(row['handler_body'], 'b000254ec7f92b87c02e74dd37ba835b3409886ccd076b0f4d758ae8d45de47e')
    dispatcher = checked_instructions(receiver['subscriber_dispatch_body'], '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca')
    installer = checked_instructions(receiver['token_hook_installer_body'], '47d0f3da083d41203373572c708cf602d828187069f0970ffc999a451b687771')
    checked_instructions(event['writer']['body'], '422cb25b848327b4d87387c4a05b8751e0839e9647e6cc6c6f1ac26d4a347a13')
    setup_guards = {'0x1400cfb26': ('33db', 'xor ebx, ebx'), '0x1400cfb74': ('48895808', 'mov qword ptr [rax + 8], rbx'), '0x1400cfb7b': ('806030fc', 'and byte ptr [rax + 0x30], 0xfc'), '0x1400cfb7f': ('895820', 'mov dword ptr [rax + 0x20], ebx'), '0x1400cfbc3': ('488919', 'mov qword ptr [rcx], rbx'), '0x1400cfbc6': ('48895908', 'mov qword ptr [rcx + 8], rbx'), '0x1400cfbca': ('48895910', 'mov qword ptr [rcx + 0x10], rbx'), '0x1400cfbce': ('48895118', 'mov qword ptr [rcx + 0x18], rdx')}
    dispatch_guards = {'0x1400dc0d8': ('488b5a18', 'mov rbx, qword ptr [rdx + 0x18]'), '0x1400dc0f1': ('804b3001', 'or byte ptr [rbx + 0x30], 1'), '0x1400dc0f5': ('488b02', 'mov rax, qword ptr [rdx]'), '0x1400dc0fe': ('7409', 'je 0x1400dc109'), '0x1400dc10d': ('397320', 'cmp dword ptr [rbx + 0x20], esi'), '0x1400dc110': ('765c', 'jbe 0x1400dc16e'), '0x1400dc16e': ('498b442408', 'mov rax, qword ptr [r12 + 8]'), '0x1400dc180': ('7409', 'je 0x1400dc18b'), '0x1400dc18b': ('806330fe', 'and byte ptr [rbx + 0x30], 0xfe'), '0x1400dc18f': ('f6433002', 'test byte ptr [rbx + 0x30], 2'), '0x1400dc198': ('0f84a3000000', 'je 0x1400dc241')}
    if any((setup.get(address) != value for address, value in setup_guards.items())) or any((dispatcher.get(address) != value for address, value in dispatch_guards.items())) or receiver['token_hook_installer_va'] != '0x1401538b0' or (tuple(receiver['token_hooked_record_types']) != (248, 132, 251, 252, 253, 312, 313, 314, 315, 316, 254)) or (161 in receiver['token_hooked_record_types']) or (sum((text == 'call 0x14011d6a0' for _, text in installer.values())) != 11):
        raise RuntimeError('DistrictCombatChanged setup/dispatch/token-hook source changed')
    return {161: {'event_name': row['event_name']['text'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {128}}}

def _f74_district_damage_changed_row() -> dict[int, dict]:
    """Admit the pinned 0x9F row when the caller proves the live empty state.

    The token-hook proof is scoped to one installer. The setup bytes establish
    the row's initial null hook slots; per-record runtime guards still reject
    observers, non-null pre/post hooks, subscribers, and active/dirty flags.
    """
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    module_root = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_deferred_empty_profile.py')))).resolve().parents[1]
    path = module_root / 'evidence' / 'native-f74-consumer526' / (F74_CONSUMER526_SHA256 + '.json')
    doc = load_pinned_json(path, F74_CONSUMER526_SHA256)
    registration, table, dispatch = (doc['registration'], doc['table'], doc['dispatch'])
    setup = registration['setup_body']
    setup_ins = {i['va']: (i['bytes'], i['text']) for fragment in setup['fragments'] for i in fragment['instructions']}
    expected_setup = {'0x1400cfa43': ('488919', 'mov qword ptr [rcx], rbx'), '0x1400cfa46': ('48895908', 'mov qword ptr [rcx + 8], rbx'), '0x1400cfa4a': ('48895910', 'mov qword ptr [rcx + 0x10], rbx'), '0x1400cfa4e': ('48895118', 'mov qword ptr [rcx + 0x18], rdx'), '0x1400cf9f4': ('48895808', 'mov qword ptr [rax + 8], rbx'), '0x1400cf9fb': ('806030fc', 'and byte ptr [rax + 0x30], 0xfc'), '0x1400cf9ff': ('895820', 'mov dword ptr [rax + 0x20], ebx')}

    def body_sha(body):
        instructions = [i for f in body['fragments'] for i in f['instructions']]
        return hashlib.sha256(bytes.fromhex(''.join((i['bytes'] for i in instructions)))).hexdigest()
    handler = registration['handler_body']
    destructor = registration['destructor_body']
    installer = doc['hook_installer']
    if doc['schema'] != 'civ6rl.native_f74_consumer526.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc['inputs']['event_registry']['sha256'] != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc['inputs']['prior_empty_profile']['sha256'] != _EVIDENCE_SHA256) or (doc['inputs']['producer_receiver_capture']['sha256'] != 'f44adc2fe644b0abbe0c6ac274840b20710dc67510c086e8e1f45a32a13556d8') or (table['record_type'] != 159) or (table['record_size'] != 144) or (table['row_static_va'] != '0x1412c8680') or (registration['initializer_setup_va'] != '0x1400cf9a0') or (registration['event_name']['text'] != 'GameCoreEvent::DistrictDamageChanged') or (registration['handler_va'] != '0x1400d9a90') or (body_sha(handler) != '3f741fa84ac76d33cb49a4d75a5e8773384329b1484fa2761081bafc644e35b0') or (tuple(dispatch['handler_direct_call_sequence']) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (dispatch['shared_subscriber_dispatch_va'] != '0x1400dc0d0') or (registration['handler_destructor_va'] != '0x1400ea0e0') or (body_sha(destructor) != '9502c0811a76c707c6ba5f7947348ad99625e2d3b9fbc52a4984d0fad8781c6b') or (installer['va'] != '0x1401538b0') or (installer['type_0x9f_present'] is not False) or (installer['absence_scope'] != 'This captured installer only.') or (159 in installer['installed_record_types']) or any((setup_ins.get(va) != value for va, value in expected_setup.items())) or (doc['validation']['native_execution'] is not False):
        raise RuntimeError('F74 DistrictDamageChanged receiver proof identity changed')
    return {159: {'event_name': registration['event_name']['text'], 'handler_va': registration['handler_va'], 'handler_body_sha256': body_sha(handler), 'record_sizes': {144}}}

def _natural_wonder_pair_rows() -> dict[int, dict]:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-36c9b2b4-receiver-pair' / (_NATURAL_WONDER_PAIR_SHA256 + '.json')
    doc = load_pinned_json(path, _NATURAL_WONDER_PAIR_SHA256)
    if doc.get('schema') != 'civ6rl.native_event_36c9b2b4_receiver_pair.static.v1' or doc.get('image', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('receiver_initializer', {}).get('direct_setup_calls') != 325 or (set(doc.get('receiver_initializer', {}).get('rows', {})) != {'0x78', '0x79'}) or (doc.get('decision', {}).get('safe_event_admission') is not False):
        raise RuntimeError('36C9 receiver-pair proof identity changed')
    expected = {120: ('GameCoreEvent::NaturalWonderRevealed', '0x1400d8bf0', '0x1400cdc60', '464097d5db424415201e66cbd8b2a5f257f9902252dc5717258bf2d30ff0b08d'), 121: ('GameCoreEvent::NaturalWonderRevealedNarrative', '0x1400d8c50', '0x1400cdd20', 'a538bdb2fad5a4e9a6df9769fbc2db08bacdd6a8e4fa6f1b09ea0bec542b1093')}
    out = {}
    for record_type, (name, handler, setup, body_sha) in expected.items():
        row = doc['receiver_initializer']['rows'][hex(record_type)]
        state = row['empty_state_contract']
        if row['event_name'] != name or row['handler_va'] != handler or row['setup_va'] != setup or (row['handler_body_sha256'] != body_sha) or (row['record_size'] != 112) or (state != {'flags_state_plus_0x30_mask_0xfc': 0, 'row_post_hook_plus_8': None, 'row_pre_hook_plus_0': None, 'row_reserved_plus_0x10': 0, 'row_subscriber_state_plus_0x18': 'allocated 0x38-byte state if allocation succeeds', 'subscriber_array_state_plus_0x08': 0, 'subscriber_count_state_plus_0x20': 0, 'subscriber_list_sentinels_plus_0x24_0x28': 268435455}):
            raise RuntimeError(f'36C9 receiver row {record_type:#x} changed')
        out[record_type] = {'event_name': name, 'handler_va': handler, 'handler_body_sha256': body_sha, 'record_sizes': {112}}
    return out

def _barbarian_raid_receiver_row() -> dict:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    doc = load_pinned_json(_EVIDENCE.parents[1] / 'native-ad786513-receiver' / (BARBARIAN_RAID_RECEIVER_SHA256 + '.json'), BARBARIAN_RAID_RECEIVER_SHA256)
    receiver, event = (doc['receiver'], doc['event'])
    row = receiver['row']
    stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400c6b7b', 'mov dword ptr [rax + 0x20], ebx': '0x1400c6b7f', 'mov qword ptr [rax + 8], rbx': '0x1400c6b74', 'mov qword ptr [rcx + 0x10], rbx': '0x1400c6bca', 'mov qword ptr [rcx + 0x18], rdx': '0x1400c6bce', 'mov qword ptr [rcx + 8], rbx': '0x1400c6bc6', 'mov qword ptr [rcx], rbx': '0x1400c6bc3'}
    if doc['schema'] != 'civ6rl.native_ad786513_receiver.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc['registry']['sha256'] != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (event['kind'] != 2910348563) or (event['callback_va'] != '0x14013f820') or (event['writer']['va'] != '0x140121460') or (event['writer']['record_type'] != 277) or (event['writer']['record_size'] != 96) or (row['record_type'] != 277) or (row['record_size'] != 96) or (row['row_va'] != '0x1412c9ca0') or (row['setup_va'] != '0x1400c6b20') or (row['event_name']['text'] != 'GameCoreEvent::BarbarianRaidStarted') or (row['handler_va'] != '0x1400d5350') or (row['handler_body_sha256'] != '9b2fa1a906ca36b98158d205a22844cfabb4dc857d6d14ae2a4e787b025ca59d') or (tuple(row['handler_direct_call_sequence']) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row['empty_initialization_instructions'] != stores) or (receiver['token_hook_installer_va'] != '0x1401538b0') or (tuple(receiver['token_hooked_record_types']) != (248, 132, 251, 252, 253, 312, 313, 314, 315, 316, 254)) or (doc['validation']['pinned_pe_bytes_rechecked'] is not True):
        raise RuntimeError('BarbarianRaidStarted empty receiver source changed')
    return {277: {'event_name': row['event_name']['text'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {96}}}

def _unit_damage_row() -> dict:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    doc = load_pinned_json(_EVIDENCE.parents[1] / 'native-unit-damage-receiver' / (UNIT_DAMAGE_RECEIVER_SHA256 + '.json'), UNIT_DAMAGE_RECEIVER_SHA256)
    row, event, hooks = (doc['receiver'], doc['event'], doc['token_hooks'])
    instructions = {i['va']: i['text'] for f in row['setup_body']['fragments'] for i in f['instructions']}
    expected = {'0x1400c9ca6': 'xor ebx, ebx', '0x1400c9cf4': 'mov qword ptr [rax + 8], rbx', '0x1400c9cfb': 'and byte ptr [rax + 0x30], 0xfc', '0x1400c9cff': 'mov dword ptr [rax + 0x20], ebx', '0x1400c9d43': 'mov qword ptr [rcx], rbx', '0x1400c9d46': 'mov qword ptr [rcx + 8], rbx', '0x1400c9d4a': 'mov qword ptr [rcx + 0x10], rbx', '0x1400c9d4e': 'mov qword ptr [rcx + 0x18], rdx'}
    if doc['schema'] != 'civ6rl.native_unit_damage_receiver.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or event['kind'] != 4171606804 or (event['record_type'] != 33) or (event['record_size'] != 112) or (event['callback_va'] != '0x140155ad0') or (row['row_va'] != '0x1412c6ee0') or (row['setup_va'] != '0x1400c9ca0') or (row['handler_va'] != '0x1400d6c10') or (row['generic_dispatch_va'] != '0x1400dc0d0') or (row['name']['text'] != 'GameCoreEvent::UnitDamageChanged') or (row['handler_direct_call_sequence'] != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (len(row['handler_body']['fragments']) != 1) or (row['handler_body']['fragments'][0]['raw_sha256'] != '556dfc5de2b478837e1dc277ab119c9f660556cead96d0068c5859e9b34cf9fe') or any((instructions.get(k) != v for k, v in expected.items())) or (hooks['installer_va'] != '0x1401538b0') or (hooks['type_0x21_has_token_post_hook'] is not False) or any((r['record_type'] == 33 for r in hooks['registrations'])):
        raise RuntimeError('UnitDamageChanged empty receiver source changed')
    return {'event_name': row['name']['text'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body']['fragments'][0]['raw_sha256'], 'record_sizes': {112}}

def _a479_receivers() -> dict[int, dict]:
    """Return only the two A479 rows proved by the pinned receiver capture."""
    path = _EVIDENCE.parents[1] / 'native-a479f83f-receivers' / (A479_RECEIVERS_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != A479_RECEIVERS_SHA256:
        raise RuntimeError('A479 receiver source proof changed')
    doc = json.loads(raw)
    if doc.get('schema') != 'civ6rl.native_a479f83f_receivers.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('event', {}).get('kind') != 2759456831 or (doc['event'].get('callback_va') != '0x1401561b0') or (doc.get('parents', {}).get('empty_profile', {}).get('sha256') != _EVIDENCE_SHA256) or (doc.get('parents', {}).get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5'):
        raise RuntimeError('A479 receiver proof identity or parent pins changed')
    receiver = doc['receiver']
    installer = receiver.get('token_hook_installer_va')
    hooked = receiver.get('token_hooked_record_types')
    if installer != '0x1401538b0' or hooked != [248, 132, 251, 252, 253, 312, 313, 314, 315, 316, 254]:
        raise RuntimeError('A479 token-hook installer proof changed')
    if 74 in hooked or 79 in hooked:
        raise RuntimeError('A479 row now has a registration in the captured installer')
    expected = {74: {'size': 96, 'row': '0x1412c7690', 'setup': '0x1400cbb60', 'handler': '0x1400d7b70', 'name': 'GameCoreEvent::UnitExperienceChanged', 'hash': '8569d0fb0c2ebf73c0767361b09982938c9f04a95c995ee87175470b94889e42', 'initialization': {'and byte ptr [rax + 0x30], 0xfc': '0x1400cbbbb', 'mov dword ptr [rax + 0x20], ebx': '0x1400cbbbf', 'mov qword ptr [rcx + 8], rbx': '0x1400cbc06'}}, 79: {'size': 112, 'row': '0x1412c7780', 'setup': '0x1400cbf20', 'handler': '0x1400d7d50', 'name': 'GameCoreEvent::UnitPromotionAvailable', 'hash': '169c6dddead33ea9b1e79a27c89c9b242bea7034fd0f1d78a91e7c81c32fefb4', 'initialization': {'and byte ptr [rax + 0x30], 0xfc': '0x1400cbf7b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cbf7f', 'mov qword ptr [rcx + 8], rbx': '0x1400cbfc6'}}}
    rows = receiver.get('rows', {})
    if set(rows) != {'0x4a', '0x4f'}:
        raise RuntimeError('A479 receiver row set changed')
    result = {}
    for record_type, contract in expected.items():
        row = rows[f'0x{record_type:x}']
        fragments = row['handler_body']['fragments']
        if row['record_type'] != record_type or row['record_size'] != contract['size'] or row['row_va'] != contract['row'] or (row['setup_va'] != contract['setup']) or (row['handler_va'] != contract['handler']) or (row['event_name'].get('text') != contract['name']) or (row['handler_direct_call_sequence'] != ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']) or (len(fragments) != 1) or (fragments[0].get('raw_sha256') != contract['hash']) or (row.get('empty_initialization_instructions') != contract['initialization']):
            raise RuntimeError(f'A479 receiver row {record_type:#x} changed')
        result[record_type] = {'event_name': contract['name'], 'handler_va': contract['handler'], 'handler_body_sha256': contract['hash'], 'record_sizes': {contract['size']}}
    return result

def _status_message_row() -> dict:
    """Add StatusMessage only under the captured initialized empty profile."""
    path = _EVIDENCE.parents[1] / 'native-host-slot-c0' / (STATUS_RECEIVER_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != STATUS_RECEIVER_SHA256:
        raise RuntimeError('StatusMessage receiver source proof changed')
    doc = json.loads(raw)
    expected_image = {'core_sha256': 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', 'exe_sha256': 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'}
    row = doc.get('empty_receiver_source', {})
    state = {'active_deferred_flag_mask': 3, 'active_deferred_flags_initial': 0, 'post_hook_row_plus_8': None, 'pre_hook_row_plus_0': None, 'subscriber_array_state_plus_8': 0, 'subscriber_count_state_plus_0x20': 0, 'thread_hook_row_plus_0x10': None}
    setup = doc.get('captures', {}).get('receiver_setup', {})
    handler = doc.get('captures', {}).get('receiver_handler', {})
    dispatcher = doc.get('captures', {}).get('subscriber_dispatch', {})
    installer = doc.get('captures', {}).get('token_hook_installer', {})
    expected_hooks = [248, 132, 251, 252, 253, 312, 313, 314, 315, 316, 254]
    if doc.get('schema') != 'civ6rl.native_host_slot_c0.static.v1' or doc.get('images') != expected_image or doc.get('binding', {}).get('slot') != 192 or (doc['binding'].get('host_vtable_va') != '0x140fc79d0') or (doc['binding'].get('target_va') != '0x1401ca890') or (row.get('record_type') != 247) or (row.get('record_size') != 1120) or (row.get('size') != 1120) or (row.get('row_va') != '0x1412c9700') or (row.get('setup_va') != '0x1400d3f60') or (row.get('handler_va') != '0x1400dbd70') or (row.get('subscriber_dispatch_va') != '0x1400dc0d0') or (row.get('event_name') != 'GameCoreEvent::StatusMessage') or (row.get('handler_body_sha256') != '46f295385c37d4a8d44b8e6771f05c4b49c65888998593e58a65bc7d06c4cab5') or (row.get('initialized_state') != state) or (row.get('token_hook_types_in_1538b0') != expected_hooks) or (setup.get('start_va') != '0x1400d3f60') or (setup.get('code_sha256') != '275164dded1b02692e7581f5ac8d21e208e55396b8c8200e8714aa3210f5f5c1') or (handler.get('start_va') != '0x1400dbd70') or (handler.get('code_sha256') != '46f295385c37d4a8d44b8e6771f05c4b49c65888998593e58a65bc7d06c4cab5') or (dispatcher.get('start_va') != '0x1400dc0d0') or (dispatcher.get('code_sha256') != '326ad0582020365181be9ed3b3e0f595e1bf834ef24f5afdf167d9ae56292bca') or (installer.get('start_va') != '0x1401538b0') or (installer.get('code_sha256') != '47d0f3da083d41203373572c708cf602d828187069f0970ffc999a451b687771'):
        raise RuntimeError('StatusMessage empty receiver source changed')
    handler_calls = [instruction['text'] for fragment in handler['fragments'] for instruction in fragment['instructions'] if instruction['text'].startswith('call ')]
    if handler_calls != ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']:
        raise RuntimeError('StatusMessage handler call sequence changed')
    return {'event_name': 'GameCoreEvent::StatusMessage', 'handler_va': '0x1400dbd70', 'handler_body_sha256': handler['code_sha256'], 'record_sizes': {1120}}

def _diplomacy_relationship_row() -> dict:
    from civ6_host.runtime.native.native_event_eaa9d373 import verify_source_evidence
    doc = verify_source_evidence()
    row = doc['empty_receiver_source']
    state = row['initialized_state']
    if row['record_type'] != 137 or row['record_size'] != 112 or row['row_va'] != '0x1412c8260' or (row['setup_va'] != '0x1400ce920') or (row['handler_va'] != '0x1400d9250') or (row['subscriber_dispatch_va'] != '0x1400dc0d0') or (row['event_name'] != 'GameCoreEvent::DiplomacyRelationshipChanged') or (row['handler_body_sha256'] != '47d7c066ec494ce799559a4b538ca105483d558c774e94f0975be76997b204cd') or (state['pre_hook_row_plus_0'] is not None) or (state['post_hook_row_plus_8'] is not None) or (state['subscriber_count_state_plus_0x20'] != 0) or (state['subscriber_array_state_plus_8'] != 0) or (state['busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc'] != 0):
        raise RuntimeError('DiplomacyRelationshipChanged empty receiver contract changed')
    return {'event_name': row['event_name'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}}

def _unit_descriptor_family_rows() -> dict[int, dict]:
    """Rows for the independently captured fixed-size descriptor family."""
    path = _EVIDENCE.parents[1] / 'native-status-receiver' / (UNIT_DESCRIPTOR_RECEIVERS_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != UNIT_DESCRIPTOR_RECEIVERS_SHA256:
        raise RuntimeError('unit descriptor receiver proof changed')
    doc = json.loads(raw)
    expected_types = {29, 34, 41, 42, 43, 76, 78, 81, 82, 84, 85, 278}
    contracts = {29: ('0x1412c6e20', '0x1400c99a0', '0x1400d6a90', 'GameCoreEvent::UnitRemovedFromMap', '1751ee0145d044b2b271c247c629822159b28975847a3b653b7f0c307d7cfc4b'), 34: ('0x1412c6f10', '0x1400c9d60', '0x1400d6c70', 'GameCoreEvent::UnitArtifactChanged', '36e67f1620743f9cc581277d664ba4c1d91eecbc93cd01b0e8564f47326c73f6'), 41: ('0x1412c7060', '0x1400ca2a0', '0x1400d6f10', 'GameCoreEvent::UnitFormCorps', 'd20422964925fe484142705f9e46c2d1762c3411219d14c56c86205cc395f46a'), 42: ('0x1412c7090', '0x1400ca360', '0x1400d6f70', 'GameCoreEvent::UnitFormArmy', 'd683dbcdf9ba70ab203e90221c4af37b1a39fa2e7cf1d572f1ab21f6f88d293a'), 43: ('0x1412c70c0', '0x1400ca420', '0x1400d6fd0', 'GameCoreEvent::UnitFortificationChanged', '213a3457ceb7d47e9777deddda55a5b5722436466f9c79017f69cfb89f02d945'), 76: ('0x1412c76f0', '0x1400cbce0', '0x1400d7c30', 'GameCoreEvent::UnitGreatPersonChanged', '6525156f141496a67b658161200919e5c0c4e9fb02a513686b889c7412226941'), 78: ('0x1412c7750', '0x1400cbe60', '0x1400d7cf0', 'GameCoreEvent::UnitTradeChanged', '4d2db59ff5d389c28d5927a86c42f8b23690142e2df38f1a35b45972e86cb563'), 81: ('0x1412c77e0', '0x1400cc0a0', '0x1400d7e10', 'GameCoreEvent::UnitAttacksRemainingChanged', 'a65dfca1782d3d2f4274848ad4bbf81f510923f99ebf00fff968d6161043bc19'), 82: ('0x1412c7810', '0x1400cc160', '0x1400d7e70', 'GameCoreEvent::SpyAdded', '48a9a180230960b1fd342bc7b74d446f4cd160e75af549796adc732fc6c40079'), 84: ('0x1412c7870', '0x1400cc2e0', '0x1400d7f30', 'GameCoreEvent::SpyUpdated', '34ad74ba28ed7eae2295e884afaf078c74683898fd8fe4e9a138912d5b93d0c2'), 85: ('0x1412c78a0', '0x1400cc3a0', '0x1400d7f90', 'GameCoreEvent::SpyMissionUpdated', '2d13ad98b422577c5c45e056fb2331dae3eb1c882b38715dcbebaddab72f1090'), 278: ('0x1412c9cd0', '0x1400c6be0', '0x1400d53b0', 'GameCoreEvent::UnitEnteredBarbarianCamp', '5fc0cbe4ad387451c07b73e31061a7307e8e3efd2dfe121d093211328d414679')}
    parents = doc.get('parents', {})
    if doc.get('schema') != 'civ6rl.native_status_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or parents.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (parents.get('prior_empty_profile', {}).get('sha256') != _EVIDENCE_SHA256) or (doc.get('event', {}).get('kind') != 895056929) or (doc['event'].get('callback_va') != '0x140155530') or (doc['event'].get('writer', {}).get('va') != '0x14012e210') or (doc['event']['writer'].get('record_type') != 81) or (doc['event']['writer'].get('record_size') != 96) or (doc.get('receiver', {}).get('token_hook_installer_va') != '0x1401538b0') or (81 in doc['receiver'].get('token_hooked_record_types', [])) or (doc['receiver'].get('hook_absence_scope') != 'Only this captured installer is ruled out.'):
        raise RuntimeError('unit descriptor receiver proof identity changed')
    rows = doc['receiver'].get('rows', [])
    if {row.get('record_type') for row in rows} != expected_types or len(rows) != len(expected_types):
        raise RuntimeError('unit descriptor receiver row set changed')
    result = {}
    generic_calls = ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']
    for record_type, (row_va, setup_va, handler_va, name, handler_hash) in contracts.items():
        row = next((row for row in rows if row['record_type'] == record_type))
        expected_stores = {'and byte ptr [rax + 0x30], 0xfc', 'mov dword ptr [rax + 0x20], ebx', 'mov qword ptr [rcx + 8], rbx'}
        if row.get('record_size') != 96 or row.get('row_va') != row_va or row.get('setup_va') != setup_va or (row.get('handler_va') != handler_va) or (row.get('event_name', {}).get('text') != name) or (row.get('handler_direct_call_sequence') != generic_calls) or (row.get('handler_body_sha256') != handler_hash) or (set(row.get('empty_initialization_instructions', {})) != expected_stores) or (len(row.get('empty_initialization_instructions', {})) != 3):
            raise RuntimeError(f'unit descriptor receiver row {record_type:#x} changed')
        result[record_type] = {'event_name': name, 'handler_va': handler_va, 'handler_body_sha256': handler_hash, 'record_sizes': {96}}
    return result

def _simple_unit_alias_receiver_rows() -> dict[int, dict]:
    """Rows for three exact unit-event aliases with independently captured receivers."""
    path = _EVIDENCE.parents[1] / 'native-simple-unit-alias-receivers' / (SIMPLE_UNIT_ALIAS_RECEIVERS_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SIMPLE_UNIT_ALIAS_RECEIVERS_SHA256:
        raise RuntimeError('Simple unit alias receiver proof changed')
    doc = json.loads(raw)
    if doc.get('schema') != 'civ6rl.native_simple_unit_alias_receivers.static.v1' or doc.get('image', {}).get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('Simple unit alias receiver proof identity changed')
    expected = {32: ('0x35c46e9e', '0x140157510', '0x140128330', 96, 'GameCoreEvent::UnitKilledLifespanExpired', '0x1412c6eb0', '0x1400c9be0', '0x1400d6bb0', '9a186102e56656f6f7d25018de81a069c27d26bcc672581db544811c0de6536e'), 37: ('0x664a37b6', '0x140155640', '0x140128d30', 112, 'GameCoreEvent::UnitCaptured', '0x1412c6fa0', '0x1400c9fa0', '0x1400d6d90', '53c40aa7e46f3087aa0d631da28f60a9f05c2fb2caa2727768c87114a7886da8'), 238: ('0x9b294d70', '0x140156e40', '0x14013ca80', 112, 'GameCoreEvent::UnitHeroCreated', '0x1412c9550', '0x1400d37e0', '0x1400db9b0', '883cf39f24bed99496cdc46fcd72cd2386211a7059ed580b0415691b53ff7dfa')}
    rows = {}
    for source in doc.get('row_mapping', {}).get('rows', []):
        record_type = int(source['record_type'], 16)
        if record_type not in expected or record_type in rows:
            raise RuntimeError('Unexpected or duplicate simple unit alias receiver row')
        kind, callback, writer, size, name, row_va, setup_va, handler_va, handler_sha = expected[record_type]
        state = source.get('initialized_state', {})
        if source.get('kind') != kind or source.get('callback_va') != callback or source.get('writer_va') != writer or (int(source.get('record_size', '0'), 16) != size) or (source.get('event_name') != name) or (source.get('row_va') != row_va) or (source.get('setup_va') != setup_va) or (source.get('handler_va') != handler_va) or (source.get('handler_sha256') != handler_sha) or (state.get('pre_hook') is not None) or (state.get('post_hook') is not None) or (state.get('subscriber_count') != 0) or (state.get('subscriber_list_head_tail') != 268435455) or (state.get('dispatch_flags_after_mask') != 0) or (state.get('handler_call_order') != ['0x14098a780', '0x1400dc0d0', '0x14098a7b0']):
            raise RuntimeError(f'Unverified simple unit alias receiver row {record_type:#x}')
        rows[record_type] = {'event_name': name, 'handler_va': handler_va, 'handler_body_sha256': handler_sha, 'record_sizes': {size}}
    if set(rows) != set(expected):
        raise RuntimeError('Simple unit alias receiver proof is missing a required row')
    return rows

def _f391_receiver_row() -> dict[int, dict]:
    """Receiver-only proof for F391D7B3; producer queries are separate evidence."""
    path = _EVIDENCE.parents[1] / 'native-f391d7b3-receiver' / (F391_RECEIVER_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != F391_RECEIVER_SHA256:
        raise RuntimeError('F391 receiver source proof changed')
    doc = json.loads(raw)
    row = doc.get('receiver', {}).get('row', {})
    receiver = doc.get('receiver', {})
    writer = doc.get('event', {}).get('writer', {})
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400cef7b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cef7f', 'mov qword ptr [rax + 8], rbx': '0x1400cef74', 'mov qword ptr [rcx], rbx': '0x1400cefc3', 'mov qword ptr [rcx + 8], rbx': '0x1400cefc6', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cefca', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cefce'}
    actual_stores = row.get('empty_initialization_instructions', {})
    if doc.get('schema') != 'civ6rl.native_f391d7b3_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('registry', {}).get('kind') != '0xf391d7b3') or (doc.get('registry', {}).get('callback_va') != '0x140149210') or (doc.get('event', {}).get('kind') != 4086421427) or (doc['event'].get('callback_va') != '0x140149210') or (writer.get('va') != '0x140133ee0') or (writer.get('record_type') != 145) or (writer.get('record_size') != 160) or (row.get('record_type') != 145) or (row.get('record_size') != 160) or (row.get('row_va') != '0x1412c83e0') or (row.get('setup_va') != '0x1400cef20') or (row.get('handler_va') != '0x1400d9550') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::ImprovementVisibilityChanged') or (row.get('handler_body_sha256') != '0283301f19cc39778c43f4917b279d615dc269f61b3688c661858b17c4bb0aec') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (actual_stores != expected_stores) or (receiver.get('token_hook_installer_va') != '0x1401538b0') or (145 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('F391 receiver source changed')
    return {145: {'event_name': 'GameCoreEvent::ImprovementVisibilityChanged', 'handler_va': '0x1400d9550', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {160}}}

def _d857_receiver_row() -> dict[int, dict]:
    """Pinned empty receiver row for the D857B21B type-0x93 writer."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-d857b21b-receiver' / (D857_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, D857_RECEIVER_SHA256)
    row = doc['receiver']['row']
    receiver = doc['receiver']
    writer = doc['event']['writer']
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400cf0fb', 'mov dword ptr [rax + 0x20], ebx': '0x1400cf0ff', 'mov qword ptr [rax + 8], rbx': '0x1400cf0f4', 'mov qword ptr [rcx], rbx': '0x1400cf143', 'mov qword ptr [rcx + 8], rbx': '0x1400cf146', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cf14a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cf14e'}
    if doc.get('schema') != 'civ6rl.native_d857b21b_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('registry', {}).get('kind') != '0xd857b21b') or (doc['registry'].get('callback_va') != '0x140148e00') or (doc.get('event', {}).get('kind') != 3629625883) or (doc['event'].get('callback_va') != '0x140148e00') or (writer.get('va') != '0x140134240') or (writer.get('record_type') != 147) or (writer.get('record_size') != 128) or (row.get('record_type') != 147) or (row.get('record_size') != 128) or (row.get('row_va') != '0x1412c8440') or (row.get('setup_va') != '0x1400cf0a0') or (row.get('handler_va') != '0x1400d9610') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::ImprovementActivated') or (row.get('handler_body_sha256') != '486181bd0a7e40970cea0640e9516d3589a84ab815bd32626301be753ff57f28') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores) or (receiver.get('token_hook_installer_va') != '0x1401538b0') or (147 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('D857B21B receiver source changed')
    return {147: {'event_name': 'GameCoreEvent::ImprovementActivated', 'handler_va': '0x1400d9610', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {128}}}

def _position_value_receiver_rows() -> dict[int, dict]:
    """Pinned empty receiver rows for the three exact position/value callbacks."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-b1a27578-receivers' / (POSITION_VALUE_RECEIVERS_SHA256 + '.json')
    doc = load_pinned_json(path, POSITION_VALUE_RECEIVERS_SHA256)
    receiver = doc['receiver']
    expected_rows = {146: ('0x1412c8410', '0x1400cefe0', '0x1400d95b0', 'GameCoreEvent::ImprovementRemovedFromMap', '9c98f5be8fffc4c53cfb62e33ac46326ba396479fb81ad013ecc2a97ae129817', {'and byte ptr [rax + 0x30], 0xfc': '0x1400cf03b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cf03f', 'mov qword ptr [rax + 8], rbx': '0x1400cf034', 'mov qword ptr [rcx], rbx': '0x1400cf083', 'mov qword ptr [rcx + 8], rbx': '0x1400cf086', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cf08a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cf08e'}), 117: ('0x1412c7ea0', '0x1400cda20', '0x1400d8ad0', 'GameCoreEvent::FeatureChanged', '7b1e6fd1ee1e5ed8f4e83658a8eec26beadb6e228c9da7b84f4d6bb03646adf7', {'and byte ptr [rax + 0x30], 0xfc': '0x1400cda7b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cda7f', 'mov qword ptr [rax + 8], rbx': '0x1400cda74', 'mov qword ptr [rcx], rbx': '0x1400cdac3', 'mov qword ptr [rcx + 8], rbx': '0x1400cdac6', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cdaca', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cdace'}), 149: ('0x1412c84a0', '0x1400cf220', '0x1400d96d0', 'GameCoreEvent::TerrainTypeChanged', '28d8caf1d973093dfcdc4929cb4fde591d02f8fd94af693261446999aaf64e40', {'and byte ptr [rax + 0x30], 0xfc': '0x1400cf27b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cf27f', 'mov qword ptr [rax + 8], rbx': '0x1400cf274', 'mov qword ptr [rcx], rbx': '0x1400cf2c3', 'mov qword ptr [rcx + 8], rbx': '0x1400cf2c6', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cf2ca', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cf2ce'})}
    if doc.get('schema') != 'civ6rl.native_b1a27578_receiver_family.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (receiver.get('token_hook_installer_va') != '0x1401538b0') or set(receiver.get('token_hooked_record_types', [])) & set(expected_rows) or (len(doc.get('events', [])) != 3):
        raise RuntimeError('Position/value receiver family source changed')
    rows = receiver.get('rows', [])
    if {row.get('record_type') for row in rows} != set(expected_rows) or len(rows) != 3:
        raise RuntimeError('Position/value receiver family row set changed')
    result = {}
    expected_calls = ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')
    for row in rows:
        record_type = row['record_type']
        row_va, setup_va, handler_va, event_name, body_sha, expected_stores = expected_rows[record_type]
        if row.get('record_size') != 96 or row.get('row_va') != row_va or row.get('setup_va') != setup_va or (row.get('handler_va') != handler_va) or (row.get('event_name', {}).get('text') != event_name) or (row.get('handler_body_sha256') != body_sha) or (tuple(row.get('handler_direct_call_sequence', ())) != expected_calls) or (row.get('empty_initialization_instructions') != expected_stores):
            raise RuntimeError(f'Position/value receiver row {record_type:#x} changed')
        result[record_type] = {'event_name': event_name, 'handler_va': handler_va, 'handler_body_sha256': body_sha, 'record_sizes': {96}}
    return result

def _e808_receiver_row() -> dict[int, dict]:
    """Pinned initialized rows for E808A01E and its exact registered alias."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-e808a01e-receiver' / (E808_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, E808_RECEIVER_SHA256)
    rows = doc.get('receiver', {}).get('rows', [])
    receiver = doc.get('receiver', {})
    expected_rows = {177: ('0x1412c89e0', '0x1400d07e0', '0x1400da1b0', 'GameCoreEvent::CityFocusChanged', '2a72c51703cc77a85a98c67341c1978e40c1c421d749d9708a8e3243d4e99397', {'and byte ptr [rax + 0x30], 0xfc': '0x1400d083b', 'mov dword ptr [rax + 0x20], ebx': '0x1400d083f', 'mov qword ptr [rax + 8], rbx': '0x1400d0834', 'mov qword ptr [rcx], rbx': '0x1400d0883', 'mov qword ptr [rcx + 8], rbx': '0x1400d0886', 'mov qword ptr [rcx + 0x10], rbx': '0x1400d088a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400d088e'}), 239: ('0x1412c9580', '0x1400d38a0', '0x1400dba10', 'GameCoreEvent::CityLoyaltyChanged', 'c7891d0a5efa60e192f7a5b1a7e65105300f95e33839dcd7636d6d2d9c14b32d', {'and byte ptr [rax + 0x30], 0xfc': '0x1400d38fb', 'mov dword ptr [rax + 0x20], ebx': '0x1400d38ff', 'mov qword ptr [rax + 8], rbx': '0x1400d38f4', 'mov qword ptr [rcx], rbx': '0x1400d3943', 'mov qword ptr [rcx + 8], rbx': '0x1400d3946', 'mov qword ptr [rcx + 0x10], rbx': '0x1400d394a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400d394e'})}
    if doc.get('schema') != 'civ6rl.native_e808a01e_receiver_family.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or ({row.get('record_type') for row in rows} != set(expected_rows)) or (receiver.get('token_hook_installer_va') != '0x1401538b0') or set(receiver.get('token_hooked_record_types', [])) & set(expected_rows) or (tuple(doc.get('registry', {}).get('bindings', ())) != ({'kind': '0xe808a01e', 'callback_va': '0x140141380'}, {'kind': '0x89de2474', 'callback_va': '0x1401415e0'})) or (len(rows) != 2):
        raise RuntimeError('E808A01E receiver source changed')
    result = {}
    for row in rows:
        record_type = row['record_type']
        row_va, setup_va, handler_va, event_name, body_sha, expected_stores = expected_rows[record_type]
        if row.get('record_size') != 96 or row.get('row_va') != row_va or row.get('setup_va') != setup_va or (row.get('handler_va') != handler_va) or (row.get('event_name', {}).get('text') != event_name) or (row.get('handler_body_sha256') != body_sha) or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores):
            raise RuntimeError(f'E808 receiver row {record_type:#x} changed')
        result[record_type] = {'event_name': event_name, 'handler_va': handler_va, 'handler_body_sha256': body_sha, 'record_sizes': {96}}
    return result

def _thirty_ae_receiver_row() -> dict[int, dict]:
    """Pinned initialized receiver row for callback 30AE2A3D/type 0x90."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-30ae2a3d-receiver' / (THIRTY_AE_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, THIRTY_AE_RECEIVER_SHA256)
    row, receiver, event = (doc['receiver']['row'], doc['receiver'], doc['event'])
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400ceebb', 'mov dword ptr [rax + 0x20], ebx': '0x1400ceebf', 'mov qword ptr [rax + 8], rbx': '0x1400ceeb4', 'mov qword ptr [rcx], rbx': '0x1400cef03', 'mov qword ptr [rcx + 8], rbx': '0x1400cef06', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cef0a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cef0e'}
    if doc.get('schema') != 'civ6rl.native_30ae2a3d_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('registry', {}).get('kind') != '0x30ae2a3d') or (doc.get('registry', {}).get('callback_va') != '0x140148fc0') or (event.get('kind') != 816720445) or (event.get('callback_va') != '0x140148fc0') or (event.get('writer', {}).get('va') != '0x140133d80') or (event.get('writer', {}).get('record_type') != 144) or (event.get('writer', {}).get('record_size') != 144) or (row.get('record_type') != 144) or (row.get('record_size') != 144) or (row.get('row_va') != '0x1412c83b0') or (row.get('setup_va') != '0x1400cee60') or (row.get('handler_va') != '0x1400d94f0') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::ImprovementChanged') or (row.get('handler_body_sha256') != 'fb9577392bd8bfb4955e4290877a967dd61e04aceece6e634128748679a07790') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores) or (receiver.get('token_hook_installer_va') != '0x1401538b0') or (144 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('30AE2A3D receiver source changed')
    return {144: {'event_name': 'GameCoreEvent::ImprovementChanged', 'handler_va': '0x1400d94f0', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {144}}}

def _b19dd18b_receiver_row() -> dict[int, dict]:
    """Pinned empty receiver for BarbarianSpottedCity/type 0x114."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-b19dd18b-receiver' / (B19DD18B_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, B19DD18B_RECEIVER_SHA256)
    event, receiver, row = (doc['event'], doc['receiver'], doc['receiver']['row'])
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400c6abb', 'mov dword ptr [rax + 0x20], ebx': '0x1400c6abf', 'mov qword ptr [rax + 8], rbx': '0x1400c6ab4', 'mov qword ptr [rcx], rbx': '0x1400c6b03', 'mov qword ptr [rcx + 8], rbx': '0x1400c6b06', 'mov qword ptr [rcx + 0x10], rbx': '0x1400c6b0a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400c6b0e'}
    if doc.get('schema') != 'civ6rl.native_b19dd18b_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or event.get('kind') != 2979910027 or (event.get('callback_va') != '0x14013f940') or (event.get('writer', {}).get('va') != '0x140121260') or (event['writer'].get('record_type') != 276) or (event['writer'].get('record_size') != 112) or (row.get('record_type') != 276) or (row.get('record_size') != 112) or (row.get('row_va') != '0x1412c9c70') or (row.get('setup_va') != '0x1400c6a60') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::BarbarianSpottedCity') or (row.get('handler_va') != '0x1400d52f0') or (row.get('handler_body_sha256') != '4bd1e5f775910e9be7347693ba07080bc54031714b18717d41d0233855c56a9f') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores) or (276 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('B19DD18B receiver source changed')
    return {276: {'event_name': 'GameCoreEvent::BarbarianSpottedCity', 'handler_va': '0x1400d52f0', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}}}

def _six_d_selector_receiver_row() -> dict[int, dict]:
    """Pinned empty receiver row for the conditional 6D7163B0 A3 writer."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-6d7163b0-selector-receiver' / (SIX_D_SELECTOR_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, SIX_D_SELECTOR_RECEIVER_SHA256)
    row = doc['receiver']['row']
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400cfcfb', 'mov dword ptr [rax + 0x20], ebx': '0x1400cfcff', 'mov qword ptr [rax + 8], rbx': '0x1400cfcf4', 'mov qword ptr [rcx], rbx': '0x1400cfd43', 'mov qword ptr [rcx + 8], rbx': '0x1400cfd46', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cfd4a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cfd4e'}
    event = doc.get('event_route', {})
    receiver = doc.get('receiver', {})
    if doc.get('schema') != 'civ6rl.native_6d7163b0_selector_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registration', {}).get('kind') != '0x6d7163b0' or (doc.get('registration', {}).get('callback_va') != '0x140144b30') or (doc.get('registration', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5') or (event.get('a3_bridge_body', {}).get('start_va') != '0x14014cd40') or (event.get('a3_writer', {}).get('va') != '0x1401359d0') or (event.get('a3_writer', {}).get('record_type') != 163) or (event.get('a3_writer', {}).get('record_size') != 128) or (row.get('record_type') != 163) or (row.get('record_size') != 128) or (row.get('row_va') != '0x1412c8740') or (row.get('setup_va') != '0x1400cfca0') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::DistrictPillaged') or (row.get('handler_va') != '0x1400d9c10') or (row.get('handler_body_sha256') != '449f569df0495923c2500b813ed89fd18d16a7f541752c14ee80224e0a35611a') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores) or (163 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('6D7163B0 selector receiver source changed')
    return {163: {'event_name': 'GameCoreEvent::DistrictPillaged', 'handler_va': '0x1400d9c10', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {128}}}

def _45b517d6_receiver_row() -> dict[int, dict]:
    """Pinned, empty EXE receiver row for 45B517D6's FA/170 ring record."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-45b517d6-receiver' / (FORTY_FIVE_B517D6_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, FORTY_FIVE_B517D6_RECEIVER_SHA256)
    event, row = (doc['event'], doc['receiver']['row'])
    setup_instructions = {ins['text']: ins['va'] for fragment in row['setup_body']['fragments'] for ins in fragment['instructions']}
    expected = {'and byte ptr [rax + 0x30], 0xfc': '0x1400d41fb', 'mov dword ptr [rax + 0x20], ebx': '0x1400d41ff', 'mov qword ptr [rax + 8], rbx': '0x1400d41f4', 'mov qword ptr [rcx], rbx': '0x1400d4243', 'mov qword ptr [rcx + 8], rbx': '0x1400d4246', 'mov qword ptr [rcx + 0x10], rbx': '0x1400d424a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400d424e'}
    if doc.get('schema') != 'civ6rl.native_45b517d6_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('registry', {}).get('kind') != '0x45b517d6') or (doc.get('registry', {}).get('callback_va') != '0x14015a300') or (event.get('writer_va') != '0x14013dc90') or (event.get('writer_body_sha256') != '12fe51b9a90994a40506f535dcf0ce282f8567e761d533a675299abaa91beeab') or (event.get('record_type') != 250) or (event.get('record_size') != 368) or (event.get('callback_body_sha256') != '9274f0cb924c2b7cebbac4c534466a69503d24f7fa5047353493145d02645c05') or (row.get('record_type') != 250) or (row.get('row_va') != '0x1412c9790') or (row.get('setup_va') != '0x1400d41a0') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::WorldTextMessage') or (row.get('handler_va') != '0x1400dbe90') or (row.get('destructor_va') != '0x1400ea0e0') or (row.get('handler_body_sha256') != '5c6e89827776b3c48a4720d48deb228f6c9b5a0288196f717a072473980d81ce') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or any((setup_instructions.get(text) != va for text, va in expected.items())) or (doc.get('validation', {}).get('all_captured_instruction_bytes_rechecked_against_pe') is not True) or (doc.get('validation', {}).get('native_execution') is not False):
        raise RuntimeError('45B517D6 empty receiver source changed')
    return {250: {'event_name': 'GameCoreEvent::WorldTextMessage', 'handler_va': '0x1400dbe90', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {368}}}

def _unit_enter_formation_row() -> dict[int, dict]:
    """Pinned empty receiver row for UnitEnterFormation/type 0x26."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-7222312b-receiver' / (UNIT_ENTER_FORMATION_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, UNIT_ENTER_FORMATION_RECEIVER_SHA256)
    event, row, receiver = (doc['event'], doc['receiver']['row'], doc['receiver'])
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400ca0bb', 'mov dword ptr [rax + 0x20], ebx': '0x1400ca0bf', 'mov qword ptr [rax + 8], rbx': '0x1400ca0b4', 'mov qword ptr [rcx], rbx': '0x1400ca103', 'mov qword ptr [rcx + 8], rbx': '0x1400ca106', 'mov qword ptr [rcx + 0x10], rbx': '0x1400ca10a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400ca10e'}
    if doc.get('schema') != 'civ6rl.native_7222312b_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('parents', {}).get('prior_empty_profile', {}).get('sha256') != _EVIDENCE_SHA256 or (doc.get('parents', {}).get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5') or (event.get('kind') != 1914843435) or (event.get('callback_va') != '0x140155e40') or (event.get('writer', {}).get('va') != '0x140128f30') or (event['writer'].get('record_type') != 38) or (event['writer'].get('record_size') != 112) or (event['writer'].get('body', {}).get('fragments', [{}])[0].get('raw_sha256') != '2d4733a13d5419bec1b83d133cc7e6f0266380899712fdceaba40ba7855b4888') or (row.get('record_type') != 38) or (row.get('record_size') != 112) or (row.get('row_va') != '0x1412c6fd0') or (row.get('setup_va') != '0x1400ca060') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::UnitEnterFormation') or (row.get('handler_va') != '0x1400d6df0') or (row.get('handler_body_sha256') != 'cf9c50d73ad9275bfb2a625fda769c0d0ab9303f926085ec4638868338cd26aa') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores) or (38 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('UnitEnterFormation empty receiver source changed')
    return {38: {'event_name': 'GameCoreEvent::UnitEnterFormation', 'handler_va': '0x1400d6df0', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}}}

def _city_command_started_row() -> dict[int, dict]:
    """Pinned empty receiver for CityCommandStarted / record type 0x6D."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    path = _EVIDENCE.parents[1] / 'native-1d103404-receiver' / (CITY_COMMAND_STARTED_RECEIVER_SHA256 + '.json')
    doc = load_pinned_json(path, CITY_COMMAND_STARTED_RECEIVER_SHA256)
    event, receiver = (doc['event'], doc['receiver'])
    row = receiver['row']
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400cd47b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cd47f', 'mov qword ptr [rax + 8], rbx': '0x1400cd474', 'mov qword ptr [rcx], rbx': '0x1400cd4c3', 'mov qword ptr [rcx + 8], rbx': '0x1400cd4c6', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cd4ca', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cd4ce'}
    if doc.get('schema') != 'civ6rl.native_1d103404_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('registry', {}).get('kind') != '0x1d103404') or (doc.get('registry', {}).get('callback_va') != '0x1401411a0') or (event.get('kind') != 487601156) or (event.get('callback_va') != '0x1401411a0') or (event.get('writer', {}).get('va') != '0x140130970') or (event['writer'].get('record_type') != 109) or (event['writer'].get('record_size') != 112) or (row.get('record_type') != 109) or (row.get('record_size') != 112) or (row.get('row_va') != '0x1412c7d20') or (row.get('setup_va') != '0x1400cd420') or (row.get('initializer_call_ordinal_zero_based') != 193) or (row.get('event_name', {}).get('text') != 'GameCoreEvent::CityCommandStarted') or (row.get('event_name', {}).get('va') != '0x140fb5c98') or (row.get('handler_va') != '0x1400d87d0') or (row.get('handler_body_sha256') != '970c4e483d897eb6e83da08298fd738ea45b80158dc8965480ddfcb41fdd4923') or (tuple(row.get('handler_direct_call_sequence', ())) != ('call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0')) or (row.get('empty_initialization_instructions') != expected_stores) or (receiver.get('subscriber_dispatch_va') != '0x1400dc0d0') or (109 in receiver.get('token_hooked_record_types', [])):
        raise RuntimeError('CityCommandStarted empty receiver source changed')
    return {109: {'event_name': 'GameCoreEvent::CityCommandStarted', 'handler_va': '0x1400d87d0', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}}}

def _unit_embarked_state_changed_row() -> dict[int, dict]:
    """Pinned empty receiver for UnitEmbarkedStateChanged / type 0x2C."""
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    pin = 'b63d67dd276fb267b494673cbf6c846536248b090176d6c5d080787f6924bc82'
    path = _EVIDENCE.parents[2] / 'work' / 'native-84c1fdd6-receiver402.json'
    doc = load_pinned_json(path, pin)
    token_path = _EVIDENCE.parents[1] / 'native-combat-receiver-f8' / (TOKEN_HOOK_INSTALLER_PROOF_SHA256 + '.json')
    token_doc = load_pinned_json(token_path, TOKEN_HOOK_INSTALLER_PROOF_SHA256)
    receiver, row = (doc['receiver'], doc['row'])
    state = row['initialized_profile']
    installer = token_doc.get('token_lifecycle', {}).get('installer_body', {})
    instructions = [instruction for fragment in installer.get('fragments', []) for instruction in fragment.get('instructions', [])]
    installer_bytes = b''.join((bytes.fromhex(instruction['bytes']) for instruction in instructions))
    installed_record_types = []
    last_ecx = None
    for instruction in instructions:
        text = instruction.get('text', '')
        if text.startswith('mov ecx, '):
            last_ecx = int(text.split(', ', 1)[1], 0)
        if text == 'call 0x14011d6a0':
            installed_record_types.append(last_ecx)
    setup_instructions = [instruction for fragment in row.get('setup_body', {}).get('fragments', []) for instruction in fragment.get('instructions', [])]
    setup_map = {instruction.get('va'): instruction.get('text') for instruction in setup_instructions}
    if doc.get('schema') != 'civ6rl.native_84c1fdd6_receiver.static.v1' or receiver.get('kind') != '0x84c1fdd6' or receiver.get('event_name') != 'GameCoreEvent::UnitEmbarkedStateChanged' or (receiver.get('record_type') != '0x2c') or (receiver.get('record_size') != '0x70') or (receiver.get('callback_va') != '0x140155d20') or (receiver.get('writer_va') != '0x140129900') or (row.get('row_va') != '0x1412c70f0') or (row.get('setup_va') != '0x1400ca4e0') or (row.get('handler_va') != '0x1400d7030') or (row.get('handler_body_sha256') != '52675ab5f4d0558fcc1aef102a0487d181cafc06887d2db300bf056f5cef3b69') or (state.get('row_plus_0_pre_hook') is not None) or (state.get('row_plus_8_post_hook') is not None) or (state.get('row_plus_0x10') != 0) or (state.get('state_plus_0x08_array') != 0) or (state.get('state_plus_0x20_subscriber_count') != 0) or (state.get('state_plus_0x24_head') != 268435455) or (state.get('state_plus_0x28_tail') != 268435455) or (state.get('state_plus_0x30_flags_mask') != '0xFC') or (state.get('state_plus_0x30_flags_value') != 0) or (setup_map.get('0x1400ca58a') != 'mov qword ptr [rcx + 0x10], rbx') or (installer.get('start_va') != '0x1401538b0') or (hashlib.sha256(installer_bytes).hexdigest() != '47d0f3da083d41203373572c708cf602d828187069f0970ffc999a451b687771') or (installed_record_types != [248, 132, 251, 252, 253, 312, 313, 314, 315, 316, 254]) or (44 in installed_record_types):
        raise RuntimeError('UnitEmbarkedStateChanged receiver proof/profile changed')
    return {44: {'event_name': 'GameCoreEvent::UnitEmbarkedStateChanged', 'handler_va': '0x1400d7030', 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}}}

def _unit_killed_in_combat_row() -> dict:
    """Capture-gated empty receiver for record 0x1E / UnitKilledInCombat."""
    path = _EVIDENCE.parents[1] / 'native-754cbd1b-receiver' / (UNIT_PAIR_RECEIVER_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != UNIT_PAIR_RECEIVER_SHA256:
        raise RuntimeError('UnitKilledInCombat receiver proof changed')
    doc = json.loads(raw)
    row = doc.get('receiver', {}).get('row', {})
    expected_state_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400c9abb', 'mov dword ptr [rax + 0x20], ebx': '0x1400c9abf', 'mov qword ptr [rax + 8], rbx': '0x1400c9ab4', 'mov qword ptr [rcx + 8], rbx': '0x1400c9b06', 'mov qword ptr [rcx + 0x10], rbx': '0x1400c9b0a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400c9b0e', 'mov qword ptr [rcx], rbx': '0x1400c9b03'}
    receiver = doc.get('receiver', {})
    if doc.get('schema') != 'civ6rl.native_754cbd1b_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('parents', {}).get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('parents', {}).get('prior_empty_profile', {}).get('sha256') != _EVIDENCE_SHA256) or (doc.get('event', {}).get('kind') != 1967963419) or (doc['event'].get('callback_va') != '0x1401573e0') or (doc['event'].get('writer', {}).get('va') != '0x140127f30') or (doc['event']['writer'].get('record_type') != 30) or (doc['event']['writer'].get('record_size') != 112) or (doc['event']['writer'].get('body', {}).get('fragments', [{}])[0].get('raw_sha256') != '81077506dc33ae13434d627132415b305cd8e1977bd275011260b365baef4e3a') or (row.get('record_type') != 30) or (row.get('record_size') != 112) or (row.get('row_va') != '0x1412c6e50') or (row.get('setup_va') != '0x1400c9a60') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::UnitKilledInCombat') or (row.get('handler_va') != '0x1400d6af0') or (row.get('handler_direct_call_sequence') != ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']) or (row.get('handler_body_sha256') != '29a2243607f6f33197f9c96f62bc417e910a171b67a0639b53b80ac73325ac2b') or (row.get('empty_initialization_instructions') != expected_state_stores) or (receiver.get('token_hook_installer_va') != '0x1401538b0') or (30 in receiver.get('token_hooked_record_types', [])) or (receiver.get('hook_absence_scope') != 'Only this captured token-hook installer is ruled out.'):
        raise RuntimeError('UnitKilledInCombat receiver source changed')
    return {'event_name': 'GameCoreEvent::UnitKilledInCombat', 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}, 'row_plus_0x10_hook_initialized_null': True}

def _unit_command_started_row() -> dict:
    """Capture-gated empty receiver for record 0x48 / UnitCommandStarted."""
    path = _EVIDENCE.parents[1] / 'native-fc7db95e-receiver' / (UNIT_COMMAND_RECEIVER_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != UNIT_COMMAND_RECEIVER_SHA256:
        raise RuntimeError('UnitCommandStarted receiver proof changed')
    doc = json.loads(raw)
    row = doc.get('receiver', {}).get('row', {})
    receiver = doc.get('receiver', {})
    expected_stores = {'and byte ptr [rax + 0x30], 0xfc': '0x1400cba3b', 'mov dword ptr [rax + 0x20], ebx': '0x1400cba3f', 'mov qword ptr [rax + 8], rbx': '0x1400cba34', 'mov qword ptr [rcx], rbx': '0x1400cba83', 'mov qword ptr [rcx + 8], rbx': '0x1400cba86', 'mov qword ptr [rcx + 0x10], rbx': '0x1400cba8a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400cba8e'}
    if doc.get('schema') != 'civ6rl.native_fc7db95e_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('parents', {}).get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('parents', {}).get('prior_empty_profile', {}).get('sha256') != _EVIDENCE_SHA256) or (doc.get('event', {}).get('kind') != 4236097886) or (doc['event'].get('callback_va') != '0x140155880') or (doc['event'].get('writer', {}).get('va') != '0x14012d100') or (doc['event']['writer'].get('record_type') != 72) or (doc['event']['writer'].get('record_size') != 112) or (doc['event']['writer'].get('body', {}).get('fragments', [{}])[0].get('raw_sha256') != 'a9ab1f0f4b5639c9b942c9db22b43141d1522abb93fe6055c57b53088f153456') or (row.get('record_type') != 72) or (row.get('record_size') != 112) or (row.get('row_va') != '0x1412c7630') or (row.get('setup_va') != '0x1400cb9e0') or (row.get('event_name', {}).get('text') != 'GameCoreEvent::UnitCommandStarted') or (row.get('handler_va') != '0x1400d7ab0') or (row.get('handler_direct_call_sequence') != ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']) or (row.get('handler_body_sha256') != '7a48dd9bcb6665e70c9889b8bfeab915b351e44799ba63ea83909cd0bf5b5a2c') or (row.get('empty_initialization_instructions') != expected_stores) or (receiver.get('token_hook_installer_va') != '0x1401538b0') or (72 in receiver.get('token_hooked_record_types', [])) or (receiver.get('hook_absence_scope') != 'Only this captured token-hook installer is ruled out.'):
        raise RuntimeError('UnitCommandStarted receiver source changed')
    return {'event_name': 'GameCoreEvent::UnitCommandStarted', 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}, 'row_plus_0x10_hook_initialized_null': True}

def _unit_promotion_rows() -> dict[int, dict]:
    """Rows for UnitPromoted and UnitUpgraded from one pinned receiver capture."""
    path = _EVIDENCE.parents[1] / 'native-661109d9-receiver' / (UNIT_PROMOTION_RECEIVER_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != UNIT_PROMOTION_RECEIVER_SHA256:
        raise RuntimeError('unit promotion receiver proof changed')
    doc = json.loads(raw)
    if doc.get('schema') != 'civ6rl.native_661109d9_receiver.static.v1' or doc.get('images', {}).get('exe_sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or doc.get('parents', {}).get('registry', {}).get('sha256') != 'ec49b8df386e35cafc401986fb1512a89e19ebe7d94f8963684ac67505a1b0f5' or (doc.get('parents', {}).get('prior_empty_profile', {}).get('sha256') != _EVIDENCE_SHA256) or (doc.get('receiver', {}).get('registrar_va') != '0x1400dc450') or (doc['receiver'].get('table_base_va') != '0x1412c68b0') or (doc['receiver'].get('subscriber_dispatch_va') != '0x1400dc0d0') or (doc['receiver'].get('token_hook_installer_va') != '0x1401538b0') or (45 in doc['receiver'].get('token_hooked_record_types', [])) or (47 in doc['receiver'].get('token_hooked_record_types', [])):
        raise RuntimeError('unit promotion receiver proof identity changed')
    contracts = {45: ('0x661109d9', '0x140158720', '0x140129b00', 'aa7f67ad14e4346fabcc37ebcd36114de136e895cbde0818a540dda8a8429305', 'e899d0bb4b838236a821ada18cdd80d322015f4747979898764188c43f6242c5', '0x1412c7120', '0x1400ca5a0', '0x1400d7090', 'GameCoreEvent::UnitPromoted', {'and byte ptr [rax + 0x30], 0xfc': '0x1400ca5fb', 'mov dword ptr [rax + 0x20], ebx': '0x1400ca5ff', 'mov qword ptr [rax + 8], rbx': '0x1400ca5f4', 'mov qword ptr [rcx], rbx': '0x1400ca643', 'mov qword ptr [rcx + 8], rbx': '0x1400ca646', 'mov qword ptr [rcx + 0x10], rbx': '0x1400ca64a', 'mov qword ptr [rcx + 0x18], rdx': '0x1400ca64e'}), 47: ('0x4b7440e9', '0x140159070', '0x140129f00', 'e53d8f0770cbb6a8d5ac1e6fe7e427d21c4c6ebb9cc8fd8f0a9d8d07bfe43ab2', '3316ffb0baf656749aae779f128a3a5a185527afc877c9f74b571d6aaf1f57d2', '0x1412c7180', '0x1400ca720', '0x1400d7150', 'GameCoreEvent::UnitUpgraded', {'and byte ptr [rax + 0x30], 0xfc': '0x1400ca77b', 'mov dword ptr [rax + 0x20], ebx': '0x1400ca77f', 'mov qword ptr [rax + 8], rbx': '0x1400ca774', 'mov qword ptr [rcx], rbx': '0x1400ca7c3', 'mov qword ptr [rcx + 8], rbx': '0x1400ca7c6', 'mov qword ptr [rcx + 0x10], rbx': '0x1400ca7ca', 'mov qword ptr [rcx + 0x18], rdx': '0x1400ca7ce'})}
    result = {}
    producer_docs = doc.get('producers', {})
    rows = doc.get('receiver', {}).get('rows', {})
    if set(rows) != {'0x2d', '0x2f'} or set(producer_docs) != {'0x661109d9', '0x4b7440e9'}:
        raise RuntimeError('unit promotion receiver row/event set changed')
    for record_type, (kind, callback, writer, callback_hash_expected, writer_hash, row_va, setup_va, handler_va, name, expected_stores) in contracts.items():
        key = f'0x{record_type:x}'
        row = rows.get(key, {})
        producer = producer_docs.get(kind, {})
        callback_hash = producer.get('callback_body', {}).get('fragments', [{}])[0].get('raw_sha256')
        writer_hash_actual = producer.get('writer_body', {}).get('fragments', [{}])[0].get('raw_sha256')
        if producer.get('callback_va') != callback or producer.get('writer_va') != writer or producer.get('record_type') != record_type or (producer.get('record_size') != 112) or (callback_hash != callback_hash_expected) or (writer_hash_actual != writer_hash) or (row.get('row_va') != row_va) or (row.get('setup_va') != setup_va) or (row.get('handler_va') != handler_va) or (row.get('record_type') != record_type) or (row.get('record_size') != 112) or (row.get('event_name', {}).get('text') != name) or (row.get('handler_direct_call_sequence') != ['call 0x14098a780', 'call 0x1400dc0d0', 'call 0x14098a7b0']) or (row.get('empty_initialization_instructions') != expected_stores):
            raise RuntimeError(f'unit promotion receiver row {record_type:#x} changed')
        result[record_type] = {'event_name': name, 'handler_va': handler_va, 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}, 'row_plus_0x10_hook_initialized_null': True}
    return result

def _diplomacy_row(record_type) -> dict:
    profiles = {129: (_DIPLOMACY_MEET_SHA256, '133d411c', '0x1412c80e0', '0x1400ce320', '0x1400d8f50', 'GameCoreEvent::DiplomacyMeet', 'a20d41d69684aa75f309f92826241454b07b8ea5df45e8c848cf77d36c9a3afe'), 130: (_DIPLOMACY_MAJOR_MINOR_SHA256, '08b3bf96', '0x1412c8110', '0x1400ce3e0', '0x1400d8fb0', 'GameCoreEvent::DiplomacyMeetMajorMinor', 'ae43e1c770125e996a6112c67140033be9c1320b996b074ab209a5f70e4e742c'), 131: (_DIPLOMACY_MAJORS_SHA256, '892f171c', '0x1412c8140', '0x1400ce4a0', '0x1400d9010', 'GameCoreEvent::DiplomacyMeetMajors', '564546e4f4f231e140936f4f41b0be68515d9a05880f6c5bf9f6b147716cea6c')}
    pin, kind, row_va, setup_va, handler_va, event_name, handler_hash = profiles[record_type]
    if not pin:
        raise RuntimeError('DiplomacyMeet receiver source proof is not pinned')
    path = _EVIDENCE.parents[1] / ('native-event-' + kind) / (pin + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise RuntimeError('DiplomacyMeet receiver source proof changed')
    doc = json.loads(raw)
    row = doc['empty_receiver_source']
    if doc.get('schema') != 'civ6rl.native_event_' + kind + '.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or row['record_type'] != record_type or (row['record_size'] != 96) or (row['row_va'] != row_va) or (row['setup_va'] != setup_va) or (row['handler_va'] != handler_va) or (row['subscriber_dispatch_va'] != '0x1400dc0d0') or (row['event_name'] != event_name) or (row['handler_body_sha256'] != handler_hash) or (row['initialized_state'] != {'pre_hook_row_plus_0': None, 'post_hook_row_plus_8': None, 'subscriber_count_state_plus_0x20': 0, 'subscriber_array_state_plus_8': 0, 'busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc': 0}):
        raise RuntimeError('DiplomacyMeet empty receiver contract changed')
    return {'event_name': row['event_name'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {96}}

def _operation_segment_row() -> dict:
    path = _EVIDENCE.parents[1] / 'native-event-cb0345f1' / (_OPERATION_SEGMENT_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _OPERATION_SEGMENT_SHA256:
        raise RuntimeError('Operation segment receiver source proof changed')
    doc = json.loads(raw)
    row = doc['empty_receiver_source']
    if doc.get('schema') != 'civ6rl.native_event_cb0345f1.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or row['record_type'] != 69 or (row['record_size'] != 112) or (row['row_va'] != '0x1412c75a0') or (row['setup_va'] != '0x1400cb7a0') or (row['handler_va'] != '0x1400d7990') or (row['subscriber_dispatch_va'] != '0x1400dc0d0') or (row['event_name'] != 'GameCoreEvent::UnitOperationSegmentComplete') or (row['handler_body_sha256'] != '86644f19b2b484f89fe814103d785400d18786bdcc72cf3d1b6df549fb8292c1') or (row['initialized_state'] != {'pre_hook_row_plus_0': None, 'post_hook_row_plus_8': None, 'subscriber_count_state_plus_0x20': 0, 'subscriber_array_state_plus_8': 0, 'busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc': 0}):
        raise RuntimeError('Operation segment empty receiver contract changed')
    return {'event_name': row['event_name'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {112}}

def _improvement_added_row() -> dict:
    path = _EVIDENCE.parents[1] / 'native-event-e5b20b82' / (_IMPROVEMENT_ADDED_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _IMPROVEMENT_ADDED_SHA256:
        raise RuntimeError('Improvement added receiver source proof changed')
    doc = json.loads(raw)
    row = doc['empty_receiver_source']
    if doc.get('schema') != 'civ6rl.native_event_e5b20b82.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or row['record_type'] != 143 or (row['record_size'] != 144) or (row['row_va'] != '0x1412c8380') or (row['setup_va'] != '0x1400ceda0') or (row['handler_va'] != '0x1400d9490') or (row['subscriber_dispatch_va'] != '0x1400dc0d0') or (row['event_name'] != 'GameCoreEvent::ImprovementAddedToMap') or (row['handler_body_sha256'] != '451629dbb05ff79ee1303250f7f5e758fdfa6dbf9ba1684b228db0fb23939105') or (row['initialized_state'] != {'pre_hook_row_plus_0': None, 'post_hook_row_plus_8': None, 'subscriber_count_state_plus_0x20': 0, 'subscriber_array_state_plus_8': 0, 'busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc': 0}):
        raise RuntimeError('Improvement added empty receiver contract changed')
    return {'event_name': row['event_name'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {144}}

def _improvement_owner_row() -> dict:
    """Add only the separately proven row94, never infer other empty handlers."""
    path = _EVIDENCE.parents[1] / 'native-event-a625c726' / (_IMPROVEMENT_OWNER_SHA256 + '.json')
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _IMPROVEMENT_OWNER_SHA256:
        raise RuntimeError('Improvement ownership receiver source proof changed')
    doc = json.loads(raw)
    row = doc['empty_receiver_source']
    if doc.get('schema') != 'civ6rl.native_event_a625c726.static.v1' or doc['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or row['record_type'] != 148 or (row['record_size'] != 144) or (row['row_va'] != '0x1412c8470') or (row['setup_va'] != '0x1400cf160') or (row['handler_va'] != '0x1400d9670') or (row['subscriber_dispatch_va'] != '0x1400dc0d0') or (row['event_name'] != 'GameCoreEvent::ImprovementOwnershipChanged') or (row['handler_body_sha256'] != '139e89348be7844a5936dc8f7535894246970eb2ec76b09d0c6ae7ee877a6692') or (row['initialized_state'] != {'pre_hook_row_plus_0': None, 'post_hook_row_plus_8': None, 'subscriber_count_state_plus_0x20': 0, 'subscriber_array_state_plus_8': 0, 'busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc': 0}):
        raise RuntimeError('Improvement ownership empty receiver contract changed')
    return {'event_name': row['event_name'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': {144}}

def _load_rows() -> dict[int, dict[str, str]]:
    raw = _resolve_resource_path(_EVIDENCE).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if not _EVIDENCE_SHA256 or actual != _EVIDENCE_SHA256:
        raise RuntimeError(f'Deferred handler proof changed: {actual}')
    doc = json.loads(raw)
    if doc.get('schema') != 'civ6rl.native_deferred_empty_handlers.v1':
        raise RuntimeError('Unsupported deferred-handler evidence schema')
    image = doc.get('image', {})
    if image.get('sha256') != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('Deferred-handler evidence refers to an unexpected EXE')
    rows: dict[int, dict[str, str]] = {}
    for row in doc['row_mapping']['rows']:
        index = int(row['record_type'], 16)
        state = row['initialized_state']
        if state['pre_hook_row_plus_0'] is not None or state['post_hook_row_plus_8'] is not None or state['subscriber_count_state_plus_0x20'] != 0 or (state['subscriber_array_state_plus_8'] != 0) or (state['busy_and_deferred_remove_flag_bits_state_plus_0x30_masked_with_0xfc'] != 0):
            raise RuntimeError(f'Evidence no longer describes an empty handler row {index:#x}')
        rows[index] = {'event_name': row['event_name'], 'handler_va': row['handler_va'], 'handler_body_sha256': row['handler_body_sha256'], 'record_sizes': set()}
    for shape in doc['observed_record_shapes']:
        row = rows.get(int(shape['record_type'], 16))
        if row is None or shape['header_size_offset'] != 0 or shape['header_type_offset'] != 4:
            raise RuntimeError('Observed record shape no longer matches the native header contract')
        row['record_sizes'].update(shape['record_sizes_bytes'])
    for shape in doc.get('source_derived_record_shapes', []):
        row = rows.get(int(shape['record_type'], 16))
        size = shape['record_size_bytes']
        expected_provenance = f'Static EXE callback queue writer stores size {size:#x} and this record type; not observed in prefix52.'
        if row is None or size not in (96, 112, 128, 144, 160) or shape['provenance'] != expected_provenance:
            raise RuntimeError('Source-derived writer shape no longer matches the proven queue contract')
        row['record_sizes'].add(size)
    if any((not row['record_sizes'] for row in rows.values())):
        raise RuntimeError('Missing observed record size for an allowed handler row')
    if len(rows) != 142:
        raise RuntimeError(f'Expected 142 distinct source-backed rows, got {len(rows)}')
    if any((kind in rows for kind in (148, 143, 69, 129, 130, 137, 33, 30, 45, 47, 72, 74, 79, 247, 38))):
        raise RuntimeError('Separately proven improvement ownership row collides with initial rows')
    rows[148] = _improvement_owner_row()
    rows[143] = _improvement_added_row()
    rows[69] = _operation_segment_row()
    rows[129] = _diplomacy_row(129)
    rows[130] = _diplomacy_row(130)
    rows[131] = _diplomacy_row(131)
    rows[137] = _diplomacy_relationship_row()
    from civ6_host.runtime.native.native_event_7dddaff1 import receiver_row as declare_war_receiver_row
    if 127 in rows:
        raise RuntimeError('DeclareWar receiver collides with initial rows')
    rows[127] = declare_war_receiver_row()
    from civ6_host.runtime.native.native_event_78932d93 import receiver_row as position_d5_receiver_row
    if 213 in rows:
        raise RuntimeError('D5 receiver collides with initial rows')
    rows[213] = position_d5_receiver_row()
    from civ6_host.runtime.native.native_trade_route_position_events import receiver_row as position_d6_receiver_row
    if 214 in rows:
        raise RuntimeError('D6 receiver collides with initial rows')
    rows[214] = position_d6_receiver_row()
    from civ6_host.runtime.native.native_event_5d706996 import receiver_row as trade_d7_receiver_row
    if 215 in rows:
        raise RuntimeError('D7 receiver collides with initial rows')
    rows[215] = trade_d7_receiver_row()
    rows[33] = _unit_damage_row()
    rows.update(_a479_receivers())
    rows[247] = _status_message_row()
    for record_type, family_row in _unit_descriptor_family_rows().items():
        existing = rows.get(record_type)
        if existing is not None:
            if existing['event_name'] != family_row['event_name'] or existing['handler_va'] != family_row['handler_va'] or existing['handler_body_sha256'] != family_row['handler_body_sha256'] or (existing['record_sizes'] != family_row['record_sizes']):
                raise RuntimeError(f'unit descriptor family disagrees with existing row {record_type:#x}')
        else:
            rows[record_type] = family_row
    rows[30] = _unit_killed_in_combat_row()
    rows[72] = _unit_command_started_row()
    rows.update(_unit_promotion_rows())
    for record_type, alias_row in _simple_unit_alias_receiver_rows().items():
        if record_type in rows:
            raise RuntimeError(f'Simple unit alias row collides with existing receiver {record_type:#x}')
        rows[record_type] = alias_row
    for record_type, receiver_row in _f391_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'F391 receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _d857_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'D857 receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _position_value_receiver_rows().items():
        if record_type in rows:
            raise RuntimeError(f'Position/value receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _e808_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'E808A01E receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _thirty_ae_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'30AE2A3D receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _b19dd18b_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'B19DD18B receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _six_d_selector_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'6D7163B0 selector receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _45b517d6_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'45B517D6 receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _unit_enter_formation_row().items():
        if record_type in rows:
            raise RuntimeError(f'UnitEnterFormation receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _city_command_started_row().items():
        if record_type in rows:
            raise RuntimeError(f'CityCommandStarted receiver row collides with existing type {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _barbarian_raid_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'BarbarianRaidStarted receiver row collides with {record_type:#x}')
        rows[record_type] = receiver_row
    if any((record_type in rows for record_type in (120, 121))):
        raise RuntimeError('Natural-wonder pair receiver rows collide with the base profile')
    rows.update(_natural_wonder_pair_rows())
    for record_type, receiver_row in _district_combat_receiver_row().items():
        if record_type in rows:
            raise RuntimeError(f'DistrictCombatChanged receiver row collides with {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _f74_district_damage_changed_row().items():
        if record_type in rows:
            raise RuntimeError(f'DistrictDamageChanged receiver row collides with {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _unit_embarked_state_changed_row().items():
        if record_type in rows:
            raise RuntimeError(f'UnitEmbarkedStateChanged receiver row collides with {record_type:#x}')
        rows[record_type] = receiver_row
    for record_type, receiver_row in _e660_building_pillaged_row().items():
        if record_type in rows:
            raise RuntimeError(f'BuildingPillaged receiver row collides with {record_type:#x}')
        rows[record_type] = receiver_row
    from civ6_host.runtime.native.native_event_great_work import receiver_row as great_work_receiver_row
    if 220 in rows:
        raise RuntimeError('GreatWorkCreated receiver row collides with existing proof')
    rows[220] = great_work_receiver_row()
    from civ6_host.runtime.goody_hut_reward import receiver_row as goody_hut_reward_row
    if 259 in rows:
        raise RuntimeError('GoodyHutReward row collides with historical profile')
    rows[259] = goody_hut_reward_row()
    from civ6_host.runtime.a0_emergencies_updated import receiver_rows
    extra = receiver_rows()
    if set(rows) & set(extra):
        raise ValueError('Publication receiver overlaps an existing source profile')
    rows.update(extra)
    return rows

def resolve_empty_receiver_row(record_type, *, execution_image=None):
    if type(record_type) is int and execution_image is not None:
        from civ6_host.runtime.execution_images import _PROFILE
        if execution_image is _PROFILE:
            if record_type in (126, 127):
                from civ6_host.runtime.xp2_diplomacy_events import receiver_row
                return receiver_row(record_type)
            if record_type == 19:
                from civ6_host.runtime.xp2_player_restored import receiver_row
                return receiver_row()
            from civ6_host.runtime.xp2_capture_notification_source import RECORD_TYPES, receiver_row
            if record_type in RECORD_TYPES:
                return receiver_row(record_type)
    row = _ROWS.get(record_type)
    if row is None and type(record_type) is int and record_type == 116:
        from civ6_host.runtime.xp2_feature_events import receiver_row
        return receiver_row()
    if row is None and type(record_type) is int and record_type == 208:
        from civ6_host.runtime.a0_policy_unlock import receiver_row
        return receiver_row()
    if row is None and type(record_type) is int and (record_type in (241, 242, 243)):
        from civ6_host.runtime.city_scalar_event_profiles import receiver_row
        return receiver_row(record_type)
    if row is None and type(record_type) is int and (record_type in (260, 261)):
        from civ6_host.runtime.game_history_event_profile import receiver_rows
        return receiver_rows()[record_type]
    if row is None and type(record_type) is int and record_type == 0x106:
        from civ6_host.runtime.xp2_history_event_profile import property_receiver_row
        return property_receiver_row()
    if row is None and type(record_type) is int and record_type in (0x107, 0x108):
        from civ6_host.runtime.xp2_history_event_profile import age_receiver_rows
        return age_receiver_rows()[record_type]
    if row is None and type(record_type) is int and (record_type == 266):
        from civ6_host.runtime.game_era_score_event_profile import receiver_row
        return receiver_row()
    if row is None and type(record_type) is int and record_type == 267:
        from civ6_host.runtime.xp2_history_event_profile import turn21_receiver_row
        return turn21_receiver_row()
    if row is None and type(record_type) is int and record_type == 0xe2:
        from civ6_host.runtime.xp2_history_event_profile import turn21_scalar_receiver_row
        return turn21_scalar_receiver_row(record_type)
    if row is None and type(record_type) is int and record_type in (0xdf, 0xe3, 0xe4):
        from civ6_host.runtime.xp2_history_event_profile import descriptor_receiver_row
        return descriptor_receiver_row(record_type)
    if row is None and type(record_type) is int and (record_type in (309, 310, 311, 312, 315, 325)):
        from civ6_host.runtime.xp2_turn_event_records import receiver_rows
        return receiver_rows()[record_type]
    if row is None and type(record_type) is int and record_type == 0x97:
        from civ6_host.runtime.xp2_turn_event_records import terrain_receiver_row
        return terrain_receiver_row()
    if row is None and type(record_type) is int and (record_type == 322):
        from civ6_host.runtime.xp2_favor_event_profile import receiver_rows
        return receiver_rows()[record_type]
    if row is None and type(record_type) is int and (record_type == 201):
        from civ6_host.runtime.xp2_wmd_fallout_visibility import receiver_row
        return receiver_row()
    return row

def validate_empty_profile_record(record: bytes | bytearray | memoryview, *, observer_registered: bool, state_pointer_nonnull: bool, pre_hook: int | None, post_hook: int | None, subscriber_count: int, state_flags: int, execution_image=None) -> dict[str, int | str]:
    """Validate that one ring record takes the proven no-observer/no-subscriber path.

    Ring header fields are native size at +0 and handler row index at +4. This
    helper only authorizes advancing after the known empty dispatch branch; the
    caller remains responsible for actually consuming the ring entry exactly once.
    """
    if observer_registered is not False:
        raise ValueError('Observer dispatch uses a different native drain path')
    if state_pointer_nonnull is not True:
        raise ValueError('Native subscriber-state allocation did not produce a usable state')
    if pre_hook is not None or post_hook is not None:
        raise ValueError('A non-null pre/post hook requires its native callback')
    if type(subscriber_count) is not int or subscriber_count != 0:
        raise ValueError('A non-empty subscriber list cannot be drained as an empty profile')
    if type(state_flags) is not int or state_flags & 3:
        raise ValueError('Busy/deferred-removal state requires native subscriber dispatch')
    view = memoryview(record).cast('B')
    if len(view) < 8:
        raise ValueError('Truncated deferred record header')
    size = int.from_bytes(view[0:4], 'little')
    record_type = int.from_bytes(view[4:8], 'little')
    if size != len(view):
        raise ValueError('Deferred record size does not match its bounded buffer')
    row = resolve_empty_receiver_row(record_type, execution_image=execution_image)
    if row is None:
        raise ValueError(f'No empty-profile handler proof for record type {record_type:#x}')
    if size not in row['record_sizes']:
        raise ValueError(f'Unexpected record size {size:#x} for type {record_type:#x}')
    return {'record_type': record_type, 'record_size': size, 'event_name': row['event_name'], 'handler_va': row['handler_va']}
_ROWS = _load_rows()

"""Source selection for the XP2 History/Era/Era-score A0 family.

The event codecs and EXE receivers are shared. XP2 membership is admitted by
this profile independently from the XP1 placement producer family.
"""
from functools import lru_cache
import hashlib
from types import MappingProxyType

from .configuration_profiles import _source
from .saved_load_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp2-game-history-static/source-profile-v1.json',
          '17ac63754f1634ec22ef6ff3e6d2f1f3e271d535e001aa1b6f2a2bdbda677b7c')
HISTORY_KIND = 0x4710f1a4
ERA_KIND = 0xf50673b7
ERA_SCORE_KIND = 0x788b7534
TURN21_KIND = 0xa47d34e3
TURN21_SPEC = (0x10b, 6, 0x14b9d0, 0x120200, 0xc62e0, 0xd4f30)
TURN21_SOURCE = ('work/host-extensions/xp2-game-history-static/turn21-event-source.json',
                 'acc2bbd1b9c44bf5395d1090f63c26d5f4dc679ec4953a9d21a05bd170b15d98')
TURN21_RECEIVER = ('work/host-extensions/xp2-game-history-static/turn21-event-receiver.json',
                   '9a90c413c040426779afc061dea76a5af813c24eefdd0f0a6fc48c2bf977525d')
TURN21_SCALAR_SOURCES = (
    ('work/host-extensions/xp2-game-history-static/turn21-e2-source.json',
     'a8877f2b4c7b7af7816451eda64fe72c16b13600f9b6dc6184cad975c9e656c8'),
    ('work/host-extensions/xp2-game-history-static/turn21-e2-neighbors.json',
     'd962f07f4acb659104e717274778c709bff49f97c778cd7878e6f5d8702ddf59'),
    ('work/host-extensions/xp2-game-history-static/turn21-de-receiver.json',
     '907dbb56c7b2f497a0ddbd0179a21a23d2297e12a8b3c893ddad93e8d5cd7836'),
)
TURN21_SCALARS = MappingProxyType({
    0x8c6b2399: (0xe2, 0, 0x148960, 0x13bc30, 0xd2ee0, 0xdb530),
    0x69356374: (0xde, 0, 0x148540, 0x13b4f0, 0xd2b9f, 0xdb350),
})
TURN21_DESCRIPTOR_KIND = 0xcf9c73f1
TURN21_DESCRIPTOR_SPEC = (0xdf, 0, 0x1485e0, 0x13b640, 0xd2be0, 0xdb3b0)
TURN21_DESCRIPTOR_SOURCES = (
    ('work/host-extensions/xp2-game-history-static/turn21-cf9c73f1-source.json',
     '9cfbfd5eece30232cc045fe1ac5b868f626af653fe6b703c01a267e37893c36b'),
    ('work/host-extensions/xp2-game-history-static/turn21-cf9c73f1-receiver.json',
     '7e802bc4bd3e19efe397ceb1e0e2a735e31f5736df7d950438272160c790212f'),
)
TURN26_DESCRIPTOR_KIND = 0xdb0807b6
TURN26_DESCRIPTOR_SOURCES = (
    ('work/host-extensions/xp2-game-history-static/turn26-db0807b6-source.json',
     'b1e18ed4cdc5248599b228b96e21ad54b5cf1c6e1fd4e82ceb1fd3da952d1e36'),
    ('work/host-extensions/xp2-game-history-static/turn26-db0807b6-receiver.json',
     'fac6a0dcf7f3f72009658c9c403d30eaaa14af73b14456ac4442efdae643d481'),
)
DESCRIPTOR_EVENTS = MappingProxyType({
    TURN21_DESCRIPTOR_KIND: (TURN21_DESCRIPTOR_SPEC, TURN21_DESCRIPTOR_SOURCES,
                             ('xp2:5fbaf0', 'xp2:2dd6a8', 'xp2:2dd752')),
    TURN26_DESCRIPTOR_KIND: ((0xe3, 0, 0x148800, 0x13bd70, 0xd2fa0, 0xdb590),
                             TURN26_DESCRIPTOR_SOURCES,
                             ('xp2:259bf1', 'xp2:259713', 'xp2:2de6fe')),
})
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
EMITTER_RVA = 0x5fc5a0
SCORE_ALTERNATE_EMITTER_RVA = 0x5fc4f0
SELECTOR_KEY = 0xA1E5A149
VALUE_KEY = 0xD6FCF3E4
SECOND_VALUE_KEY = 0xA1FBC372


def _rows(body):
    return [row for fragment in body.get('fragments', ()) for row in fragment['instructions']]


def _ordered_subsequence(actual, expected):
    cursor = iter(actual)
    return all(any(row == wanted for row in cursor) for wanted in expected)


def _check_body(body):
    fragments = body.get('fragments')
    if not fragments:
        raise ValueError('XP2 event source body has no retained instructions')
    raw_parts = []
    for fragment in fragments:
        raw = bytes.fromhex(fragment['raw_hex'])
        rows = fragment['instructions']
        if (len(raw) != fragment['length']
                or hashlib.sha256(raw).hexdigest() != fragment['sha256']
                or ''.join(row['bytes'] for row in rows) != raw.hex()):
            raise ValueError('XP2 event source fragment bytes changed')
        cursor = int(fragment['start_rva'], 16)
        for row in rows:
            code = bytes.fromhex(row['bytes'])
            if int(row['rva'], 16) != cursor:
                raise ValueError('XP2 event source instruction boundary changed')
            cursor += len(code)
        raw_parts.append(raw)
    raw = b''.join(raw_parts)
    if len(raw) != body['bytes'] or hashlib.sha256(raw).hexdigest() != body['sha256']:
        raise ValueError('XP2 event source body digest changed')
    if body.get('all_conditional_targets_captured') is not True:
        raise ValueError('XP2 event source conditional successor is unclosed')
    return raw


@lru_cache(maxsize=1)
def source():
    p = _source(SOURCE)
    if (p.get('schema') != 'civ6-host.xp2-history-era-score.static.v1'
            or p['images']['xp2']['sha256'] != XP2_CORE_SHA256
            or p['images']['exe']['sha256'] != EXE_SHA256
            or p['event_ids'] != {'history_moment': hex(HISTORY_KIND),
                                  'era_changed': hex(ERA_KIND),
                                  'era_score_changed': hex(ERA_SCORE_KIND)}
            or p['validation']['native_execution'] is not False
            or p['validation']['process_memory_read'] is not False
            or p['validation']['all_source_bytes_from_exact_installed_images'] is not True
            or tuple(p['validation']['history_kind_function_rvas']) != ('0x97be0', '0x212c64')
            or tuple(p['validation']['era_kind_function_rvas']) != ('0x912f0', '0x1e7efa')
            or p['validation']['era_score_kind_function_count'] != 35
            or p['validation']['era_score_producer_function_count'] != 34
            or p['validation']['era_score_emitter_call_count'] != 40):
        raise ValueError('XP2 history/era/score source identity changed')
    for body in p['registrations'].values():
        _check_body(body)
    for family in ('history_moment', 'era_changed'):
        body = p['producers'][family]['body']
        _check_body(body)
        if len(p['producers'][family]['event_calls']) != 1:
            raise ValueError('XP2 history/era producer call count changed')
    score = p['producers']['era_score_changed']
    if len(score['functions']) != 34 or len(score['event_calls']) != 40:
        raise ValueError('XP2 score producer closure changed')
    for body in score['functions'].values():
        _check_body(body)
    _check_body(p['common_core_emitter']['body'])
    _check_body(p['score_alternate_emitter']['body'])
    common = _rows(p['common_core_emitter']['body'])
    alternate = _rows(p['score_alternate_emitter']['body'])
    if ('call qword ptr [rax + 0xa0]' not in {row['text'] for row in common}
            or 'call qword ptr [rax + 0xa0]' not in {row['text'] for row in alternate}):
        raise ValueError('XP2 scalar emitters no longer reach the shared A0 callback')
    # Score has two exact Core input shapes. The common emitter writes the
    # caller's EDX/R8D values under D6/A1FBC; its alternate emitter writes only
    # A1E5/D6. The latter's missing second scalar is handled by the already
    # pinned EXE normalizer, not by manufacturing an A1FBC input key.
    common_text = [row['text'] for row in common]
    alternate_text = [row['text'] for row in alternate]
    required_common = (
        'mov r8d, edi', 'mov edx, 0xd6fcf3e4', 'call 0x18099fee0',
        'mov r8d, ebx', 'mov edx, 0xa1fbc372', 'call 0x18099fee0',
        'mov ecx, dword ptr [rsp + 0x90]', 'call 0x18007c670',
    )
    required_alternate = (
        'mov r8d, dword ptr [rsp + 0x94]', 'mov edx, 0xa1e5a149',
        'call 0x1809a0000', 'mov r8d, ebx', 'mov edx, 0xd6fcf3e4',
        'call 0x18099fee0', 'mov ecx, dword ptr [rsp + 0x90]',
        'call 0x18007c670',
    )
    if not _ordered_subsequence(common_text, required_common):
        raise ValueError('XP2 three-key score emitter field order changed')
    if not _ordered_subsequence(alternate_text, required_alternate):
        raise ValueError('XP2 alternate score emitter field order changed')
    alt_calls = [row for row in p['producers']['era_score_changed']['event_calls']
                 if row.get('target') == 'call 0x1805fc4f0']
    if (len(alt_calls) != 1 or alt_calls[0]['function_rva'] != '0x1e7195'
            or alt_calls[0]['call_rva'] != '0x1e71dd'
            or 'mov qword ptr [rsp + 0x20], 0x788b7534' not in
               {row['text'] for row in alt_calls[0]['instructions']}):
        raise ValueError('XP2 alternate score producer caller changed')
    # The callback map and scalar writer are the exact common EXE proof already
    # consumed by XP1; this does not import its XP1 producer as XP2 evidence.
    from . import game_history_event_profile as history
    from . import game_era_score_event_profile as score_source
    from .native.native_two_value_event_family import verify_missing_b_source_evidence
    history.verify_source()
    score_source.verify_source()
    verify_missing_b_source_evidence()
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    expected = {HISTORY_KIND: 0x147300, ERA_KIND: 0x147200, ERA_SCORE_KIND: 0x14b8d0}
    if any(EXE_EVENT_CALLBACKS.get(kind) != rva for kind, rva in expected.items()):
        raise ValueError('Common EXE event callback mapping changed')
    return p


@lru_cache(maxsize=1)
def turn21_source():
    from .game_era_score_event_profile import verify_source, _normalized, _verify_rip_targets
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS

    proof = _source(TURN21_SOURCE)
    receiver = _source(TURN21_RECEIVER)
    _, _, callback, writer, _, _ = TURN21_SPEC
    if (proof['core_sha256'] != XP2_CORE_SHA256 or proof['exe_sha256'] != EXE_SHA256
            or proof['kind'] != TURN21_KIND or EXE_EVENT_CALLBACKS.get(TURN21_KIND) != callback
            or (proof['exe_callback'], proof['writer_rva']) != (callback, hex(writer))
            or receiver['producer_proof_sha256'] != TURN21_SOURCE[1]
            or receiver['exe_sha256'] != EXE_SHA256
            or (receiver['record_type'], receiver['record_size'], receiver['handler_va'])
                != (0x10b, 96, '0x1400d4f30')):
        raise ValueError('XP2 turn-21 event source differs')
    old = verify_source()['functions']['exe']
    new = proof['exe_bodies']
    if (_normalized(new[hex(callback)], writer) != _normalized(old['0x14b8d0'], 0x120000)
            or _normalized(new[hex(writer)]) != _normalized(old['0x120000'])
            or not any(row['text'] == 'mov dword ptr [rbx + 4], 0x10b'
                       for row in new[hex(writer)]['instructions'])):
        raise ValueError('XP2 turn-21 scalar writer differs')
    _verify_rip_targets(new[hex(callback)], old['0x14b8d0'],
        hook_relocation=(('0x1412c9aa0',), ('0x1412c9ad0',)))
    _verify_rip_targets(new[hex(writer)], old['0x120000'])
    return proof, receiver


def turn21_receiver_row():
    _, receiver = turn21_source()
    handler = receiver['bodies']['0xd4f30']['instructions']
    return dict(event_name='Unknown', handler_va=receiver['handler_va'], record_sizes={96},
                handler_body_sha256=hashlib.sha256(
                    b''.join(bytes.fromhex(row['bytes']) for row in handler)).hexdigest(),
                source_sha256=TURN21_RECEIVER[1])


@lru_cache(maxsize=1)
def turn21_scalar_sources():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS

    primary, neighbors, adjacent = (_source(ref) for ref in TURN21_SCALAR_SOURCES)
    if (primary['images'] != {'xp2': XP2_CORE_SHA256, 'exe': EXE_SHA256}
            or neighbors['images'] != primary['images']
            or neighbors['source_sha256'] != TURN21_SCALAR_SOURCES[0][1]
            or adjacent['exe_sha256'] != EXE_SHA256):
        raise ValueError('XP2 turn-21 scalar image identity changed')
    exe = {**primary['bodies'], **neighbors['bodies'],
           **{f'exe:{rva[2:]}': body for rva, body in adjacent['bodies'].items()}}
    for kind, (record, _, callback, writer, setup, handler) in TURN21_SCALARS.items():
        callback_rows, writer_rows, setup_rows, handler_rows = (
            _rows(exe[f'exe:{rva:x}']) for rva in (callback, writer, setup, handler))
        if (EXE_EVENT_CALLBACKS.get(kind) != callback
                or not any(row['text'] == f'call {0x140000000 + writer:#x}' for row in callback_rows)
                or not any(row['text'] == f'mov dword ptr [rbx + 4], {record:#x}' for row in writer_rows)
                or not any(tuple(row.get('rip_targets', ())) == (hex(0x140000000 + handler),)
                           for row in setup_rows)
                or not any(row['text'] == 'call 0x1400dc0d0' for row in handler_rows)):
            raise ValueError('XP2 turn-21 scalar callback or receiver differs')
    return primary, neighbors, adjacent


def turn21_scalar_receiver_row(record):
    primary, _, adjacent = turn21_scalar_sources()
    handler = {spec[0]: spec[-1] for spec in TURN21_SCALARS.values()}[record]
    body = (primary['bodies'][f'exe:{handler:x}'] if record == 0xe2
            else adjacent['bodies'][hex(handler)])
    proof = TURN21_SCALAR_SOURCES[0 if record == 0xe2 else 2][1]
    label = 'Unknown' if record == 0xe2 else 'GameCoreEvent::GovernorAppointed'
    return dict(event_name=label, handler_va=hex(0x140000000 + handler),
                record_sizes={96}, source_sha256=proof, handler_body_sha256=hashlib.sha256(
                    b''.join(bytes.fromhex(row['bytes']) for row in _rows(body))).hexdigest())


def turn21_scalar_core_fragments():
    primary, neighbors, _ = turn21_scalar_sources()
    for key in ('xp2:2df433', 'xp2:5fc680', 'xp2:2dd12a', 'xp2:5fc5a0'):
        body = (primary['bodies'] if key in primary['bodies'] else neighbors['bodies'])[key]
        for fragment in body['fragments']:
            yield (int(fragment['start_va'], 16) - 0x180000000,
                   b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions']))


@lru_cache(maxsize=len(DESCRIPTOR_EVENTS))
def descriptor_sources(kind):
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS

    spec, refs, _ = DESCRIPTOR_EVENTS[kind]
    producer, receiver = (_source(ref) for ref in refs)
    record, _, callback, writer, setup, handler = spec
    if (producer['images'] != {'xp2': XP2_CORE_SHA256, 'exe': EXE_SHA256}
            or receiver['exe_sha256'] != EXE_SHA256
            or receiver['producer_sha256'] != refs[0][1]
            or EXE_EVENT_CALLBACKS.get(kind) != callback
            or (receiver['record_type'], receiver['record_size']) != (record, 112)):
        raise ValueError('XP2 descriptor source identity changed')
    callback_rows = {row['text'] for row in _rows(producer['bodies'][f'exe:{callback:x}'])}
    writer_rows = {row['text'] for row in _rows(receiver['bodies'][hex(writer)])}
    setup_rows = _rows(receiver['bodies'][hex(setup)])
    handler_rows = _rows(receiver['bodies'][hex(handler)])
    if (not {f'call {0x140000000 + writer:#x}', 'movzx eax, word ptr [rdx + 0x18]',
             'movzx eax, word ptr [rdx + 0x1a]', 'mov eax, dword ptr [rdx + 0x1c]',
             'mov eax, dword ptr [rdx + 0x50]', 'mov eax, dword ptr [rdx + 0x54]'} <= callback_rows
            or not {'mov dword ptr [rbx], 0x70', f'mov dword ptr [rbx + 4], {record:#x}',
                    'movups xmmword ptr [rax], xmm0',
                    'movsd qword ptr [rax + 0x10], xmm1'} <= writer_rows
            or not any(tuple(row.get('rip_targets', ())) == (receiver['handler'],) for row in setup_rows)
            or not any(row['text'] == 'call 0x1400dc0d0' for row in handler_rows)):
        raise ValueError('XP2 descriptor writer or receiver differs')
    return producer, receiver


def descriptor_receiver_row(record):
    kind, = (kind for kind, (spec, _, _) in DESCRIPTOR_EVENTS.items() if spec[0] == record)
    spec, refs, _ = DESCRIPTOR_EVENTS[kind]
    _, receiver = descriptor_sources(kind)
    handler = receiver['bodies'][hex(spec[-1])]
    return dict(event_name='Unknown', handler_va=receiver['handler'], record_sizes={112},
                source_sha256=refs[1][1], handler_body_sha256=hashlib.sha256(
                    b''.join(bytes.fromhex(row['bytes']) for row in _rows(handler))).hexdigest())


def descriptor_core_fragments():
    for kind, (_, _, keys) in DESCRIPTOR_EVENTS.items():
        producer, _ = descriptor_sources(kind)
        for key in keys:
            for fragment in producer['bodies'][key]['fragments']:
                yield (int(fragment['start_va'], 16) - 0x180000000,
                       b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions']))


def decode_score_fields(raw_fields):
    """Normalize only the two source-proven XP2 PlayerEraScoreChanged shapes.

    The two-key form is admitted only after the shared EXE missing-second
    normalizer proof: it initializes the absent A1FBC DWORD to zero before
    reading the normalized +0x50/+0x54 pair. No raw A1FBC field is invented.
    """
    source()
    from .game_era_score_event_profile import verify_source as verify_score_source
    from .native.native_two_value_event_family import verify_missing_b_source_evidence
    verify_score_source()
    verify_missing_b_source_evidence()
    from .native.native_scalar_event_encoder import _read_u32_variant
    if type(raw_fields) is not dict:
        raise ValueError('XP2 era-score Core arguments must be an exact field map')
    keys = set(raw_fields)
    if keys not in ({SELECTOR_KEY, VALUE_KEY},
                    {SELECTOR_KEY, VALUE_KEY, SECOND_VALUE_KEY}):
        raise ValueError('XP2 era-score keys must match a retained emitter shape')
    selector = _read_u32_variant(raw_fields[SELECTOR_KEY], 3, 'selector')
    value_a = _read_u32_variant(raw_fields[VALUE_KEY], 2, 'value A')
    value_b = (_read_u32_variant(raw_fields[SECOND_VALUE_KEY], 2, 'value B')
               if SECOND_VALUE_KEY in raw_fields else 0)
    if selector != 0:
        raise ValueError('XP2 era-score requires the common selector-zero normalizer route')
    return selector, value_a, value_b


AGE_SOURCE = ('work/host-extensions/xp2-game-history-static/player-age-source.json',
              '15a0d40b82fa296b8e6e18ffe5530903b5bcbd152a630495245035716eed748a')
AGE_EVENTS = MappingProxyType({0xa7e78c7a: (0x108, 6), 0x2c333ac8: (0x107, 4)})


@lru_cache(maxsize=1)
def age_source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS

    proof = _source(AGE_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-player-age-notifications.static.v1'
            or proof['core_sha256'] != XP2_CORE_SHA256 or proof['exe_sha256'] != EXE_SHA256
            or proof['native_execution'] is not False
            or set(proof['events']) != {hex(kind) for kind in AGE_EVENTS}):
        raise ValueError('XP2 age notification source changed')
    for kind, (record, flag) in AGE_EVENTS.items():
        event = proof['events'][hex(kind)]
        if (event['record_type'], event['metadata_flag'], event['record_size'],
                event['callback_rva'], event['producer_token_hook']) != (
                    record, flag, 96, EXE_EVENT_CALLBACKS[kind], False):
            raise ValueError('XP2 age notification writer changed')
    return proof


def age_receiver_rows():
    return {
        event['record_type']: dict(
            record_sizes={96}, event_name=event['event_name'],
            handler_va=hex(0x140000000 + event['receiver_rva']),
            handler_body_sha256=event['receiver_sha256'], source_sha256=AGE_SOURCE[1])
        for event in age_source()['events'].values()
    }


def age_core_fragments():
    proof = age_source()
    for key in ('core_emitter', 'core_caller'):
        body = proof[key]
        raw = bytes.fromhex(body['raw_hex'])
        if len(raw) != body['size'] or hashlib.sha256(raw).hexdigest() != body['sha256']:
            raise ValueError('XP2 age notification producer evidence changed')
        yield body['rva'], raw


def source_dependencies(*, core_sha256=XP2_CORE_SHA256):
    if core_sha256 != XP2_CORE_SHA256:
        if core_sha256 == XP1_CORE_SHA256:
            return {}
        raise ValueError('Unknown history event source engine')
    from .a0_family_source import _path, verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p = source()
    turn21_source()
    age_source()
    primary, _, _ = turn21_scalar_sources()
    for kind in DESCRIPTOR_EVENTS:
        descriptor_sources(kind)
    refs = [dict(path=path, sha256=digest)
            for path, digest in (SOURCE, AGE_SOURCE, TURN21_SOURCE, TURN21_RECEIVER, *TURN21_SCALAR_SOURCES,
                                 *TURN21_DESCRIPTOR_SOURCES, *TURN26_DESCRIPTOR_SOURCES)]
    from .native.native_city_descriptor_events import NORMALIZER_PROOF_SHA256
    refs.append(dict(path=f'evidence/native-event-99e85ec6/{NORMALIZER_PROOF_SHA256}.json',
                     sha256=NORMALIZER_PROOF_SHA256))
    normalizer = 'evidence/native-scalar-event-callback-candidates.json'
    refs.append(dict(path=normalizer, sha256=primary['references'][normalizer.replace('/', '\\')]))
    refs.extend((p['extractor'], p['capture_helper']))
    pins = {}
    for ref in refs:
        path = str(_path(ref['path']).resolve())
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('XP2 history source dependency identity conflict')
        pins[path] = ref['sha256']
    # Pin the existing shared EXE callback and writer proofs separately from
    # XP2 Core emitter evidence.
    from .game_history_event_profile import source_dependencies as history_dependencies
    from .game_era_score_event_profile import source_dependencies as score_dependencies
    from .native.native_two_value_event_family import (
        MISSING_B_PROOF_SHA256, _MISSING_B_PROOF_PATH)
    for group in (history_dependencies(), score_dependencies(),
                  {str(_MISSING_B_PROOF_PATH.resolve()): MISSING_B_PROOF_SHA256}):
        for path, sha in group.items():
            if path in pins and pins[path] != sha:
                raise ValueError('XP2 history source dependency identity conflict')
            pins[path] = sha
    verify_pinned_files(pins)
    return pins


def event_profile(*, core_sha256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 history event profile requires the exact XP2 Core')
    p = source()
    source_dependencies()
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    from . import game_history_event_profile as history
    from . import game_era_score_event_profile as score
    mapping = {
        HISTORY_KIND: frozenset((0x105,)),
        ERA_KIND: frozenset((0x104,)),
        ERA_SCORE_KIND: frozenset((0x10a,)),
        TURN21_KIND: frozenset((0x10b,)),
    }
    sizes = {0x105: 96, 0x104: 96, 0x10a: 96, 0x10b: 96}
    common_rows = history.receiver_rows()
    common_rows.update(age_receiver_rows())
    for kind, (record, _) in AGE_EVENTS.items():
        mapping[kind] = frozenset((record,))
        sizes[record] = 96
    common_rows[0x10a] = score.receiver_row()
    common_rows[0x10b] = turn21_receiver_row()
    # GovernorAppointed (0xde) is already routed by the shared A0 profile.
    mapping[0x8c6b2399] = frozenset((0xe2,))
    sizes[0xe2] = 96
    common_rows[0xe2] = turn21_scalar_receiver_row(0xe2)
    for kind, (spec, _, _) in DESCRIPTOR_EVENTS.items():
        record = spec[0]
        mapping[kind] = frozenset((record,))
        sizes[record] = 112
        common_rows[record] = descriptor_receiver_row(record)
    for record, size in sizes.items():
        row = resolve_empty_receiver_row(record)
        expected = common_rows[record]
        if (row['record_sizes'] != {size}
                or any(row[k] != expected[k] for k in ('event_name', 'handler_va', 'handler_body_sha256'))):
            raise ValueError('XP2 history/era shared EXE receiver differs')
    profile = A0FamilyProfile(MappingProxyType(mapping), MappingProxyType(sizes), SOURCE[1])
    return profile


def _bodies(p):
    result = list(p['registrations'].values())
    result.extend(p['producers'][name]['body'] for name in ('history_moment', 'era_changed'))
    result.extend(p['producers']['era_score_changed']['functions'].values())
    result.extend((p['common_core_emitter']['body'], p['score_alternate_emitter']['body']))
    return result


def bind_owner(backend, core, read):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 history event owner mismatch')
    p = source()
    for body in _bodies(p):
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            address = core._handle + int(fragment['start_rva'], 16)
            if read(address, len(raw)) != raw:
                raise ValueError('XP2 history producer live bytes changed')
    producer = turn21_source()[0]['producer']
    raw = bytes.fromhex(producer['raw_hex'])
    if read(core._handle + int(producer['start_rva'], 16), len(raw)) != raw:
        raise ValueError('XP2 turn-21 producer live bytes changed')
    for rva, raw in turn21_scalar_core_fragments():
        if read(core._handle + rva, len(raw)) != raw:
            raise ValueError('XP2 turn-21 scalar producer live bytes changed')
    for rva, raw in descriptor_core_fragments():
        if read(core._handle + rva, len(raw)) != raw:
            raise ValueError('XP2 descriptor producer live bytes changed')
    for rva, raw in age_core_fragments():
        if read(core._handle + rva, len(raw)) != raw:
            raise ValueError('XP2 age notification producer live bytes changed')
    return SOURCE[1]

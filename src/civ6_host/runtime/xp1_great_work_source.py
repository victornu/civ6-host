"""Both source-bound GreatWorkCreated producers on registered Rise and Fall."""

import hashlib
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity
from .native import native_event_great_work as codec
from .xp2_great_work import SOURCE as RECEIVER_SOURCE, dispatch_record


SOURCE = (
    'evidence/host-xp1-installed-great-work-created-source.json',
    'f8448002b5b11616f04f0cc01a485677cbd5b315d0590ca8bb1b78b4944fd7fe',
)
UNIT_PRODUCER_SOURCE = (
    'work/x1trade/great-work-unit-producer-stage/1d0e865664cae5321ae86f8a42044705f15623da1fa50fd4c5e9327ad846057f.json',
    '1d0e865664cae5321ae86f8a42044705f15623da1fa50fd4c5e9327ad846057f',
)
_ACTIVATION_SOURCE = (
    'work/x1trade/great-person-activation-stage/9d56cd2ca813c46fe43e39e3e94526c31e4c4116e0be6e3089dff6e8d9edc045.json',
    '9d56cd2ca813c46fe43e39e3e94526c31e4c4116e0be6e3089dff6e8d9edc045',
)
_UNIT_SPANS = ((0x177fa0, 97), (0x178001, 34), (0x178023, 355),
               (0x178186, 5), (0x17818b, 13))
SPANS = {
    'producer': (0x295540, 0xE5),
    'map_builder': (0x518630, 0x180),
    'caller': (0x76A3B6, 0x6B),
    'signed_field_writer': (0x845E90, 0x115),
    'unsigned_field_writer': (0x845FB0, 0x115),
}


def source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('GreatWorkCreated requires the registered Rise and Fall image')
    proof = _source(SOURCE)
    contract = proof['contract']
    receiver = proof['shared_receiver']
    if (proof['schema'] != 'civ6-host.xp1-installed-great-work-created.source.v1'
            or proof['engine'] != identity(execution_image)
            or (receiver['path'], receiver['sha256']) != RECEIVER_SOURCE
            or proof['matching_exe_spans'] != 43
            or (contract['kind'], contract['record_type'], contract['record_size']) !=
               (codec.EVENT_KIND, codec.RECORD_TYPE, codec.RECORD_SIZE)
            or (contract['selector'], contract['descriptor_type'], contract['descriptor_id']) !=
               (0, 1, 0xffffffff)
            or contract['internal_gamecore_dispatch_before_host'] is not True
            or contract['producer_discards_host_result'] is not True
            or contract['empty_receiver_reused'] is not True
            or contract['gameplay_mutation_reimplemented'] is not False
            or {name: (row['rva'], row['size']) for name, row in proof['spans'].items()} != SPANS):
        raise ValueError('Rise and Fall GreatWorkCreated source contract differs')
    shared = _source(RECEIVER_SOURCE)
    if (proof['exe'] != shared['images']['exe']
            or shared['receiver']['event_name'] != 'GameCoreEvent::GreatWorkCreated'):
        raise ValueError('GreatWorkCreated shared receiver identity differs')
    return proof


def unit_source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('GreatWorkCreated unit producer requires the registered Rise and Fall image')
    proof = _source(UNIT_PRODUCER_SOURCE)
    contract = proof['contract']
    parents = proof['parents']
    producer = proof['producer']
    if (proof['schema'] != 'civ6-host.xp1-great-work-unit-producer.source.v1'
            or proof['engine'] != identity(execution_image)
            or {name:(row['path'], row['sha256']) for name,row in parents.items()} !=
               {'legacy':SOURCE, 'activation':_ACTIVATION_SOURCE, 'shared_receiver':RECEIVER_SOURCE}
            or (contract['kind'], contract['record_type'], contract['record_size'],
                contract['selector'], contract['descriptor_bytes'], contract['descriptor_owner_bits'],
                contract['descriptor_type'], contract['descriptor_id_bits'],
                contract['descriptor_id_min'], contract['descriptor_id_max'], contract['legacy_descriptor_id']) !=
               (codec.EVENT_KIND, codec.RECORD_TYPE, codec.RECORD_SIZE, 0, 8, 16, 1, 32, 0, 0xffffffff, 0xffffffff)
            or any(contract[key] is not True for key in (
                'legacy_producer_preserved', 'shared_codec_unchanged', 'internal_gamecore_dispatch_before_host',
                'producer_discards_host_result', 'empty_receiver_required', 'native_plot_retained_through_enqueue'))
            or contract['gameplay_mutation_reimplemented'] is not False
            or (producer['entry_rva'], producer['complete_end_rva'], producer['bytes']) != (0x177fa0, 0x178198, 504)
            or tuple((int(row['rva'],16),row['length']) for row in producer['fragments']) != _UNIT_SPANS):
        raise ValueError('Rise and Fall GreatWorkCreated unit source contract differs')
    legacy = source(execution_image)
    shared = _source(RECEIVER_SOURCE)
    activation = _source(_ACTIVATION_SOURCE)
    if (proof['exe'] != legacy['exe'] or proof['exe'] != shared['images']['exe']
            or producer['fragments'] != activation['code_spans']['create_great_work']['fragments']
            or any(proof['shared_builder'][key] != value for key,value in legacy['spans']['map_builder'].items())
            or set(proof['consumer_full_bodies_reused']) != {
                'EXE A0 normalizer', 'GreatWorkCreated callback', 'GreatWorkCreated deferred writer',
                'GreatWorkCreated receiver handler', 'EXE shared subscriber dispatch',
                'EXE deferred record dispatch without observer'}):
        raise ValueError('GreatWorkCreated unit producer and shared consumer joins differ')
    for name,row in proof['consumer_full_bodies_reused'].items():
        if any(row[key] != value for key,value in shared['bodies'][name].items()):
            raise ValueError('GreatWorkCreated full shared consumer body differs')
    for row in producer['fragments']:
        raw = bytes.fromhex(row['raw_hex'])
        if (len(raw) != row['length'] or int(row['end_rva'],16)-int(row['rva'],16) != len(raw)
                or hashlib.sha256(raw).hexdigest() != row['sha256']):
            raise ValueError('GreatWorkCreated unit source bytes differ')
    return proof


def source_dependencies(execution_image):
    proof = source(execution_image)
    unit_source(execution_image)
    pins = {
        str(_path(SOURCE[0]).resolve()): SOURCE[1],
        str(_path(UNIT_PRODUCER_SOURCE[0]).resolve()): UNIT_PRODUCER_SOURCE[1],
        str(_path(_ACTIVATION_SOURCE[0]).resolve()): _ACTIVATION_SOURCE[1],
        str(_path(RECEIVER_SOURCE[0]).resolve()): RECEIVER_SOURCE[1],
        str(codec.PROOF_PATH.resolve()): codec.PROOF_SHA256,
        str(Path(execution_image.path).resolve()): execution_image.image_sha256,
        str(Path(proof['exe']['path']).resolve()): proof['exe']['sha256'],
    }
    verify_pinned_files(pins)
    return pins


def verify_live(core, read):
    proof = source(getattr(core, '_civ6_host_execution_image', None))
    for row in proof['spans'].values():
        raw = read(core._handle + row['rva'], row['size'])
        if len(raw) != row['size'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Rise and Fall GreatWorkCreated live producer differs')
    for row in unit_source(core._civ6_host_execution_image)['producer']['fragments']:
        if read(core._handle + int(row['rva'],16), row['length']) != bytes.fromhex(row['raw_hex']):
            raise ValueError('Rise and Fall GreatWorkCreated live unit producer differs')


def dispatch(owner, raw_fields):
    # The complete unit producer and shared builder/consumer copy the ID DWORD
    # without narrowing. The codec still enforces the eight-byte descriptor,
    # selector0 and type1; legacyFFFFFFFF remains in the same binary domain.
    return dispatch_record(owner, raw_fields, core_sha256=XP1_CORE_SHA256,
                           verify_producer=verify_live, proof_sha256=UNIT_PRODUCER_SOURCE[1])

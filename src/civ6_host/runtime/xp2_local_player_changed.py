"""Installed Gathering Storm sources for the existing LocalPlayerChanged codec."""

from functools import lru_cache
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .a0_policy_unlock_current import _require_image
from .configuration_profiles import _source
from .xp2_feature_reveal_source import _read_exact
from .xp2_bbg_inputs import SCRIPT_SHA256 as BBG_SCRIPT
from .xp2_bundle_inputs import SCRIPT_SHA256 as STOCK_SCRIPT

SOURCE = (
    'evidence/host-xp2-local-player-changed-source.json',
    '10a07277fa1aa9c603289e67677b2dfb9539ba7839f221c407b4c11cef49be30',
)
KIND = 0xC0372152
RECORD = (274, 96, 6)
_SCRIPT_SEQUENCES = ((STOCK_SCRIPT,), (STOCK_SCRIPT, BBG_SCRIPT))
_LIVE_SPANS = ('automatic_update', 'control_transfer_producer', 'tagged_builder')


def supports_script_hashes(hashes):
    """Only the already authenticated selection may qualify the receiver."""
    return hashes is not None and tuple(hashes.values()) in _SCRIPT_SEQUENCES


@lru_cache(maxsize=1)
def source():
    from .native.native_unary_event_family import source_for

    proof = _source(SOURCE)
    wire = proof['wire']
    reference = source_for(KIND)
    if (proof['schema'] != 'civ6-host.xp2-local-player-changed-source.static.v1'
            or tuple(tuple(row) for row in
                     proof['gameplay_scripts']['recognized_hash_sequences']) != _SCRIPT_SEQUENCES
            or proof['gameplay_scripts']['matching_literals']
            or (wire['record_type'], wire['record_size'], wire['metadata_flag']) != RECORD
            or wire['kind'] != hex(KIND) or wire['current_callback'] != '0x148d90'
            or reference['record_type'] != RECORD[0] or reference['callback_flag'] != RECORD[2]
            or int(reference['callback_va'], 16) - 0x140000000 != int(wire['legacy_callback'], 16)
            or proof['transport']['reused_unary_record'] is not True):
        raise ValueError('LocalPlayerChanged source contract differs')
    return proof


def source_dependencies():
    proof = source()
    parent = proof['shared_receiver_source']
    reference = proof['transport']['reference_source']
    pins = {
        str(_path(SOURCE[0]).resolve()): SOURCE[1],
        str(_path(parent['path']).resolve()): parent['sha256'],
        str(_path(reference['path']).resolve()): reference['sha256'],
        **{str(Path(row['path']).resolve()): row['sha256'] for row in proof['images'].values()},
    }
    # The captured script bindings check the exact selected scripts separately.
    # A stock session does not depend on having BBG installed.
    verify_pinned_files(pins)
    return pins


def core_fragments():
    for label in _LIVE_SPANS:
        row = source()['spans'][label]
        raw = bytes.fromhex(row['raw_hex'])
        if row['image'] != 'core' or row['verify_loaded_core'] is not True or len(raw) != row['bytes']:
            raise ValueError('LocalPlayerChanged live source span differs')
        yield int(row['rva'], 16), raw


def _verify_image(image):
    _require_image(image)
    selected = source()['images']['core']
    if (image.image_sha256 != selected['sha256']
            or Path(image.path).resolve() != Path(selected['path']).resolve()):
        raise ValueError('LocalPlayerChanged image differs')


def verify_live(image, base, read):
    _verify_image(image)
    for rva, raw in core_fragments():
        if _read_exact(read, base + rva, len(raw)) != raw:
            raise ValueError('LocalPlayerChanged live Core source differs')


def receiver_row(image):
    _verify_image(image)
    proof = source()
    handler = proof['spans']['receiver_handler']
    return dict(event_name=proof['wire']['name'], record_sizes={RECORD[1]},
                handler_va=hex(0x140000000 + int(handler['rva'], 16)),
                handler_body_sha256=handler['sha256'], source_sha256=SOURCE[1])


def dispatch_scoped(owner, fields):
    """Enqueue with the existing unary codec while notification counters are open."""
    from .native.native_unary_event_family import encode_core_fields

    scope = owner._active_notification_scope
    if owner.active_kind != KIND or scope is None or scope[-1] != RECORD:
        raise ValueError('LocalPlayerChanged requires its source-qualified A0 scope')
    _verify_image(getattr(owner.deferred.core, '_civ6_host_execution_image', None))
    record = encode_core_fields(KIND, owner._sequence + 1, fields,
                                optional_callback_present=owner.per_thread_hook_present,
                                queue_hook_present=owner.writer_metadata_callback_present)
    owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued', dispatch_kind=hex(KIND),
               queue_type=hex(RECORD[0]), event_name='GameCoreEvent::LocalPlayerChanged',
               record_hex=record.hex(), pending_count=len(owner.pending), callback_flag=RECORD[2],
               consumer_validated=False, source_sha256=SOURCE[1], eligible_for_training=False,
               native_dispatch_return=0)
    return 0

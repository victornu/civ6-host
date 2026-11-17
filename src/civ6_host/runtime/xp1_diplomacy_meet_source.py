"""Installed expansion notification proofs for native diplomacy contacts."""

from hashlib import sha256
from pathlib import Path
from types import MappingProxyType

from .configuration_profiles import _source
from .execution_images import _PROFILE, _XP1_PROFILE, identity
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp1-diplomacy-meet-counter-scope-source.json',
          'a77183a2027279b392e62081c22f1cff030e6389c6bbcdc9079feea0f6879e84')
XP2_SOURCE = ('work/x1trade/xp2-contact-source-stage/source.json',
              'ec67acfa841d4cc92d120c95b24bcf969a21bb738915a3319cf736696e71d68b')
RECORDS = MappingProxyType({
    0x133d411c: (129, 96, 4),
    0x08b3bf96: (130, 96, 4),
    0x892f171c: (131, 96, 4),
})


def source_reference(execution_image):
    if execution_image is _XP1_PROFILE:
        return SOURCE
    if execution_image is _PROFILE:
        return XP2_SOURCE
    return None


def _xp2_captures():
    from . import xp2_bbg_inputs, xp2_bundle_inputs

    return (xp2_bundle_inputs.REFERENCE, xp2_bbg_inputs.REFERENCE)


def scope_supported(execution_image, capture_reference):
    return (execution_image is _XP1_PROFILE
            or execution_image is _PROFILE and capture_reference in _xp2_captures())


def source(execution_image):
    reference = source_reference(execution_image)
    if reference is None:
        return None
    proof = _source(reference)
    engine = 'xp1' if execution_image is _XP1_PROFILE else 'xp2'
    if (proof['schema'] != f'civ6-host.{engine}-diplomacy-meet-counter-scope.source.v1'
            or proof['image'] != identity(execution_image)
            or {int(key, 16): (row['record'], row['size'], row['flag'])
                for key, row in proof['records'].items()} != RECORDS
            or proof['contract'] != dict(reuses_codec=True, empty_receiver_required=True,
                gameplay_dispatch_already_native=True, modifies_notification_counter=False,
                modifies_metadata_counter=False)):
        raise ValueError('Installed diplomacy contact source differs')
    if execution_image is _PROFILE:
        predecessor = source(_XP1_PROFILE)
        captures = tuple((row['path'], row['sha256']) for row in proof['admitted_captures'])
        if (captures != _xp2_captures() or proof['executable'] != predecessor['executable']
                or proof['abi']['native_core_dispatch_before_host'] is not True
                or proof['abi']['host_return_unused_by_producer_call_sites'] is not True
                or proof['abi']['host_slot'] != 0xa0
                or proof['capture_scope']['owned_receiver_must_be_empty'] is not True
                or any({key: item for key, item in row.items() if key != 'producer'}
                       != {key: item for key, item in predecessor['records'][kind].items() if key != 'producer'}
                       for kind, row in proof['records'].items())):
            raise ValueError('Gathering Storm diplomacy contact differs from the shared receiver and capture scope')
    return proof


def source_dependencies(execution_image):
    proof = source(execution_image)
    if proof is None:
        return {}
    reference_path, expected = source_reference(execution_image)
    path = resolve_path(resource_root() / reference_path)
    result = {str(path.resolve()): expected}
    for row in (*proof['parents'], proof['executable']):
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        result[str(path.resolve())] = row['sha256']
    return result


def verify_live(execution_image, base, read):
    proof = source(execution_image)
    if proof is not None:
        spans = [proof['common_producer'], *(row['producer'] for row in proof['records'].values()),
                 *proof.get('supplemental_live_core_spans', {}).values()]
        for span in spans:
            raw = read(base + span['rva'], span['bytes'])
            if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
                raise ValueError(f"Live diplomacy contact producer differs at {span['rva']:#x}")


def receiver_row(record_type, *, execution_image=_XP1_PROFILE):
    proof = source(execution_image)
    if proof is None:
        raise ValueError('Diplomacy contact receiver requires an exact installed image')
    row, = (row for row in proof['records'].values() if row['record'] == record_type)
    receiver = row['receiver']
    return dict(event_name=row['label'], handler_va=hex(0x140000000 + receiver['rva']),
                record_sizes={row['size']}, handler_body_sha256=receiver['sha256'],
                source_sha256=source_reference(execution_image)[1])

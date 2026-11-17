"""Installed Rise and Fall source for the shared turn-history FIFO record."""

from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE, identity


SOURCE = ('evidence/host-xp1-installed-turn21-scalar-event-source.json',
          '1ced51a584140b95c6288e12924377ddf5b7d4156626593822812c710dc319c7')
KIND = 0xa47d34e3
RECORD = 0x10b
SIZE = 96
FLAG = 6


def source(image=_XP1_PROFILE):
    proof = _source(SOURCE)
    if (image is not _XP1_PROFILE or proof['image'] != identity(image)
            or proof['schema'] != 'civ6-host.xp1-turn21-scalar-event.source.v1'
            or (proof['kind'], proof['record'], proof['size'], proof['metadata_flag'])
                != (KIND, RECORD, SIZE, FLAG)
            or proof['selector'] != 0 or proof['variant_keys'] != (0xa1e5a149, 0xd6fcf3e4, 0xa1fbc372)
            or proof['receiver_label'] != 'Unknown'):
        raise ValueError('Rise and Fall turn-history notification source differs')
    return proof


def receiver_row():
    proof = source()
    receiver = proof['exe']['receiver']
    return dict(event_name=proof['receiver_label'], handler_va=hex(0x140000000 + receiver['rva']),
                record_sizes={SIZE}, handler_body_sha256=receiver['sha256'], source_sha256=SOURCE[1])

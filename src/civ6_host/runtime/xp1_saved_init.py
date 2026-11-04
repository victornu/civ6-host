"""Exact captured database binding for the existing XP1 Init adapters.

Historical diagnostic fixture proofs retain their original identities. These
checks select different inputs only for the owned saved-Load candidate bundle.
They neither execute Init nor admit a public expansion session.
"""
from .xp1_saved_load import REFERENCE, validate_candidate_inputs


DATABASE_PINS = {
    'configuration': dict(sha256='38242bafe65932e61c9c5307adbc97606bbecce8f738ed14fec30e020a39eaad', size_bytes=765952),
    'gameplay': dict(sha256='9965886887e836a8d714a4eef38d812bece266286bc2608b38c1ad14c31b76a8', size_bytes=6901760),
    'localization': dict(sha256='0d805e91c70171c484a619687ed2a215d09cfa12a34b07f7dd51e5aff2c94a66', size_bytes=81342464),
}


def database_input_binding(bundle, host, configuration_path, gameplay_path, private_root):
    from .captured_init_inputs import database_input_binding as bind
    return bind(bundle, host, configuration_path, gameplay_path, private_root,
        family='xp1-lan', reference=REFERENCE, database_pins=DATABASE_PINS,
        validate_inputs=validate_candidate_inputs)


def validate_init_receipt_binding(bundle, host, receipt):
    from .captured_init_inputs import validate_init_receipt_binding as validate
    return validate(bundle, host, receipt, family='xp1-lan', reference=REFERENCE,
        database_pins=DATABASE_PINS, validate_inputs=validate_candidate_inputs)

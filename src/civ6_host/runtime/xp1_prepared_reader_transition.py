"""One retained XP1 prepared-package reader transition.

This is not raw capture revalidation or a general reader-version allowance.
It binds the previously prepared XP1 LAN package, its exact official origin,
the historical component comparison, and the six reviewed reader-source pairs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .paths import resource_root

PRODUCER_IDENTITY_SHA256 = '5317ec0a1c1b4054173d58cb10e95b3437d427e6dfd2eded8092425a6937e01a'
PACKAGE_RELATIVE = 'work/host-prepared-captures/xp1-lan-20261030/manifest.json'
PACKAGE_SHA256 = 'be65f4900a0e32edcee471ebfc0f697d299a86a839c5798c3d1a324a031c0665'
ORIGIN_RELATIVE = 'work/official-capture/xp1-lan-20261030/manifest.json'
ORIGIN_SHA256 = '475f74f15dc4921b3281c9eece768afadbff924c6384f0507d3ea92413c48fcf'
COMPONENT_REPORT_SHA256 = '43c4fc64ad016e72d071d1fe1fdafeea4d7c68c5c7ee64c42a18b7133f4c9411'
BRANCH_REPORT_SHA256 = 'bcf4492cf759a5db07ead80e9d1f4e8019127b9f7b7c3ecccf4f08bb707956d4'

# These are precisely the source pairs from the retained branch comparison.
SOURCE_PAIRS = {
    'runtime/native/native_official_bundle.py': (
        '0f9ad559341707cebd6ce0e9a76f27ccdc2dfecee6cc65ab2f385eaba93ce51b',
        '713204d0a967b415a5bdd5d809c3045b945ef33ae5963469fd2fa5b62bffd83f'),
    'runtime/capture_package.py': (
        '5ff7311faa83fc23aa71f17b8fe1a0fb16636da21d21395e49a11fb1720787b1',
        '46c9af96b9aa703b79d3b33fe43564cc2e4ce88a4b528d754e43b1e580b0e460'),
    'runtime/native/database_capture_bundle993.py': (
        '8a1db3ceed89f8b91d194091298df146a0944e8369af36959e6f231af48375d6',
        'dfd94cfe6e6255e39e1c606582fcad7c126ecd0b9697461e9d8aa5120d24c9a7'),
    'runtime/native/native_gameplay_source_capture.py': (
        'd429126a266e6b9c61c9e5a720d8a5f0900e6a74e5983f5de00bb92808a0f209',
        '0385528e5992a6df3c5e045c5c17d014df998bcf2b6a34c19185d1312f959ae4'),
    'runtime/native/native_localization_logical_export.py': (
        'be40453259876b4b6073b9efd16806272047734537afddecdb03303442bc9b21',
        '27542b6c688d6571457a7fde76ad22f4edcfd40ad0c8d2e2bcae9de817e87c52'),
    'runtime/workers/capture_phase1_bundle994.py': (
        '9cbc6b4158259cb5ef944ffad13fafe76edc7019db1cb94550e322a8d15d1b36',
        'c0c71bf871273d00b1e3745eece54e69f93e5741d4306192f784bca9fc367cc0'),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity_sha(identity) -> str:
    return _sha(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def _read_pinned_json(path: Path, expected_sha: str):
    raw = path.read_bytes()
    if _sha(raw) != expected_sha:
        raise ValueError('XP1 prepared-reader evidence changed')
    return json.loads(raw)


def _validate_evidence(host_root: Path, manifest, producer, consumer, validator_digests):
    review = host_root / 'work/xp2-ui-integration/reader-review'
    components = _read_pinned_json(
        review / 'xp1-input-components-revalidation-v1.json', COMPONENT_REPORT_SHA256)
    branches = _read_pinned_json(
        review / 'xp1-selected-branch-equivalence-v1.json', BRANCH_REPORT_SHA256)

    if (components.get('status') != 'component-equality-confirmed_full-current-bundle-reader-incomplete'
            or components.get('identity', {}).get('producer_identity_sha256') != PRODUCER_IDENTITY_SHA256
            or components.get('identity', {}).get('producer_identity_substituted') is not False
            or components.get('identity', {}).get('input_profile') != 'xp1-lan'
            or components.get('identity', {}).get('native_session_qualified') is not False
            or components.get('identity', {}).get('prepared_manifest') != {
                'path': PACKAGE_RELATIVE, 'sha256': PACKAGE_SHA256}
            or components.get('identity', {}).get('origin_manifest') != {
                'path': ORIGIN_RELATIVE, 'sha256': ORIGIN_SHA256}
            or len(components.get('component_comparison', ())) != 6
            or any(row.get('byte_equal') is not True for row in components['component_comparison'])
            or components.get('full_current_reader_attempt', {}).get('status') != 'incomplete'):
        raise ValueError('XP1 component revalidation evidence is outside the accepted scope')

    subject = branches.get('subject', {})
    gates = branches.get('retained_code_evidence', {}).get('current_manifest_gates', {})
    localization = gates.get('localization_exports', {})
    active_db = gates.get('active_database_witnesses', {})
    if (branches.get('status') != 'narrow-xp1-branch-equivalence-demonstrated-static-and-by-retained-component-revalidation'
            or subject.get('profile') != 'xp1-lan'
            or subject.get('package_manifest_sha256') != PACKAGE_SHA256
            or subject.get('origin_manifest_sha256') != ORIGIN_SHA256
            or subject.get('producer_identity_sha256') != PRODUCER_IDENTITY_SHA256
            or gates.get('input_profile') != 'xp1-lan'
            or gates.get('response_file_predecessor') is not None
            or gates.get('selected_gameplay_paths') != []
            or gates.get('selected_script_records') != 0
            or gates.get('selected_script_files') != 0
            or localization.get('schema') != 'civ6rl.localization_logical_export.v1'
            or localization.get('row_files_present') is not False
            or localization.get('build_is_stream_build') is not False
            or localization.get('tables_schema') != 'civ6rl.database_capture_bundle993.v1'
            or active_db.get('schema') != 'civ6rl.database_capture_bundle993.v1'
            or branches.get('full_replay_status', '').find('incomplete') < 0):
        raise ValueError('XP1 selected legacy branches no longer match the retained proof')

    actual = _identity_sha(producer)
    if actual != PRODUCER_IDENTITY_SHA256:
        raise ValueError('XP1 prepared-reader producer identity changed')
    if producer.get('schema') != consumer.get('schema'):
        raise ValueError('XP1 prepared-reader identity schema changed')
    if producer.get('original_validator_sources') != consumer.get('original_validator_sources'):
        raise ValueError('XP1 original validators changed; raw revalidation required')

    psrc = producer.get('runtime_sources')
    csrc = consumer.get('runtime_sources')
    if type(psrc) is not dict or type(csrc) is not dict:
        raise ValueError('XP1 prepared-reader source identities are invalid')
    expected_validators = {
        'runtime/capture_package.py',
        'runtime/native/official_save.py',
        'runtime/native/official_configuration.py',
        'runtime/native/database_capture_bundle993.py',
        'runtime/native/native_gameplay_source_capture.py',
        'runtime/native/native_localization_logical_export.py',
        'runtime/native/native_localization.py',
        'runtime/native/native_source_cache.py',
        'runtime/native/native_checkpoint_provider.py',
        'runtime/native/native_game_configuration.py',
        'runtime/capture_profiles.py',
        'runtime/gameplay_active_profiles.py',
        'runtime/native/native_gameplay_empty.py',
        'runtime/native/native_official_bundle.py',
        'runtime/native/official_application_configuration.py',
        'runtime/workers/capture_phase1_bundle994.py',
        'runtime/xp1_bundle_inputs.py',
    }
    if set(validator_digests) != expected_validators:
        raise ValueError('XP1 reader validator set changed; raw revalidation required')
    if any(csrc.get(key) != digest for key, digest in validator_digests.items()):
        raise ValueError('XP1 current input validator changed')
    changed = {key for key in expected_validators if psrc.get(key) != csrc.get(key)}
    if changed != set(SOURCE_PAIRS):
        raise ValueError('XP1 prepared-reader changes exceed the six reviewed source pairs')
    for key, (old, current) in SOURCE_PAIRS.items():
        if psrc.get(key) != old or csrc.get(key) != current:
            raise ValueError('XP1 prepared-reader source pair changed: ' + key)


def admit_retained_package(*, producer, consumer, manifest, reference, validator_digests):
    """Return a receipt for this exact immutable package and reviewed branches."""
    if _identity_sha(producer) != PRODUCER_IDENTITY_SHA256:
        raise ValueError('XP1 prepared-reader producer identity changed')
    if type(reference) is not dict or set(reference) != {'path', 'sha256'}:
        raise ValueError('XP1 migration requires an exact prepared package reference')
    root = resource_root().resolve(strict=True)
    expected_path = (root / PACKAGE_RELATIVE).resolve(strict=True)
    try:
        actual_path = Path(reference['path']).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError('XP1 prepared package reference is invalid') from exc
    if actual_path != expected_path or reference.get('sha256') != PACKAGE_SHA256:
        raise ValueError('XP1 migration is limited to the retained prepared package')
    raw = actual_path.read_bytes()
    if _sha(raw) != PACKAGE_SHA256:
        raise ValueError('XP1 prepared package changed')
    stored = json.loads(raw)
    if stored != manifest:
        raise ValueError('XP1 prepared manifest differs from its pinned package')
    if (manifest.get('schema') != 'civ6-host.prepared-capture.v1'
            or manifest.get('input_profile') != 'xp1-lan'
            or manifest.get('origin') != {'path': ORIGIN_RELATIVE, 'sha256': ORIGIN_SHA256}
            or manifest.get('validation_identity') != producer):
        raise ValueError('XP1 prepared manifest scope or producer changed')
    origin_path = (root / ORIGIN_RELATIVE).resolve(strict=True)
    if _sha(origin_path.read_bytes()) != ORIGIN_SHA256:
        raise ValueError('XP1 official origin manifest changed')

    host_root = Path(__file__).resolve().parents[3]
    _validate_evidence(host_root, manifest, producer, consumer, validator_digests)
    return dict(
        transition='xp1_retained_prepared_package_legacy_reader_v1',
        producer_identity_sha256=PRODUCER_IDENTITY_SHA256,
        consumer_identity_sha256=_identity_sha(consumer),
        package=dict(path=str(actual_path), sha256=PACKAGE_SHA256),
        origin=dict(path=ORIGIN_RELATIVE, sha256=ORIGIN_SHA256),
        reviewed_source_pairs=len(SOURCE_PAIRS),
        components_byte_equal=6,
        selected_script_paths=0,
        legacy_database_schema='civ6rl.database_capture_bundle993.v1',
        full_raw_reader_replayed=False,
        native_session_admitted=False,
        producer_identity_substituted=False)

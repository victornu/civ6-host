"""Source-pinned layouts for read-only GameplayScripts list capture.

These profiles permit inspection of retained list headers, not execution of
scripts or admission of an expansion save to the headless loader. No binary
is loaded by this module. The Base reader's existing proof remains separate.
"""
from __future__ import annotations

import copy
import hashlib
import json

from .paths import resource_root
from .resource_resolution import resolve_path
from . import execution_images


BASE_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
XP2_CORE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
CURRENT_XP2_CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
CURRENT_XP2_PROFILE_ID = 'xp2-gamecore-current-092abfbb'
CURRENT_XP2_ACTIVE_GROUP = 'saved_load_active_list_xp2'
CURRENT_XP2_ACTIVE_SPANS = 589
CURRENT_XP2_MANIFEST_SHA256 = '34e6ddc19ae70cd9c2b910bb6f6af0b629dee1ad6f7ddd654250989b225e9bd3'
SUPPORTED_CORES = frozenset((BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256,
                             CURRENT_XP2_CORE_SHA256))
BASE_SOURCE_SHA256 = '78bcfe0876a1bdc5062c5f53726e3e3b43d3548893079eca11f4f2e78897dbf2'
SOURCE = ('work/host-extensions/active-list-source/source.json',
          '404cc80b6ebb63a2e95a692a85152ce4df9cebcfc4cd4a90602b4423c5708dc6')
BASE_STATE_SCHEMA = 'civ6rl.base_gameplay_active_list.memory_snapshot.v1'
EXPANSION_STATE_SCHEMA = 'civ6-host.gameplay_active_list.memory_snapshot.v1'
CURRENT_EXPANSION_STATE_SCHEMA = 'civ6-host.gameplay_active_list.memory_snapshot.v2'
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def source_digest(core_sha):
    # An unsupported-engine negative report retains the historical reader
    # identity and no state. It must not pretend an engine profile exists.
    if type(core_sha) is str and core_sha in (XP1_CORE_SHA256, XP2_CORE_SHA256,
                                               CURRENT_XP2_CORE_SHA256):
        return SOURCE[1]
    return BASE_SOURCE_SHA256


def state_schema(core_sha):
    if core_sha == BASE_CORE_SHA256:
        return BASE_STATE_SCHEMA
    if type(core_sha) is str and core_sha in (XP1_CORE_SHA256, XP2_CORE_SHA256,
                                               CURRENT_XP2_CORE_SHA256):
        return CURRENT_EXPANSION_STATE_SCHEMA if core_sha == CURRENT_XP2_CORE_SHA256 else EXPANSION_STATE_SCHEMA
    raise ValueError('Unsupported GameCore active-list layout')


def expansion_profile(core_sha):
    if type(core_sha) is not str or core_sha not in (
            XP1_CORE_SHA256, XP2_CORE_SHA256, CURRENT_XP2_CORE_SHA256):
        raise ValueError('Unsupported expansion active-list layout')
    source_core_sha = core_sha
    current_evidence = None
    if core_sha == CURRENT_XP2_CORE_SHA256:
        image = execution_images.select(
            CURRENT_XP2_PROFILE_ID, core_path=execution_images.known_path(CURRENT_XP2_PROFILE_ID))
        verification = execution_images.verify(image)
        proof = next((row for row in image.source_proofs
                      if row.group == CURRENT_XP2_ACTIVE_GROUP), None)
        if (image.image_sha256 != CURRENT_XP2_CORE_SHA256
                or image.reference_core_sha256 != XP2_CORE_SHA256
                or image.correspondence_manifest_sha256 != CURRENT_XP2_MANIFEST_SHA256
                or proof is None
                or proof.path != SOURCE[0]
                or proof.sha256 != SOURCE[1]
                or proof.captured_spans != CURRENT_XP2_ACTIVE_SPANS
                or proof.matching_spans != CURRENT_XP2_ACTIVE_SPANS
                or verification.profile_id != CURRENT_XP2_PROFILE_ID
                or verification.image_sha256 != CURRENT_XP2_CORE_SHA256
                or verification.manifest_sha256 != CURRENT_XP2_MANIFEST_SHA256
                or verification.executable is not True
                or verification.game_qualified is not False
                or verification.admission_scope != 'bounded_native_trial'
                or CURRENT_XP2_ACTIVE_GROUP not in verification.verified_groups
                or verification.native_execution_performed):
            raise ValueError('Current XP2 active-list correspondence is not qualified')
        source_core_sha = XP2_CORE_SHA256
        current_evidence = {
            'profile_id': image.id,
            'image_sha256': image.image_sha256,
            'reference_core_sha256': image.reference_core_sha256,
            'manifest_sha256': verification.manifest_sha256,
            'active_list_group': proof.group,
            'active_list_source_sha256': proof.sha256,
            'active_list_captured_spans': proof.captured_spans,
            'active_list_matching_spans': proof.matching_spans,
            'native_execution_performed': False,
        }
    path = resolve_path(resource_root() / SOURCE[0])
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError('Expansion active-list source is missing or oversized')
    with path.open('rb') as stream:
        raw = stream.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES or hashlib.sha256(raw).hexdigest() != SOURCE[1]:
        raise ValueError('Expansion active-list source changed')
    value = json.loads(raw)
    if (type(value) is not dict
            or value.get('schema') != 'civ6-host.expansion-active-list-source.v1'
            or value.get('native_execution') is not False
            or type(value.get('profiles')) is not dict
            or set(value['profiles']) != {XP1_CORE_SHA256, XP2_CORE_SHA256}):
        raise ValueError('Invalid expansion active-list source contract')
    profile = value['profiles'][source_core_sha]
    if (type(profile) is not dict
            or profile.get('status') != 'static_layout_verified_no_execution'
            or profile.get('image', {}).get('sha256') != source_core_sha
            or type(profile.get('checks')) is not dict or not profile['checks']
            or not all(check is True for check in profile['checks'].values())):
        raise ValueError('Expansion active-list source is not qualified for reading')
    result = copy.deepcopy(profile)
    if current_evidence is not None:
        result['runtime_execution_image'] = current_evidence
    return result

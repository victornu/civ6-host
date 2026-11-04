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


BASE_CORE_SHA256 = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
XP1_CORE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
XP2_CORE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
SUPPORTED_CORES = frozenset((BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256))
BASE_SOURCE_SHA256 = '78bcfe0876a1bdc5062c5f53726e3e3b43d3548893079eca11f4f2e78897dbf2'
SOURCE = ('work/host-extensions/active-list-source/source.json',
          '404cc80b6ebb63a2e95a692a85152ce4df9cebcfc4cd4a90602b4423c5708dc6')
BASE_STATE_SCHEMA = 'civ6rl.base_gameplay_active_list.memory_snapshot.v1'
EXPANSION_STATE_SCHEMA = 'civ6-host.gameplay_active_list.memory_snapshot.v1'
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def source_digest(core_sha):
    # An unsupported-engine negative report retains the historical reader
    # identity and no state. It must not pretend an engine profile exists.
    if type(core_sha) is str and core_sha in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        return SOURCE[1]
    return BASE_SOURCE_SHA256


def state_schema(core_sha):
    if core_sha == BASE_CORE_SHA256:
        return BASE_STATE_SCHEMA
    if type(core_sha) is str and core_sha in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        return EXPANSION_STATE_SCHEMA
    raise ValueError('Unsupported GameCore active-list layout')


def expansion_profile(core_sha):
    if type(core_sha) is not str or core_sha not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Unsupported expansion active-list layout')
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
    profile = value['profiles'][core_sha]
    if (type(profile) is not dict
            or profile.get('status') != 'static_layout_verified_no_execution'
            or profile.get('image', {}).get('sha256') != core_sha
            or type(profile.get('checks')) is not dict or not profile['checks']
            or not all(check is True for check in profile['checks'].values())):
        raise ValueError('Expansion active-list source is not qualified for reading')
    return copy.deepcopy(profile)

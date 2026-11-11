"""Explicit static identities for native execution images.

This registry keeps an installed GameCore distinct from the older image
that anchors captured ABIs. It can admit only a statically verified bounded
native trial; it never claims full-game qualification or runs native code.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import os
import re
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


_CURRENT_CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
_CURRENT_CORE_SIZE_BYTES = 12941080
_REFERENCE_CORE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
_SHARED_INTERFACE_SHA256 = 'a4de406dfbbed460af4ed2b15b7cb4d75afc610e3f9268838b65a65fc9a069c9'
_NATIVE_HOST_BUILD_ID = 'xp2-current-strings-source-v1'
_NATIVE_HOST_BUILD_EXECUTABLE = 'work/native-host-xp2-current-strings-build01/civ6rl-native-python.exe'
_NATIVE_HOST_BUILD_EXECUTABLE_SHA256 = '106018516854f1e28d34814f24e08d3834eee0272f143b3daba0d4a5c571bc5e'
_NATIVE_HOST_BUILD_EXECUTABLE_BYTES = 134656
_NATIVE_HOST_BUILD_RECORD = 'work/native-host-xp2-current-strings-build01/build.json'
_NATIVE_HOST_BUILD_RECORD_SHA256 = '391f78fcb31aff04b3c552122fb1143e3380fdca94ad6bbdb639ffbf63d50fa3'
_NATIVE_HOST_BUILD_MANIFEST_SHA256 = '7e67158f208f19cd9d29c36ce940a8c6082096ae750bf925884a63ce51f7b303'
_COMPARISON_MANIFEST_SHA256 = '34e6ddc19ae70cd9c2b910bb6f6af0b629dee1ad6f7ddd654250989b225e9bd3'
_COMPARISON_MANIFEST_PATH = (
    'work/bbg751-turn-source-scope/war-confirmation/'
    'current-build-capture-comparison-v1.json'
)
_GAMECORE_PATH = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI"
    r"\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"
)


@dataclass(frozen=True)
class ImageFileIdentity:
    name: str
    path: str
    sha256: str
    reference_sha256: str


@dataclass(frozen=True)
class SourceProofReference:
    group: str
    path: str
    sha256: str
    captured_spans: int
    matching_spans: int


@dataclass(frozen=True)
class PinnedSourceReference:
    path: str
    sha256: str


@dataclass(frozen=True)
class NativeHostBuildReference:
    profile_id: str
    executable_path: str
    executable_sha256: str
    executable_size_bytes: int
    build_record_path: str
    build_record_sha256: str
    source_manifest_sha256: str


@dataclass(frozen=True)
class ExecutionImageProfile:
    id: str
    image_sha256: str
    image_size_bytes: int
    reference_core_sha256: str
    path: str
    shared_dependencies: tuple[ImageFileIdentity, ...]
    correspondence_manifest_path: str
    correspondence_manifest_sha256: str
    correspondence_manifest_spans: int
    matching_correspondence_spans: int
    source_proofs: tuple[SourceProofReference, ...]
    correspondence_sources: tuple[PinnedSourceReference, ...]
    native_host_build: NativeHostBuildReference
    covered_groups: tuple[str, ...]
    matched_interface_groups: tuple[str, ...]
    matched_build_groups: tuple[str, ...]
    missing_groups: tuple[str, ...]
    limitations: tuple[str, ...]

    @property
    def state(self) -> str:
        """Static evidence state; this does not authorize a native load."""
        if (self.missing_groups or not self.covered_groups or not self.source_proofs or
                not self.matched_interface_groups or not self.matched_build_groups or
                self.correspondence_manifest_spans <= 0 or
                self.correspondence_manifest_spans != self.matching_correspondence_spans):
            return 'blocked'
        return 'candidate_for_bounded_native_trial'

    @property
    def executable(self) -> bool:
        # This is an explicit, scoped trial eligibility bit. `verify()` must
        # still check the files and evidence before any caller can load native code.
        return self.state == 'candidate_for_bounded_native_trial'


@dataclass(frozen=True)
class ExecutionImageVerification:
    profile_id: str
    image_sha256: str
    reference_core_sha256: str
    path: str
    manifest_sha256: str
    native_host_executable_sha256: str
    native_host_build_record_sha256: str
    native_host_build_manifest_sha256: str
    verified_groups: tuple[str, ...]
    missing_groups: tuple[str, ...]
    executable: bool
    admission_scope: str
    game_qualified: bool
    native_execution_performed: bool
    limitations: tuple[str, ...]


class ExecutionImageVerificationError(ValueError):
    """A requested correspondence group is not covered by pinned evidence."""

    def __init__(self, message: str, *, missing_groups: tuple[str, ...] = ()):
        super().__init__(message)
        self.missing_groups = missing_groups


_SOURCE_PROOFS = (
    SourceProofReference(
        'native_context_factory_destructor',
        'evidence/native-expansion-context/6f808ce7420c461ee4e0b7cb1cab46d90c7df4b4c1120cf2958c3477f0773cc1.json',
        '6f808ce7420c461ee4e0b7cb1cab46d90c7df4b4c1120cf2958c3477f0773cc1', 5, 5),
    SourceProofReference(
        'native_context_constructor_and_vtable',
        'evidence/native-expansion-context-constructors/127fdfff335b79415a665c57bb76e2f44a253d42aec27445f6d5fd970269591d.json',
        '127fdfff335b79415a665c57bb76e2f44a253d42aec27445f6d5fd970269591d', 23, 23),
    SourceProofReference(
        'saved_load_dispatch_xp2',
        'work/host-extensions/load-dispatch-static/complete-load-dispatch.json',
        'd3e8f3ada6f37edd1a5baf1bfa59dce93143dbe262fa92d3adb13ecf95d2aef2', 124, 124),
    SourceProofReference(
        'saved_load_prepare_xp2',
        'work/host-extensions/load-prepare-static/prepare-lifecycle-v2.json',
        '615cda7a2fb1ab7e17f3bc726578efd6a1ecbc96482764d6dc2414261a389e5a', 361, 361),
    SourceProofReference(
        'saved_load_active_list_xp2',
        'work/host-extensions/active-list-source/source.json',
        '404cc80b6ebb63a2e95a692a85152ce4df9cebcfc4cd4a90602b4423c5708dc6', 589, 589),
    SourceProofReference(
        'xp2_context_initialization',
        'work/host-extensions/xp2-context-initialization/source-profile-v3.json',
        '5d386ab8de757623da143f4e3277d62827b35ba5f784f6b31e6a3d28d1a651fe', 25, 25),
    SourceProofReference(
        'xp2_prepare_services',
        'work/host-extensions/xp2-prepare-services/source-profile-v1.json',
        '6902ee066de66136ef5ceac7dfe203bd7c87145d6ae2b271206a5b0141a81e6e', 23, 23),
    SourceProofReference(
        'xp2_configuration_provider',
        'work/host-extensions/xp2-configuration-static/xp2_configuration_source_v1.json',
        '46ddfc453e1bf0d9de7cd5509173ebad3e25cf4d208906e08701d2ab790e8387', 530, 530),
    SourceProofReference(
        'xp2_configuration_copy',
        'work/host-extensions/xp2-configuration-copy-static/xp2-configuration-copy-source-v1.json',
        '884114e402319b773c5922baef55f5ea8439a1c2a7cda48e849805a6a82fb8c5', 47, 47),
)

_DEPENDENCIES = (
    ImageFileIdentity(
        'DatabaseDLL_FinalRelease.dll',
        r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\DatabaseDLL_FinalRelease.dll",
        'd0fac3847b55af5bbe74b9fe7d4677f5bc462c579a8eb2b254cdefd7ff2032f8',
        'e6577e873f946224df65c02f6c4bc3b385607e2a82d957b0fd613e01cbe78b0c'),
    ImageFileIdentity(
        'Localization_FinalRelease.dll',
        r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\Localization_FinalRelease.dll",
        '8490e6694b966564f2f0baf6b685e6f23817c7348996511ce03891c0d14fe431',
        '0becd5c425a3d6edc88f5315c01af3dd30dd7cb158271d56f4bba7ff2bb4e056'),
    ImageFileIdentity(
        'HavokScript_FinalRelease.dll',
        r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\Base\Binaries\Win64Steam\HavokScript_FinalRelease.dll",
        '201979051f23378fed5ec50a49d36593591adbce5d1be6b7a42f482da46c73de',
        '9fb4e34afa6666aafb519d6edb9c1e4e9add9cce2cecaa3b1e5bb8f08b168532'),
)

_DEPENDENCY_FILE_SIZES = {
    'DatabaseDLL_FinalRelease.dll': 931104,
    'Localization_FinalRelease.dll': 1718048,
    'HavokScript_FinalRelease.dll': 581408,
}

_CORRESPONDENCE_SOURCES = (
    PinnedSourceReference(
        'work/bbg751-turn-source-scope/shared-dependencies/current-shared-dependency-interfaces-v1.json',
        _SHARED_INTERFACE_SHA256),
    PinnedSourceReference('evidence/phase38-database-query.json',
        '46647abdcb753dee21320ccf2068e5c1fe6b091ca52089c250326de0ae5f9d08'),
    PinnedSourceReference('evidence/phase23-native-localization.json',
        'ac4a108171f5025470dab053c3ef55410a2a440f1f064071429bb8b0d32be868'),
    PinnedSourceReference('evidence/phase24-havok-vm-static.json',
        'c2ac077310f2545de9f7d4e858c7ecdb28bdb0f8dbaea03a7de12db304ed443b'),
    PinnedSourceReference('evidence/phase34-havok-factory.json',
        'a10f8dd2138851cd516e5917bb1347ae2fd41a19ee5e3a00128c0dd0e433d1ee'),
)

_NATIVE_HOST_BUILD = NativeHostBuildReference(
    profile_id=_NATIVE_HOST_BUILD_ID,
    executable_path=_NATIVE_HOST_BUILD_EXECUTABLE,
    executable_sha256=_NATIVE_HOST_BUILD_EXECUTABLE_SHA256,
    executable_size_bytes=_NATIVE_HOST_BUILD_EXECUTABLE_BYTES,
    build_record_path=_NATIVE_HOST_BUILD_RECORD,
    build_record_sha256=_NATIVE_HOST_BUILD_RECORD_SHA256,
    source_manifest_sha256=_NATIVE_HOST_BUILD_MANIFEST_SHA256,
)

_PROFILE = ExecutionImageProfile(
    id='xp2-gamecore-current-092abfbb',
    image_sha256=_CURRENT_CORE_SHA256,
    image_size_bytes=_CURRENT_CORE_SIZE_BYTES,
    reference_core_sha256=_REFERENCE_CORE_SHA256,
    path=_GAMECORE_PATH,
    shared_dependencies=_DEPENDENCIES,
    correspondence_manifest_path=_COMPARISON_MANIFEST_PATH,
    correspondence_manifest_sha256=_COMPARISON_MANIFEST_SHA256,
    correspondence_manifest_spans=1727,
    matching_correspondence_spans=1727,
    source_proofs=_SOURCE_PROOFS,
    correspondence_sources=_CORRESPONDENCE_SOURCES,
    native_host_build=_NATIVE_HOST_BUILD,
    covered_groups=tuple(row.group for row in _SOURCE_PROOFS),
    matched_interface_groups=(
        'database_exports_ordinals_and_consumed_vtable_slots_match_reference',
        'localization_selected_exports_and_host_locale_bridge_rvas_match_reference',
    ),
    matched_build_groups=(
        'havok_current_rva_thread_import_overlay_and_tonumber_guards_exact_build',
    ),
    missing_groups=(),
    limitations=(
        'Core evidence is limited to 1727 selected byte spans, not whole-image ABI equivalence.',
        'Database and Localization admission covers the observed exports/prototypes/slots only; semantic behavior is not qualified.',
        'The Havok overlay and file pins admit only a bounded native trial; runtime behavior remains untested.',
        'Base-only native_checkpoint_load plan and prepared-restore receipts are not XP2 evidence.',
        'This profile does not qualify a full game, later turns, or a complete gameplay scope.',
    ),
)
_XP1_CORE_SHA256 = '63c17d9e417aa780427383cfda41d7ab3ca4e964f37ea4d8de30afdb0e8a56cb'
_XP1_REFERENCE_SHA256 = '259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
_XP1_CORE_PATH = _GAMECORE_PATH.replace(
    r'\Expansion2\Binaries\Win64\GameCore_XP2_', r'\Expansion1\Binaries\Win64\GameCore_XP1_')
_XP1_SOURCE_PROOFS = (*_SOURCE_PROOFS[:2], SourceProofReference(
    'xp1_retained_lan_code_spans', 'work/trade-common-client/xp1-installed-source-comparison.json',
    '277edae93a3d533e944cf16ca2bd97d40675c241c901a7985228a0e06e6f4b96', 39262, 39262))
_XP1_UI_BINDER = '1ec54d12e6c014a8ba9b2f97e68edf7ad2d775e9129a16eaa092db2159affc9f'
_XP1_PROFILE = replace(
    _PROFILE,
    id='xp1-gamecore-current-63c17d9',
    image_sha256=_XP1_CORE_SHA256,
    image_size_bytes=11159832,
    reference_core_sha256=_XP1_REFERENCE_SHA256,
    path=_XP1_CORE_PATH,
    correspondence_manifest_path='work/trade-common-client/xp1-installed-context-shared-join.json',
    correspondence_manifest_sha256='b60b2bcf4d711fc037a2ac0b818c6bf3d4d0acb9b94e3c731474a4a3f08ba88f',
    correspondence_manifest_spans=39290,
    matching_correspondence_spans=39290,
    source_proofs=_XP1_SOURCE_PROOFS,
    covered_groups=tuple(row.group for row in _XP1_SOURCE_PROOFS),
    matched_interface_groups=(*_PROFILE.matched_interface_groups, 'xp1_imports_resolved_in_shared_libraries'),
    matched_build_groups=(*_PROFILE.matched_build_groups, 'xp1_legacy_lua_binder_retained'),
    limitations=(
        'Only the captured XP1 code spans and the selected shared-library interfaces are compared.',
        'Context preflight does not qualify an official capture, a native session, or any gameplay family.',
    ),
)
_REGISTRY: Mapping[str, ExecutionImageProfile] = MappingProxyType(
    {row.id: row for row in (_PROFILE, _XP1_PROFILE)}
)
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_REQUIRED_EXECUTION_GROUPS = (
    *_PROFILE.covered_groups,
    *_PROFILE.matched_interface_groups,
    *_PROFILE.matched_build_groups,
    *_PROFILE.missing_groups,
)


def select(profile_id: str, *, core_path: str | os.PathLike[str]) -> ExecutionImageProfile:
    """Select pinned metadata for an exact image path; do not read or load it."""
    if type(profile_id) is not str or not profile_id:
        raise ValueError('profile_id must be an explicit non-empty string')
    profile = _REGISTRY.get(profile_id)
    if profile is None:
        raise ValueError(f'unrecognized execution-image profile: {profile_id!r}')
    if not isinstance(core_path, (str, os.PathLike)):
        raise ValueError('core_path must be an explicit installed image path')
    requested_path = os.path.normcase(os.path.normpath(os.fspath(core_path)))
    pinned_path = os.path.normcase(os.path.normpath(profile.path))
    if requested_path != pinned_path:
        raise ValueError('installed image path does not match the selected profile')
    if _SHA256_RE.fullmatch(profile.image_sha256) is None:
        raise RuntimeError('profile has an invalid current image SHA-256')
    if _SHA256_RE.fullmatch(profile.reference_core_sha256) is None:
        raise RuntimeError('profile has an invalid reference core SHA-256')
    if profile.image_sha256 == profile.reference_core_sha256:
        raise RuntimeError('installed image and reference ABI image must remain distinct')
    if any(_SHA256_RE.fullmatch(row.sha256) is None for row in profile.source_proofs):
        raise RuntimeError('profile contains an invalid pinned source proof hash')
    if any(_SHA256_RE.fullmatch(row.sha256) is None or
           _SHA256_RE.fullmatch(row.reference_sha256) is None
           for row in profile.shared_dependencies):
        raise RuntimeError('profile contains an invalid dependency image hash')
    if (profile.correspondence_manifest_spans !=
            profile.matching_correspondence_spans):
        raise RuntimeError('pinned source correspondence summary is internally inconsistent')
    if not profile.covered_groups or not profile.source_proofs:
        raise RuntimeError('execution-image profile has no pinned source correspondence')
    if sum(row.captured_spans for row in profile.source_proofs) != profile.correspondence_manifest_spans:
        raise RuntimeError('source proof span totals disagree with the pinned manifest')
    if any(row.captured_spans != row.matching_spans for row in profile.source_proofs):
        raise RuntimeError('a pinned source correspondence group is not fully matched')
    if len(profile.shared_dependencies) != 3:
        raise RuntimeError('execution-image profile has an incomplete dependency identity set')
    return profile


def select_pair(actual_sha256: str, reference_sha256: str) -> ExecutionImageProfile:
    """Select the registered installed/reference pair used by a shared service."""
    for profile in _REGISTRY.values():
        if (profile.image_sha256, profile.reference_core_sha256) == (actual_sha256, reference_sha256):
            return select(profile.id, core_path=profile.path)
    raise ValueError('unrecognized actual/reference execution-image pair')


def known_path(profile_id: str) -> Path:
    """Return the registered canonical path from an explicit profile id only."""
    if type(profile_id) is not str or not profile_id:
        raise ValueError('profile_id must be an explicit non-empty string')
    profile = _REGISTRY.get(profile_id)
    if profile is None:
        raise ValueError(f'unrecognized execution-image profile: {profile_id!r}')
    return Path(profile.path)


def identity(profile: ExecutionImageProfile) -> dict[str, str]:
    """Return a deterministic four-field selection identity, not an attestation."""
    if type(profile) is not ExecutionImageProfile or _REGISTRY.get(profile.id) is not profile:
        raise ValueError('profile is not the registered immutable identity')
    return {
        'profile_id': profile.id,
        'image_sha256': profile.image_sha256,
        'reference_core_sha256': profile.reference_core_sha256,
        'path': profile.path,
    }


def from_identity(value: object) -> ExecutionImageProfile:
    """Re-select only if a serialized identity exactly matches the local pin."""
    expected_keys = {'profile_id', 'image_sha256', 'reference_core_sha256', 'path'}
    if type(value) is not dict or set(value) != expected_keys:
        raise ValueError('execution-image identity has an unexpected shape')
    if any(type(value[key]) is not str for key in expected_keys):
        raise ValueError('execution-image identity fields must be strings')
    profile = select(value['profile_id'], core_path=value['path'])
    if identity(profile) != value:
        raise ValueError('serialized execution-image identity differs from the local pin')
    return profile


def _hash_file_and_size(path: str) -> tuple[str, int]:
    file_path = Path(path)
    if not file_path.is_file() or file_path.resolve() != file_path:
        raise ValueError('selected GameCore path is absent, redirected, or not a file')
    digest = hashlib.sha256()
    size = 0
    with file_path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _resource_file(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('pinned resource path must be root-relative')
    target = root / relative
    resolved = target.resolve(strict=True)
    if resolved != target or not resolved.is_relative_to(root):
        raise ValueError('pinned resource escaped the canonical resource root')
    return resolved


def _verify_native_host_build(profile: ExecutionImageProfile):
    from .source_build_identity import (
        CURRENT_STRINGS_BUILD_PROFILE,
        CURRENT_STRINGS_HOST_REFERENCE,
        SOURCE_BUILDS,
        _CURRENT_STRINGS_COMPONENT_TRANSITION,
        verify_source_build,
        xp2_component_requirements,
    )

    build_pin = profile.native_host_build
    if (CURRENT_STRINGS_BUILD_PROFILE != build_pin.profile_id or
            CURRENT_STRINGS_HOST_REFERENCE !=
            (build_pin.executable_path, build_pin.executable_sha256)):
        raise ValueError('registered current strings host build differs from the execution-image pin')
    selected_build = SOURCE_BUILDS.get(build_pin.executable_sha256)
    if (selected_build is None or
            selected_build.get('profile') != build_pin.profile_id or
            selected_build.get('manifest_sha256') != build_pin.source_manifest_sha256 or
            selected_build.get('reference') !=
            (build_pin.build_record_path, build_pin.build_record_sha256)):
        raise ValueError('native host build identity is not the exact reviewed source-build record')

    from .paths import resource_root
    root = resource_root()
    executable = _resource_file(root, build_pin.executable_path)
    actual_exe_sha, actual_exe_size = _hash_file_and_size(str(executable))
    if (actual_exe_sha, actual_exe_size) != (
            build_pin.executable_sha256, build_pin.executable_size_bytes):
        raise ValueError('compiled native host executable differs from the selected build')
    build_record = _resource_file(root, build_pin.build_record_path)
    record_sha, _record_size = _hash_file_and_size(str(build_record))
    if record_sha != build_pin.build_record_sha256:
        raise ValueError('native host build record differs from the selected build')
    record = json.loads(build_record.read_bytes())
    artifact = record.get('executable', {})
    if (record.get('schema') != 'civ6-host.native-build.v1' or
            record.get('status') != 'source_build_unqualified' or
            record.get('profile') != build_pin.profile_id or
            record.get('source_manifest_sha256') != build_pin.source_manifest_sha256 or
            record.get('compiler_exit_code') != 0 or record.get('compiler_reaped') is not True or
            record.get('gamecore_loaded') is not False or
            record.get('original_lab_required') is not False or
            record.get('compatibility_admitted') is not False or
            artifact.get('sha256') != build_pin.executable_sha256 or
            artifact.get('bytes') != build_pin.executable_size_bytes or
            Path(artifact.get('path', '')).resolve(strict=True) != executable):
        raise ValueError('native host build receipt differs from the exact bounded-trial build')

    expected_transition_names = {
        'script_game_event_aggregators.inc',
        'gamecore_python_host.c',
        'script_game_event_result_map.inc',
        'script_aux_b8.inc',
        'script_game_event_dispatch_legacy.inc',
    }
    if set(_CURRENT_STRINGS_COMPONENT_TRANSITION) != expected_transition_names:
        raise ValueError('native host build no longer has the exact five strings source transitions')
    historical_components = {
        name: old for name, (old, _current) in _CURRENT_STRINGS_COMPONENT_TRANSITION.items()
    }
    required_components = xp2_component_requirements(executable, historical_components)
    expected_current_components = {
        name: current for name, (_old, current) in _CURRENT_STRINGS_COMPONENT_TRANSITION.items()
    }
    if required_components != expected_current_components:
        raise ValueError('current strings component transition changed from the reviewed build')
    if profile is _XP1_PROFILE:
        required_components = dict(required_components, **{'script_core_bindings_xp1_legacy.inc': _XP1_UI_BINDER})
    receipt = verify_source_build(executable, required_components=required_components)
    if (receipt.get('profile') != build_pin.profile_id or
            receipt.get('source_manifest_sha256') != build_pin.source_manifest_sha256 or
            receipt.get('build_reference') !=
            [build_pin.build_record_path, build_pin.build_record_sha256] or
            receipt.get('native_compatibility_claimed') is not False):
        raise ValueError('source-build identity verifier returned an unexpected receipt')
    return receipt


def source_dependencies(profile: ExecutionImageProfile) -> dict[str, str]:
    """Return absolute file pins for correspondence sources and selected images.

    Host source pins embedded as historical attribution in the interface
    supplement are deliberately excluded. Current installed host sources use
    their own ``installed_source_pins``. The selected native-host executable,
    build record and staged inputs are verified by ``source_build_identity``.
    """
    if type(profile) is not ExecutionImageProfile or _REGISTRY.get(profile.id) is not profile:
        raise ValueError('profile is not the registered immutable identity')
    from .paths import resource_root

    root = resource_root()
    pins: dict[str, str] = {}

    def add(path: str | Path, digest: str) -> None:
        absolute = Path(path)
        if not absolute.is_absolute():
            raise ValueError('source dependency path is not absolute')
        key = str(absolute)
        if key in pins and pins[key] != digest:
            raise ValueError('source dependency path has conflicting hashes')
        pins[key] = digest

    add(profile.path, profile.image_sha256)
    for dependency in profile.shared_dependencies:
        add(dependency.path, dependency.sha256)
    source_rows = (*profile.source_proofs,)
    for row in source_rows:
        relative = Path(row.path)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('source proof reference must be contained under the resource root')
        target = root / relative
        resolved = target.resolve(strict=True)
        if resolved != target or not resolved.is_relative_to(root):
            raise ValueError('source proof escaped the canonical resource root')
        add(resolved, row.sha256)
    for row in profile.correspondence_sources:
        add(_resource_file(root, row.path), row.sha256)
    add(_resource_file(root, profile.correspondence_manifest_path),
        profile.correspondence_manifest_sha256)

    build_receipt = _verify_native_host_build(profile)
    build_pin = profile.native_host_build
    add(_resource_file(root, build_pin.executable_path), build_pin.executable_sha256)
    add(_resource_file(root, build_pin.build_record_path), build_pin.build_record_sha256)
    for path, digest in build_receipt['build_dependencies'].items():
        dependency_path = Path(path)
        if not dependency_path.is_absolute():
            dependency_path = root / dependency_path
        resolved = dependency_path.resolve(strict=True)
        if resolved != dependency_path:
            raise ValueError('native host source-build dependency path is redirected')
        add(resolved, digest)
    return dict(sorted(pins.items()))


def runtime_source_pins(
    pins: Mapping[str, str],
    *,
    execution_image: ExecutionImageProfile | None = None,
) -> dict[str, str]:
    """Materialize expected source pins for one explicitly selected image.

    Static capture proofs remain anchored to their reference image. Only the
    installed Core file pin is translated, and only when its exact path/hash
    pair is present alongside the canonical registered profile. This is a pure
    pin transformation, not a file check, verification receipt, or admission.
    """
    if not isinstance(pins, Mapping):
        raise TypeError('source pins must be a mapping')
    result = dict(pins)
    if execution_image is None:
        return result
    if (type(execution_image) is not ExecutionImageProfile
            or _REGISTRY.get(execution_image.id) is not execution_image):
        raise ValueError('execution image must be the canonical registered profile')
    profile = execution_image
    core_path = profile.path
    core_key = os.path.normcase(os.path.normpath(core_path))
    for key in result:
        if (type(key) is str and os.path.normcase(os.path.normpath(key)) == core_key
                and key != core_path):
            raise ValueError('source pins contain a non-canonical alias for the selected Core path')
    if core_path not in result:
        return result
    if result[core_path] != profile.reference_core_sha256:
        raise ValueError('source pin for the selected Core is not the exact reference-image pair')
    result[core_path] = profile.image_sha256
    return result


def _verify_capture_manifest(profile: ExecutionImageProfile, root: Path) -> None:
    path = _resource_file(root, profile.correspondence_manifest_path)
    manifest = json.loads(path.read_bytes())
    if profile is _XP1_PROFILE:
        _verify_xp1_capture_manifest(profile, root, manifest)
        return
    if (manifest.get('schema') != 'civ6-host.current-image-pinned-capture-comparison.v1' or
            manifest.get('classification') !=
            'static_byte_comparison_only_not_ABI_or_runtime_admission'):
        raise ValueError('pinned Core comparison manifest has an unexpected schema or classification')
    rows = [row for row in manifest.get('comparisons', ())
            if row.get('current_image', {}).get('id') == 'gamecore']
    expected_sources = {row.path for row in profile.source_proofs}
    source_paths = {row.get('source_proof', {}).get('path') for row in rows}
    if (len(rows) != profile.correspondence_manifest_spans or
            source_paths != expected_sources or
            any(row.get('matches') is not True or
                row.get('current_image', {}).get('sha256') != profile.image_sha256 or
                row.get('reference_image', {}).get('sha256') != profile.reference_core_sha256
                for row in rows)):
        raise ValueError('pinned Core byte-comparison rows do not match the registered capture groups')
    summary = next((row for row in manifest.get('image_summaries', ())
                    if row.get('image') == 'gamecore'), None)
    if (summary is None or summary.get('ranges') != profile.correspondence_manifest_spans or
            summary.get('matches') != profile.matching_correspondence_spans or
            summary.get('mismatches') != 0 or
            summary.get('current_sha256') != profile.image_sha256):
        raise ValueError('pinned Core comparison summary differs from its exact rows')


def _verify_xp1_capture_manifest(profile: ExecutionImageProfile, root: Path, manifest: dict) -> None:
    core = manifest['core']
    if (manifest['schema'] != 'civ6-host.xp1-installed-context-and-shared-join.static.v1'
            or manifest['native_calls'] != 0 or Path(core['path']) != Path(profile.path)
            or core['sha256'] != profile.image_sha256 or core['bytes'] != profile.image_size_bytes
            or manifest['reference_core_sha256'] != profile.reference_core_sha256
            or manifest['reference_shared_image_pair'] != {
                'actual_image_sha256': _PROFILE.image_sha256,
                'interface_reference_sha256': _PROFILE.reference_core_sha256,
            }):
        raise ValueError('XP1 context/shared evidence has the wrong image pair')
    context = manifest['context']
    if len(context) != 2:
        raise ValueError('XP1 factory and constructor sources are required')
    for row, expected in zip(context, profile.source_proofs[:2]):
        if (row['group'] != expected.group or row['source']['path'] != expected.path
                or row['source']['sha256'] != expected.sha256
                or len(row['spans']) != expected.captured_spans):
            raise ValueError('XP1 context comparison is incomplete')
    audit_ref = profile.source_proofs[-1]
    audit = manifest['retained_code_comparison']
    if (audit['path'], audit['sha256']) != (audit_ref.path, audit_ref.sha256):
        raise ValueError('XP1 retained source comparison differs')
    comparison = json.loads(_resource_file(root, audit_ref.path).read_bytes())
    if (comparison['installed_core'] != core
            or comparison['reference_core_sha256'] != profile.reference_core_sha256
            or comparison['retained_sources']['distinct_spans'] != audit_ref.captured_spans
            or comparison['retained_sources']['mismatches']):
        raise ValueError('XP1 retained source ranges differ')
    interface_ref = profile.correspondence_sources[0]
    interface = manifest['common_interface_source']
    if (interface['path'], interface['sha256']) != (interface_ref.path, interface_ref.sha256):
        raise ValueError('XP1 shared library evidence changed')
    dependencies = manifest['shared_dependencies']
    if set(dependencies) != {row.name for row in profile.shared_dependencies}:
        raise ValueError('XP1 shared library set changed')
    for dependency, count in zip(profile.shared_dependencies, (1, 28, 48)):
        row = dependencies[dependency.name]
        library = row['library']
        if (Path(library['path']) != Path(dependency.path)
                or library['sha256'] != dependency.sha256
                or row['reference_sha256'] != dependency.reference_sha256
                or len(row['imports']) != count):
            raise ValueError('XP1 shared library import evidence changed: ' + dependency.name)
    if (manifest['host']['sha256'] != profile.native_host_build.executable_sha256
            or manifest['xp1_legacy_binder']['sha256'] != _XP1_UI_BINDER
            or set(manifest['host_exports']) != {'LAB_HavokHeapCreate', 'LAB_HavokHeapDestroy',
                'LAB_XP1ScriptCoreBindingsInstall', 'LAB_XP1ScriptCoreUIBindingsInstall'}):
        raise ValueError('XP1 selected host build evidence changed')


def _verify_interface_contract(profile: ExecutionImageProfile, root: Path) -> None:
    from .native.native_shared_dependency_profiles import profile_for_shared_dependencies

    proof_ref = profile.correspondence_sources[0]
    proof_path = _resource_file(root, proof_ref.path)
    proof = json.loads(proof_path.read_bytes())
    if (proof.get('schema') != 'civ6-host.shared-dependency-interface-current.v1' or
            proof.get('engine_pair') != {
                'actual_image_sha256': _PROFILE.image_sha256,
                'interface_reference_sha256': _PROFILE.reference_core_sha256,
            }):
        raise ValueError('shared dependency interface proof has the wrong schema or image pair')

    libraries = proof.get('libraries', {})
    if set(libraries) != {row.name for row in profile.shared_dependencies}:
        raise ValueError('shared dependency proof does not name exactly the selected DLL set')
    for dependency in profile.shared_dependencies:
        row = libraries[dependency.name]
        if (row.get('path') != dependency.path or
                row.get('current_sha256') != dependency.sha256 or
                row.get('reference_sha256') != dependency.reference_sha256 or
                row.get('size_bytes') != _DEPENDENCY_FILE_SIZES[dependency.name]):
            raise ValueError(f'shared dependency proof identity differs for {dependency.name}')

    database = proof.get('database_interface', {})
    database_exports = database.get('exports', ())
    connection_slots = database.get('connection_slots_rva', {})
    result_slots = database.get('query_result_slots_rva', {})
    if (database.get('current_sha256') != _DEPENDENCIES[0].sha256 or
            database.get('reference_sha256') != _DEPENDENCIES[0].reference_sha256 or
            len(database_exports) != 5 or
            any(row.get('matches_reference_rva') is not True for row in database_exports) or
            len(connection_slots) != 16 or len(result_slots) != 3 or
            database.get('selected_slots_match_reference') is not True or
            database.get('consumer_slots') != {
                'connection_release': '0x8',
                'connection_query': '0x18',
                'result_release': '0x8',
                'result_advance': '0x20',
                'result_get_string': '0xf0',
            }):
        raise ValueError('Database selected export/slot interface is not fully matched')

    localization = proof.get('localization_interface', {})
    localization_exports = localization.get('selected_exports', ())
    bridge_exports = localization.get('host_locale_bridge_exports', ())
    if (localization.get('current_sha256') != _DEPENDENCIES[1].sha256 or
            localization.get('reference_sha256') != _DEPENDENCIES[1].reference_sha256 or
            len(localization_exports) != 12 or
            any(row.get('matches_reference_rva') is not True for row in localization_exports) or
            localization.get('all_selected_symbols_and_rvas_match_reference') is not True or
            len(bridge_exports) != 8 or
            not set(bridge_exports).issubset({row.get('name') for row in localization_exports})):
        raise ValueError('Localization selected export/bridge interface is not fully matched')

    havok = proof.get('havok_interface', {})
    thread_imports = havok.get('host_thread_imports', ())
    direct_exports = havok.get('additional_direct_exports', ())
    if (havok.get('current_sha256') != _DEPENDENCIES[2].sha256 or
            havok.get('reference_sha256') != _DEPENDENCIES[2].reference_sha256 or
            havok.get('thread_import_count') != 48 or len(thread_imports) != 48 or
            havok.get('thread_import_names_present') is not True or
            havok.get('thread_import_old_rva_match_count') != 0 or
            havok.get('thread_import_all_old_rvas_rejected_by_current_shim') != 48 or
            len(direct_exports) != 4):
        raise ValueError('Havok relocation evidence differs from the reviewed 48-import/4-export map')

    shared = profile_for_shared_dependencies(
        Path(profile.shared_dependencies[0].path).parent,
        actual_image_sha256=profile.image_sha256,
        interface_reference_sha256=profile.reference_core_sha256,
    )
    actual_paths = shared.verify_files()
    if set(actual_paths) != {row.name for row in profile.shared_dependencies}:
        raise ValueError('selected shared dependency files are incomplete')
    for name, path in actual_paths.items():
        if path.stat().st_size != _DEPENDENCY_FILE_SIZES[name]:
            raise ValueError(f'selected shared dependency byte size differs: {name}')
    if shared.interface_evidence_sha256 != _SHARED_INTERFACE_SHA256:
        raise ValueError('shared dependency profile refers to another interface proof')
    if shared.havok_shim_rva_mismatches != 48:
        raise ValueError('selected Havok shim mismatch count differs from the retained proof')


def verify(
    profile: ExecutionImageProfile,
    required_groups: tuple[str, ...] = (),
) -> ExecutionImageVerification:
    """Verify exact files and selected interfaces for a bounded native trial.

    Success is a pre-load authorization for the registered host overlay only.
    It does not run a native call and does not qualify full-game behavior.
    """
    if type(profile) is not ExecutionImageProfile or _REGISTRY.get(profile.id) is not profile:
        raise ExecutionImageVerificationError('profile is not the registered immutable identity')
    if type(required_groups) not in (tuple, list) or any(
            type(group) is not str or not group for group in required_groups):
        raise ExecutionImageVerificationError('required_groups must be a sequence of non-empty names')
    default_groups = (_REQUIRED_EXECUTION_GROUPS if profile is _PROFILE else (
        *profile.covered_groups, *profile.matched_interface_groups, *profile.matched_build_groups,
        *profile.missing_groups))
    requested = tuple(dict.fromkeys((*default_groups, *required_groups)))
    evidence_groups = set((
        *profile.covered_groups, *profile.matched_interface_groups,
        *profile.matched_build_groups,
    ))
    absent = tuple(group for group in requested if group not in evidence_groups)
    if absent or profile.missing_groups:
        missing = tuple(dict.fromkeys((*absent, *profile.missing_groups)))
        raise ExecutionImageVerificationError(
            'required static correspondence groups are missing: ' + ', '.join(missing),
            missing_groups=missing)
    if (not profile.covered_groups or not profile.source_proofs or
            not profile.matched_interface_groups or not profile.matched_build_groups or
            profile.correspondence_manifest_spans <= 0 or
            profile.correspondence_manifest_spans != profile.matching_correspondence_spans or
            sum(row.captured_spans for row in profile.source_proofs) !=
            profile.correspondence_manifest_spans or
            any(row.captured_spans != row.matching_spans for row in profile.source_proofs)):
        raise ExecutionImageVerificationError('profile has incomplete or empty pinned source correspondence')

    from .paths import resource_root
    root = resource_root()
    try:
        pins = source_dependencies(profile)
        core_key = os.path.normcase(profile.path)
        native_host_exe = _resource_file(root, profile.native_host_build.executable_path)
        native_host_key = os.path.normcase(str(native_host_exe))
        for path, expected_sha in pins.items():
            actual_sha, actual_size = _hash_file_and_size(path)
            if actual_sha != expected_sha:
                raise ValueError(f'pinned source/image SHA-256 mismatch: {path}')
            if os.path.normcase(path) == core_key and actual_size != profile.image_size_bytes:
                raise ValueError('selected Core byte size differs from the execution-image profile')
            if (os.path.normcase(path) == native_host_key and
                    actual_size != profile.native_host_build.executable_size_bytes):
                raise ValueError('selected native-host executable size differs from its build pin')
        _verify_capture_manifest(profile, root)
        _verify_interface_contract(profile, root)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            json.JSONDecodeError) as exc:
        if isinstance(exc, ExecutionImageVerificationError):
            raise
        raise ExecutionImageVerificationError(f'static execution-image verification failed: {exc}') from exc

    return ExecutionImageVerification(
        profile_id=profile.id,
        image_sha256=profile.image_sha256,
        reference_core_sha256=profile.reference_core_sha256,
        path=profile.path,
        manifest_sha256=profile.correspondence_manifest_sha256,
        native_host_executable_sha256=profile.native_host_build.executable_sha256,
        native_host_build_record_sha256=profile.native_host_build.build_record_sha256,
        native_host_build_manifest_sha256=profile.native_host_build.source_manifest_sha256,
        verified_groups=tuple((
            *profile.covered_groups, *profile.matched_interface_groups,
            *profile.matched_build_groups,
        )),
        missing_groups=(),
        executable=True,
        admission_scope='bounded_native_trial',
        game_qualified=False,
        native_execution_performed=False,
        limitations=profile.limitations,
    )


__all__ = [
    'ExecutionImageVerification',
    'ExecutionImageVerificationError',
    'ExecutionImageProfile',
    'ImageFileIdentity',
    'NativeHostBuildReference',
    'SourceProofReference',
    'from_identity',
    'identity',
    'known_path',
    'runtime_source_pins',
    'select',
    'source_dependencies',
    'verify',
]

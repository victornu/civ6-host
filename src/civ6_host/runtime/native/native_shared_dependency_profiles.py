"""Exact shared-DLL identities and selected interface maps for current Cores.

This profile keeps the installed bytes distinct from their older interface
reference. It validates paths and file hashes only; it does not load a DLL or
claim that native initialization has succeeded.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from civ6_host.runtime.execution_images import select_pair
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path

PROFILE_ID = 'xp2-shared-dependencies-current-092abfbb'
ACTUAL_IMAGE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
INTERFACE_REFERENCE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
EVIDENCE_PATH = Path('work/bbg751-turn-source-scope/shared-dependencies/current-shared-dependency-interfaces-v1.json')
EVIDENCE_SHA256 = 'a4de406dfbbed460af4ed2b15b7cb4d75afc610e3f9268838b65a65fc9a069c9'
_EVIDENCE = None


def _lab_root() -> Path:
    source = _resolve_resource_path(Path(_historical_source_file('civ6rl/native_core_context_profiles.py'))).resolve()
    return source.parents[1]


def _evidence():
    global _EVIDENCE
    if _EVIDENCE is None:
        row = load_pinned_json(_lab_root() / EVIDENCE_PATH, EVIDENCE_SHA256)
        if row.get('schema') != 'civ6-host.shared-dependency-interface-current.v1':
            raise RuntimeError('unexpected shared dependency interface evidence schema')
        pair = row.get('engine_pair', {})
        if (pair.get('actual_image_sha256'), pair.get('interface_reference_sha256')) != (ACTUAL_IMAGE_SHA256, INTERFACE_REFERENCE_SHA256):
            raise RuntimeError('shared dependency evidence image pair differs from the selected profile')
        _EVIDENCE = row
    return _EVIDENCE


@dataclass(frozen=True)
class NativeSharedDependencyProfile:
    profile_id: str
    actual_image_sha256: str
    interface_reference_sha256: str
    directory: Path
    dependency_sha256: Mapping[str, str]
    interface_evidence_sha256: str
    localization_export_rvas: Mapping[str, int]
    havok_export_rvas: Mapping[str, int]
    database_interface: Mapping[str, object]
    havok_shim_rva_mismatches: int

    def verify_files(self) -> Mapping[str, Path]:
        """Recheck the exact three shared files and return their pinned paths."""
        try:
            selected = select_pair(self.actual_image_sha256, self.interface_reference_sha256)
        except ValueError as exc:
            raise ValueError('shared dependency profile image/reference pair changed') from exc
        if self.profile_id != selected.id.replace('-gamecore-', '-shared-dependencies-', 1):
            raise ValueError('execution-image profile does not match the shared dependency profile')
        expected_directory = _resolve_resource_path(Path(selected.shared_dependencies[0].path)).resolve().parent
        if _normalized(self.directory) != _normalized(expected_directory):
            raise ValueError('shared dependency directory differs from the selected execution image')
        result = {}
        for entry in selected.shared_dependencies:
            path = _resolve_resource_path(Path(entry.path)).resolve()
            if _normalized(path.parent) != _normalized(self.directory):
                raise RuntimeError('shared dependency paths do not share the selected directory')
            actual = _sha256_file(path)
            if actual != entry.sha256 or self.dependency_sha256.get(entry.name) != actual:
                raise ValueError(f'shared dependency hash mismatch: {entry.name}')
            result[entry.name] = path
        if set(result) != set(self.dependency_sha256) or len(result) != 3:
            raise RuntimeError('shared dependency profile is incomplete')
        return MappingProxyType(result)

    def verify_library_path(self, name: str, candidate: str | os.PathLike[str]) -> Path:
        """Return a selected DLL path only when the caller names the pinned file."""
        if type(name) is not str or not name:
            raise ValueError('dependency name must be explicit')
        paths = self.verify_files()
        expected = paths.get(name)
        if expected is None:
            raise ValueError(f'unknown shared dependency: {name!r}')
        if _normalized(candidate) != _normalized(expected):
            raise ValueError(f'{name} path differs from the selected shared dependency')
        return expected


def _normalized(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(str(_resolve_resource_path(Path(path)).resolve()))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def profile_for_shared_dependencies(directory: str | os.PathLike[str], *, actual_image_sha256: str,
                                    interface_reference_sha256: str) -> NativeSharedDependencyProfile:
    """Select the exact Steam DLL set for an explicit current/reference pair."""
    selected = select_pair(actual_image_sha256, interface_reference_sha256)
    directory = _resolve_resource_path(Path(directory)).resolve()
    evidence = _evidence()
    record_directory = _resolve_resource_path(Path(evidence['install_directory'])).resolve()
    if _normalized(directory) != _normalized(record_directory):
        raise ValueError('shared dependency directory is not the captured Steam Base directory')
    dependencies = {entry.name: entry.sha256 for entry in selected.shared_dependencies}
    evidence_hashes = {name: row['current_sha256'] for name, row in evidence['libraries'].items()}
    if dependencies != evidence_hashes:
        raise RuntimeError('execution-image dependency pins differ from the interface receipt')
    localization = evidence['localization_interface']['selected_exports']
    havok_record = evidence['havok_interface']
    havok = (*havok_record['host_thread_imports'], *havok_record['additional_direct_exports'])
    localization_rvas = {row['name']: int(row['current_rva'], 16) for row in localization}
    havok_rvas = {row['name']: int(row['current_rva'], 16) for row in havok}
    profile = NativeSharedDependencyProfile(
        profile_id=selected.id.replace('-gamecore-', '-shared-dependencies-', 1),
        actual_image_sha256=actual_image_sha256,
        interface_reference_sha256=interface_reference_sha256,
        directory=directory,
        dependency_sha256=MappingProxyType(dependencies),
        interface_evidence_sha256=EVIDENCE_SHA256,
        localization_export_rvas=MappingProxyType(localization_rvas),
        havok_export_rvas=MappingProxyType(havok_rvas),
        database_interface=evidence['database_interface'],
        havok_shim_rva_mismatches=int(evidence['havok_interface']['thread_import_all_old_rvas_rejected_by_current_shim']),
    )
    profile.verify_files()
    return profile

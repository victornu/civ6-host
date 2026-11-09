"""Hash-pinned static profiles for Base, XP1, and XP2 GameCore contexts.

This module selects addresses and shared dependency files from PE evidence. It
does not load a DLL or establish that the selected build can initialize a game.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
import hashlib
import os
import struct
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_shared_dependency_profiles import NativeSharedDependencyProfile
from civ6_host.runtime.native.native_shared_dependency_profiles import profile_for_shared_dependencies
from civ6_host.runtime.execution_images import ExecutionImageProfile
from civ6_host.runtime.execution_images import select as _select_execution_image
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_core_context_profiles.py')))).resolve().parents[1]
_CONTEXT_PROOF_SHA = '6f808ce7420c461ee4e0b7cb1cab46d90c7df4b4c1120cf2958c3477f0773cc1'
_CTOR_PROOF_SHA = '127fdfff335b79415a665c57bb76e2f44a253d42aec27445f6d5fd970269591d'
_CONTEXT_PROOF = _ROOT / 'evidence/native-expansion-context' / f'{_CONTEXT_PROOF_SHA}.json'
_CTOR_PROOF = _ROOT / 'evidence/native-expansion-context-constructors' / f'{_CTOR_PROOF_SHA}.json'
_XP_CONTEXT_MODES = frozenset({'load', 'trace-load', 'context', 'trace-context'})
_DEPENDENCY_NAMES = ('DatabaseDLL_FinalRelease.dll', 'Localization_FinalRelease.dll', 'HavokScript_FinalRelease.dll')

@dataclass(frozen=True)
class NativeCoreContextProfile:
    ruleset: str
    mode: str
    core_path: Path
    core_sha256: str
    create_context_rva: int
    destroy_context_rva: int
    context_vtable_rva: int
    context_vtable_bytes: bytes
    initialized_getter_rva: int
    initialized_getter_bytes: bytes
    shared_dependency_directory: Path
    dependency_sha256: Mapping[str, str]
    reference_core_sha256: str | None = None
    execution_image: ExecutionImageProfile | None = None
    shared_dependency_profile: NativeSharedDependencyProfile | None = None

    @property
    def source_core_sha256(self) -> str:
        """SHA used to select captured ABI/source evidence, distinct from execution."""
        return self.reference_core_sha256 or self.core_sha256

    @property
    def executable(self) -> bool:
        return self.execution_image is None or bool(self.execution_image.executable)


def require_executable_profile(profile: NativeCoreContextProfile) -> None:
    """Reject a statically selected execution image before any native call/allocation."""
    if type(profile) is not NativeCoreContextProfile:
        raise ValueError('Expected an exact native context profile')
    image = profile.execution_image
    if image is None:
        return
    if type(image) is not ExecutionImageProfile:
        raise ValueError('Context profile has an invalid execution-image identity')
    if (image.image_sha256 != profile.core_sha256
            or image.reference_core_sha256 != profile.source_core_sha256
            or _normalized(image.path) != _normalized(profile.core_path)):
        raise ValueError('Context profile actual/reference/path differs from its retained execution image')
    shared = profile.shared_dependency_profile
    if shared is not None and (
            shared.actual_image_sha256 != profile.core_sha256
            or shared.interface_reference_sha256 != profile.source_core_sha256):
        raise ValueError('Context profile differs from its shared dependency identity pair')
    from civ6_host.runtime.execution_images import verify as _verify_execution_image
    try:
        verification = _verify_execution_image(image)
    except ValueError as exc:
        raise ValueError('Execution image lacks required static correspondence: '
                         + ', '.join(getattr(exc, 'missing_groups', ()))) from exc
    if not verification.executable:
        raise ValueError('Execution image is not admitted for native execution')

def _normalized(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(str(_resolve_resource_path(_resolve_resource_path(Path(path))).resolve()))

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with _resolve_resource_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _rva(value: int | str) -> int:
    return int(value, 16) if isinstance(value, str) else int(value)

def _validate_proofs():
    context = load_pinned_json(_CONTEXT_PROOF, _CONTEXT_PROOF_SHA)
    constructors = load_pinned_json(_CTOR_PROOF, _CTOR_PROOF_SHA)
    if context.get('schema') != 'civ6rl.native_expansion_context.static.v1':
        raise RuntimeError('unexpected context evidence schema')
    if constructors.get('schema') != 'civ6rl.native_expansion_context_constructors.static.v1':
        raise RuntimeError('unexpected constructor evidence schema')
    if constructors.get('parent_factory_destructor_proof', {}).get('sha256') != _CONTEXT_PROOF_SHA:
        raise RuntimeError('constructor evidence is not linked to the pinned lifecycle proof')
    if set(context.get('images', {})) != {'base', 'xp1', 'xp2'}:
        raise RuntimeError('context evidence image set changed')
    if set(constructors.get('ruleset_constructor_chains', {})) != {'base', 'xp1', 'xp2'}:
        raise RuntimeError('constructor evidence image set changed')
    return (context, constructors)

def profile_for_core(gamecore_path: str | os.PathLike[str], *, mode: str, shared_dependency_directory: str | os.PathLike[str] | None=None, execution_image=None) -> NativeCoreContextProfile:
    """Return the exact profile for one installed, hash-pinned GameCore image.

    XP1/XP2 are deliberately restricted to load/trace-load/context/trace-context.
    The Base mode policy remains with the existing probe dispatcher.
    """
    if not isinstance(mode, str) or not mode:
        raise ValueError('mode must be a non-empty string')
    requested_core = _resolve_resource_path(_resolve_resource_path(Path(gamecore_path))).resolve()
    requested_sha = _sha256_file(requested_core)
    context, constructors = _validate_proofs()
    selected = None
    for ruleset, entry in context['images'].items():
        if entry['sha256'] == requested_sha:
            selected = (ruleset, entry)
            break
    retained_execution_image = execution_image
    execution_image = None
    reference_sha = None
    if selected is None:
        if retained_execution_image is None:
            raise ValueError(f'unrecognized GameCore SHA-256 without retained execution identity: {requested_sha}')
        try:
            registered = _select_execution_image(retained_execution_image.id,
                                                   core_path=requested_core)
        except (AttributeError, ValueError, TypeError) as exc:
            raise ValueError('Execution image identity is not registered for this Core path') from exc
        if registered is not retained_execution_image:
            raise ValueError('Execution image identity is not the registered retained profile')
        execution_image = retained_execution_image
        if execution_image.image_sha256 != requested_sha:
            raise ValueError('Selected execution image hash differs from installed GameCore')
        reference_sha = execution_image.reference_core_sha256
        context, constructors = _validate_proofs()
        selected = ('xp2', context['images']['xp2'])
    ruleset, image = selected
    if execution_image is not None and ruleset != 'xp2':
        raise ValueError('Execution image identity cannot be attached to a different ruleset')
    if _normalized(requested_core) != _normalized(image['path']):
        raise ValueError('GameCore path does not match the path pinned for this image')
    if ruleset != 'base' and mode not in _XP_CONTEXT_MODES:
        raise ValueError(f'XP context profiles do not admit mode {mode!r}')
    ctor_image = constructors['images'][ruleset]
    expected_source_sha = reference_sha or requested_sha
    if ctor_image['sha256'] != expected_source_sha:
        raise RuntimeError('lifecycle and constructor evidence disagree on GameCore hash')
    lifecycle = context['context_paths'][ruleset]
    constructor = constructors['ruleset_constructor_chains'][ruleset]
    create = lifecycle['factory_export_thunk']
    destroy = lifecycle['destructor_export_thunk']
    if len(bytes.fromhex(create['raw_hex'])) != 5 or len(bytes.fromhex(destroy['raw_hex'])) != 5:
        raise RuntimeError('unexpected context export thunk width')
    if hashlib.sha256(bytes.fromhex(create['raw_hex'])).hexdigest() != create['sha256']:
        raise RuntimeError('factory thunk bytes do not match their capture hash')
    if hashlib.sha256(bytes.fromhex(destroy['raw_hex'])).hexdigest() != destroy['sha256']:
        raise RuntimeError('destructor thunk bytes do not match their capture hash')
    vtable = constructor['context_vtable']
    vtable_bytes = bytes.fromhex(vtable['capture']['raw_hex'])
    if len(vtable_bytes) != 64 or hashlib.sha256(vtable_bytes).hexdigest() != vtable['capture']['sha256']:
        raise RuntimeError('context vtable capture failed integrity validation')
    vtable_rva = _rva(vtable['capture']['rva'])
    getter_rva = _rva(constructor['initialized_state_getter']['body']['start_rva'])
    if vtable['slot_0x38_target_rva'] != hex(getter_rva):
        raise RuntimeError('slot +0x38 getter does not match captured vtable')
    getter_bytes = bytes.fromhex(constructor['initialized_state_getter']['body']['raw_hex'])
    getter_body = constructor['initialized_state_getter']['body']
    if len(getter_bytes) != getter_body['length'] or hashlib.sha256(getter_bytes).hexdigest() != getter_body['sha256']:
        raise RuntimeError('initialized-state getter bytes failed integrity validation')
    dependency_rows = constructors['shared_dependency_locations']['xp1']['dependencies']
    xp2_dependency_rows = constructors['shared_dependency_locations']['xp2']['dependencies']
    if any((dependency_rows.get(name, {}).get('base_path') != xp2_dependency_rows.get(name, {}).get('base_path') or dependency_rows.get(name, {}).get('base_sha256') != xp2_dependency_rows.get(name, {}).get('base_sha256') for name in _DEPENDENCY_NAMES)):
        raise RuntimeError('XP1/XP2 shared-dependency evidence differs')
    expected_directory = _resolve_resource_path(_resolve_resource_path(Path(next(iter(dependency_rows.values()))['base_path'])).parent).resolve()
    chosen_directory = _resolve_resource_path(_resolve_resource_path(Path(shared_dependency_directory))).resolve() if shared_dependency_directory is not None else expected_directory
    if _normalized(chosen_directory) != _normalized(expected_directory):
        raise ValueError('shared dependency directory differs from the pinned Base directory')
    shared_dependency_profile = None
    if execution_image is not None:
        shared_dependency_profile = profile_for_shared_dependencies(
            chosen_directory,
            actual_image_sha256=execution_image.image_sha256,
            interface_reference_sha256=execution_image.reference_core_sha256,
        )
    dep_hashes = {}
    for name in _DEPENDENCY_NAMES:
        row = dependency_rows.get(name)
        if row is None or row.get('expansion_directory_exists') is not False or row.get('base_exists') is not True:
            raise RuntimeError(f'dependency location evidence incomplete for {name}')
        dependency_path = chosen_directory / name
        if _normalized(dependency_path) != _normalized(row['base_path']):
            raise RuntimeError(f'dependency path evidence mismatch for {name}')
        actual = _sha256_file(dependency_path)
        expected_dependency_sha = (shared_dependency_profile.dependency_sha256[name]
                                   if shared_dependency_profile is not None
                                   else row['base_sha256'])
        if actual != expected_dependency_sha:
            raise ValueError(f'shared dependency hash mismatch for {name}')
        dep_hashes[name] = actual
    dependency_hashes: Mapping[str, str] = MappingProxyType(dep_hashes)
    return NativeCoreContextProfile(ruleset=ruleset, mode=mode, core_path=requested_core, core_sha256=requested_sha, create_context_rva=_rva(image['exports']['DllCreateGameContext']['rva']), destroy_context_rva=_rva(image['exports']['DllDestroyGameContext']['rva']), context_vtable_rva=vtable_rva, context_vtable_bytes=vtable_bytes, initialized_getter_rva=getter_rva, initialized_getter_bytes=getter_bytes, shared_dependency_directory=chosen_directory, dependency_sha256=dependency_hashes, reference_core_sha256=reference_sha, execution_image=execution_image, shared_dependency_profile=shared_dependency_profile)

def validate_loaded_modules(profile: NativeCoreContextProfile, module_paths):
    """Verify the actual shared modules before calling any context export."""
    require_executable_profile(profile)
    if profile.shared_dependency_profile is not None:
        shared = profile.shared_dependency_profile
        if ((shared.actual_image_sha256, shared.interface_reference_sha256)
                != (profile.core_sha256, profile.source_core_sha256)
                or dict(shared.dependency_sha256) != dict(profile.dependency_sha256)):
            raise ValueError('Shared dependency profile differs from the selected Core identities')
        shared.verify_files()
    expected = {profile.core_path.name.lower(): (profile.core_path, profile.core_sha256)}
    expected.update({name.lower(): (profile.shared_dependency_directory / name, digest) for name, digest in profile.dependency_sha256.items()})
    matches = {}
    for value in module_paths:
        path = _resolve_resource_path(Path(value))
        name = path.name.lower()
        if name not in expected:
            continue
        target, digest = expected[name]
        if name in matches or _normalized(path) != _normalized(target) or _sha256_file(path) != digest:
            raise ValueError('Loaded native module does not match the selected context profile')
        matches[name] = str(path)
    if set(matches) != set(expected):
        raise ValueError('A required native context module was not loaded')
    return matches

def validate_loaded_context(profile: NativeCoreContextProfile, module_base: int, context_address: int, read):
    """Return only the proved getter address after checking relocated live bytes."""
    if type(module_base) is not int or module_base <= 0 or type(context_address) is not int or (context_address <= 0):
        raise ValueError('Context layout check requires live addresses')
    table_address = module_base + profile.context_vtable_rva
    if read(context_address, 8) != struct.pack('<Q', table_address):
        raise ValueError('Unexpected native context vtable for the selected GameCore')
    pointers = struct.unpack('<8Q', profile.context_vtable_bytes)
    if any((p < 6442450944 for p in pointers)):
        raise ValueError('Context vtable contains an unproven target')
    relocated = struct.pack('<8Q', *(module_base + p - 6442450944 for p in pointers))
    if read(table_address, 64) != relocated:
        raise ValueError('Live context vtable differs from the selected PE')
    address = module_base + profile.initialized_getter_rva
    if read(address, len(profile.initialized_getter_bytes)) != profile.initialized_getter_bytes:
        raise ValueError('Live context initialized-state getter differs from the selected PE')
    return address
__all__ = ['NativeCoreContextProfile', 'profile_for_core', 'require_executable_profile', 'validate_loaded_modules', 'validate_loaded_context']

"""Materialize static source closures for an explicitly selected runtime image.

Image rows in source receipts describe where code was captured. They remain in
those immutable receipts, but are removed from runtime file pins unless the
image is the selected Core. The selected Core is then pinned by its canonical
path and its old ABI reference hash before the execution-image helper projects
that one pin to the installed hash.
"""
from pathlib import Path
from typing import Mapping, Iterable


def materialize_runtime_source_pins(
    pins: Mapping[str, str], *, execution_image=None, provenance_images: Iterable[Mapping[str, str]] = ()
) -> dict[str, str]:
    """Return an independent dependency map for this runtime, preserving None semantics."""
    result = dict(pins)
    if execution_image is None:
        return result

    from .execution_images import identity, runtime_source_pins
    identity(execution_image)
    from .resource_resolution import resolve_path

    core_path = str(Path(execution_image.path).resolve())
    reference_sha = execution_image.reference_core_sha256

    # Captured EXE/other-Core rows are provenance. Remove only their exact
    # recorded file identities; never infer identities from a basename.
    for row in provenance_images:
        path_value, digest = row.get('path'), row.get('sha256')
        if not isinstance(path_value, str) or not isinstance(digest, str):
            raise ValueError('Malformed source image provenance row')
        path = str(Path(resolve_path(path_value)).resolve())
        if path == core_path:
            if digest != reference_sha:
                raise ValueError('Selected Core source image identity conflicts with the profile')
            continue
        if path in result:
            if result[path] != digest:
                raise ValueError('Source image provenance pin conflicts with its receipt')
            del result[path]

    existing = result.get(core_path)
    if existing == execution_image.image_sha256:
        # A parent may aggregate a child that already projected this exact
        # registered image. Accept only that one canonical runtime digest.
        return result
    if existing is not None and existing != reference_sha:
        raise ValueError('Selected Core pin conflicts with its ABI reference identity')
    result[core_path] = reference_sha
    return runtime_source_pins(result, execution_image=execution_image)

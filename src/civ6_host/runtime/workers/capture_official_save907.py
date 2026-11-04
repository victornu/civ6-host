"""Preserve existing game saves and inspect components without launching Civ6."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import argparse
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import sys
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('tools/capture_official_save907.py')))).resolve().parents[1]
from civ6_host.runtime.native.official_save import MAX_SAVE_BYTES
from civ6_host.runtime.native.official_save import inspect_save
from civ6_host.runtime.native.official_save import sha

def capture(source: Path, out: Path) -> dict:
    source = _resolve_resource_path(source).resolve(strict=True)
    before = _resolve_resource_path(source).stat()
    if before.st_size > MAX_SAVE_BYTES:
        raise ValueError('Save exceeds read budget')
    data = _resolve_resource_path(source).read_bytes()
    after = _resolve_resource_path(source).stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Save changed during capture')
    report, sections = inspect_save(data)
    folder = out / report['sha256']
    folder.mkdir()
    (folder / 'source.Civ6Save').write_bytes(data)
    for index, section in enumerate(sections):
        name = f'section-{index:02d}-{section.offset:08x}-{section.kind}.raw'
        (folder / name).write_bytes(section.payload)
        report['sections'][index]['extracted_file'] = name
    current = _resolve_resource_path(source).read_bytes()
    if sha(current) != report['sha256']:
        raise ValueError('Original changed before capture completion')
    report.update(source_path=str(source), source_mtime_ns=before.st_mtime_ns, original_rehashed_unchanged=True, source_copy='source.Civ6Save', captured_at=datetime.now(timezone.utc).isoformat(), matched_database_fixture=None, configuration_component=None, unresolved=['Exact application-configuration component boundary', 'Save-to-final-database and ruleset binding', 'Official-container component Load in dedicated host', 'Post-load lifecycle, actions, observations and reset equivalence'])
    (folder / 'manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return dict(manifest=str((folder / 'manifest.json').relative_to(ROOT)), sha256=report['sha256'], bytes=report['bytes'], sections=len(sections), gamecore_candidate_count=report['gamecore_candidate_count'], ruleset_string_hints=report['ruleset_string_hints'], original_rehashed_unchanged=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = _resolve_resource_path(args.output).resolve()
    if not out.is_relative_to(ROOT / 'work') or _resolve_resource_path(out).exists():
        raise ValueError('Use a fresh directory under project work')
    if len(args.save) > 16:
        raise ValueError('At most 16 saves per capture')
    out.mkdir(parents=True)
    rows = [capture(path, out) for path in args.save]
    result = dict(schema='civ6rl.official_save_capture907.v1', captures=rows, game_launched=False, native_load_attempted=False, strategic_training_ready=False)
    (out / 'index.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
if __name__ == '__main__':
    main()

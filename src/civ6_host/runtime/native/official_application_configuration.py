"""Derive the application provider from its official serialized prelude.

No save-specific offsets, scanning for GAME_ROOT, or caller-supplied slices.
The surrounding container is not fully decoded; ambiguous/unsupported framing
is refused and native Load compatibility remains a separate requirement.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib
import json
from civ6_host.runtime.native.official_configuration import read_provider
from civ6_host.runtime.native.official_save import inspect_save
from civ6_host.runtime.native.official_saved_content import inspect_content
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/official_application_configuration.py')))).resolve().parents[1]
SOURCE_PATH = 'work/official-bundle/application-configuration-source.json'
SOURCE_SHA256 = '8abf5216307f4a0be408a7aca846ed1cc04e040254b41ee5f4ce584a633f987a'
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PREFIX = bytes.fromhex('1000000001000000')
MARKER = b'\x01\x00\x00\x00'
FLAGS = {676943257, 2134403239, 3972952662}
MAX_CONFIGURATION_BYTES = 1024 * 1024

def verify_source():
    raw = _resolve_resource_path(ROOT / SOURCE_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Application configuration framing source changed')
    proof = json.loads(raw)
    if proof['image']['sha256'] != EXE_SHA256 or proof['prefix_constants']['raw_hex'] != PREFIX.hex() or proof['marker']['raw_hex'] != MARKER.hex():
        raise ValueError('Application configuration framing source differs')
    return dict(path=SOURCE_PATH, sha256=SOURCE_SHA256, executable_sha256=EXE_SHA256)

def extract_application_configuration(data: bytes):
    """Return exact provider bytes plus source-derived boundaries and hashes."""
    source = verify_source()
    container, sections = inspect_save(data)
    games = [section for section in sections if section.kind == 'gamecore_stream_candidate']
    if len(games) != 1:
        raise ValueError('One identified GameCore stream candidate required')
    game = games[0]
    matches, searched, position = ([], 0, 0)
    while True:
        position = data.find(PREFIX, position, game.offset)
        if position < 0:
            break
        start = position
        position += len(PREFIX)
        searched += 1
        if searched > 512:
            raise ValueError('Too many application configuration framing candidates')
        if any((section.offset <= start < section.end for section in sections)):
            continue
        try:
            header, consumed = read_provider(data[position:position + 128])
        except ValueError:
            continue
        if len(header) != 3 or len({v.key for v in header}) != 3 or {v.key for v in header} != FLAGS or any(((v.tag, v.extra, v.flags, v.size) != (1, 0, 0, 0) or v.scalar() not in (0, 1) for v in header)):
            continue
        flags = {v.key: v.scalar() for v in header}
        if flags[676943257] != 1 or flags[3972952662] != 1:
            raise ValueError('Unsupported official application prelude flags')
        marker = position + consumed
        if data[marker:marker + 4] != MARKER:
            raise ValueError('Application provider version marker differs')
        provider_start = marker + 4
        window = data[provider_start:min(provider_start + MAX_CONFIGURATION_BYTES, game.offset)]
        _, length = read_provider(window)
        provider_end = provider_start + length
        if any((start < section.end and provider_end > section.offset for section in sections)):
            raise ValueError('Application framing overlaps a compressed component')
        payload = window[:length]
        content = inspect_content(payload)
        matches.append((payload, dict(start=provider_start, end=provider_end, prelude_start=start, prelude_flags={hex(k): flags[k] for k in sorted(flags)}, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), save_sha256=container['sha256'], source=source, content_declaration=content, gamecore_section_offset=game.offset, gamecore_payload_sha256=game.receipt()['payload_sha256'], identity_method='unique_official_application_write_prelude_outside_compressed_sections', full_container_decoded=False, native_load_qualified=False)))
    if len(matches) != 1:
        raise ValueError('Exactly one unambiguous official application provider required')
    return matches[0]

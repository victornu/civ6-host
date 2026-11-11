"""Static proofs for exact XP2 optional achievement callback paths."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-v2.json",
    "75c84663fd822c1f0a7308dda39ad474fbcc7492ca567428579742f249b585d8",
)
FORMATION_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-formation-v1.json",
    "bbe7b27f73b23fdfcf7e3046a6f0534c27c1f44da41c937f3109a2c9557d81ef",
)
ERA_TRANSITION_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-era-transition-v1.json",
    "569c172f91b1b945ef561e6fd7104dca9b3cf14ef2e4bca00ade8aafdae49a8d",
)
ERA_TRANSITION_PREFIX = ("0x17f098", "0x177737", "0xda763", "0x284c4d")
_ERA_TRANSITION_LITERAL = b"NEW_ACHIEVEMENT_4_20\0"
RAF30_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-raf30-v1.json",
    "921975e3a4d88c6676e9e79f2f70568725de52be3e655b24082a558c9f9aa4a3",
)
RAF30_PREFIX = ("0x17f098", "0x17ad1c", "0xda763", "0x285abe")
_RAF30_LITERAL = b"RAF_ACHIEVEMENT_30\0"
CITY_LISTENER_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-city-listener-v1.json",
    "470ef25a36de360294366c9ec3622141cf219ba501a6c56a3e9f2c4cc30c4216",
)
NATIVE02_SOURCE = (
    "work/host-extensions/xp2-host-slot20-static/source-profile-native02-v1.json",
    "eeeccad843287fccfd356155369fc3aa5e9250bb2816321e795c39e27f032d71",
)
CITY_LISTENER_PREFIX = ("0x17f098", "0x178ed0", "0x25c54c", "0x25d3f1", "0x25d459")
CITY_CAPTURE_LISTENER_SOURCE = (
    'evidence/host-xp2-previous-owner-capture-achievement-source.json',
    '457b32250afb749a40cd9bbf6e7e4f3f2bff4d72e107ef145a7cd7ee528997dd',
)
CITY_CAPTURE_LISTENER_PREFIX = CITY_LISTENER_PREFIX[:4] + ('0x144325', '0x151b0c')
NATIVE02_PREFIX = ("0x17f098", "0x17feda", "0x2e9e8c")
NATIVE02_OBSERVED_CHAIN = ("0x17f098", "0x17feda", "0x2e9e8c", "0x2eda33", "0x2ead5b",
    "0x2eadb4", "0x447ffe", "0x447dc8", "0x447e33", "0x42e2c6", "0x401537",
    "0x5cacd", "0x5e343", "0x4b172", "0x63e2e9")
NATIVE02_OBSERVED_CHAIN_BODY_STARTS = ("0x17f060", "0x17fe80", "0x2e9de0", "0x2ed850",
    "0x2eaaa0", "0x2ead90", "0x447fb0", "0x447d70", "0x447df0", "0x42dc40",
    "0x4012f0", "0x5ca80", "0x5e2d0", "0x4afc0", "0x63e2e0")
_CITY_LISTENER_LITERAL = b"NEW_ACHIEVEMENT_4_14\0"
FORMATION_CORE_RETURN_PREFIX = ("0x17f098", "0x17fa97", "0x226ed4", "0x1a33a5", "0x65a217")
_FORMATION_LITERAL = b"NEW_ACHIEVEMENT_4_13\0"
CONGRESS_SOURCE = (
    "work/trade-common-client/congress-achievement-staging/source.json",
    "1d3df505be559ae348892048c8985586845f55ea13867a526d4cfe730fb16906",
)
CONGRESS_PREFIX = ("0x17f098", "0x17cdc6", "0x3bc6b9", "0x3bf934")
_CONGRESS_DATA = (
    (0x9d0678, b"VSV_ACHIEVEMENT_21\0"),
    (0x9c46f8, b"PlayerType\0"),
    (0x9d0650, b"APPLY_DECREASED_DIPLO_VP_TO_PLAYER\0"),
)
RAF35_SOURCE = (
    'evidence/host-xp2-stock-t61-achievement-frontier.json',
    '8f2cb0ad3a5106e9c93a0b1c671d8654ac32db258955c36fac936c00eea85064',
)
RAF35_PREFIX = ('0x17f098', '0x17fd22', '0xfc253', '0x1e2e97')
_RAF35_LITERAL = b'RAF_ACHIEVEMENT_35\0'
CORE_MODULE = "GameCore_XP2_FinalRelease.dll"
EXE_SHA256 = "e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63"
HOST_GLOBAL_RVA = 0xB8AA80
ACCEPTED_CORE_RETURN_PREFIX = ("0x17f098", "0x17b387", "0x35b0dc", "0x24025b")
MAX_READ_BYTES = 4096


def _verify_body(body: dict, label: str) -> int:
    if body.get("fragments"):
        pieces = []
        for fragment in body["fragments"]:
            raw = bytes.fromhex(fragment["raw_hex"])
            if (len(raw) != fragment.get("length")
                    or hashlib.sha256(raw).hexdigest() != fragment.get("sha256")):
                raise ValueError("XP2 host+20 source fragment digest changed: " + label)
            cursor = int(fragment["start_rva"], 16)
            for row in fragment.get("instructions", ()):
                code = bytes.fromhex(row["bytes"])
                if (not code or int(row["rva"], 16) != cursor
                        or raw[cursor - int(fragment["start_rva"], 16):
                               cursor - int(fragment["start_rva"], 16) + len(code)] != code):
                    raise ValueError("XP2 host+20 instruction map changed: " + label)
                cursor += len(code)
            if cursor != int(fragment["start_rva"], 16) + len(raw):
                raise ValueError("XP2 host+20 source tail changed: " + label)
            pieces.append(raw)
        complete = b"".join(pieces)
        if (len(complete) != body.get("length")
                or hashlib.sha256(complete).hexdigest() != body.get("sha256")):
            raise ValueError("XP2 host+20 chained body changed: " + label)
        rows = [row for fragment in body["fragments"] for row in fragment["instructions"]]
    else:
        raw = bytes.fromhex(body["raw_hex"])
        if (len(raw) != body.get("length")
                or hashlib.sha256(raw).hexdigest() != body.get("sha256")
                or "".join(row["bytes"] for row in body.get("instructions", ())) != raw.hex()):
            raise ValueError("XP2 host+20 source body changed: " + label)
        rows = body["instructions"]
    if not rows:
        raise ValueError("XP2 host+20 source has no instruction bytes: " + label)
    return len(rows)


def source() -> dict:
    proof = _source(SOURCE)
    if (proof.get("schema") != "civ6-host.xp2-host-slot20-achievement-attempt13.static.v2"
            or proof.get("images", {}).get("xp2", {}).get("sha256") != XP2_CORE_SHA256
            or proof.get("images", {}).get("exe", {}).get("sha256") != EXE_SHA256
            or proof.get("contract", {}).get("host_slot") != "0x20"
            or proof.get("contract", {}).get("host_global_rva") != "0xb8aa80"
            or tuple(proof.get("contract", {}).get("accepted_core_return_prefix", ()))
               != ACCEPTED_CORE_RETURN_PREFIX
            or proof.get("contract", {}).get("only_this_observed_propagating_site_admitted") is not True
            or proof.get("contract", {}).get("other_propagated_or_consumed_callers_admitted") is not False
            or proof.get("validation", {}).get("native_execution") is not False
            or proof.get("validation", {}).get("process_memory_read") is not False
            or proof.get("validation", {}).get("runtime_modified") is not False
            or len(proof.get("bodies", {})) != 5):
        raise ValueError("XP2 host+20 source identity changed")
    refs = proof.get("references", ())
    if not refs:
        raise ValueError("XP2 host+20 source references are missing")
    for ref in refs:
        path = _path(ref["path"])
        if (not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]):
            raise ValueError("XP2 host+20 source reference changed: " + ref["path"])
    for name, body in proof["bodies"].items():
        _verify_body(body, name)
    # These source joins are the point of the narrow exception: the callback
    # result may leave the helper's method, but the actual parent consumer
    # overwrites RAX before its first read.
    expected = {
        "helper_17f060": ("0x17f095", "call qword ptr [rax + 0x20]"),
        "method_17b190": ("0x17b382", "call 0x18017f060"),
        "owner_35b080": ("0x35b0d9", "call qword ptr [rax + 0x10]"),
        "consumer_240220": ("0x240256", "call 0x18035b080"),
        "consumer_getter_306b80": ("0x306b80", "mov rax, qword ptr [rip + 0x8875b9]"),
    }
    for name, (rva, text) in expected.items():
        rows = [row for body in (proof["bodies"][name],)
                for row in (row for frag in body.get("fragments", ())
                            for row in frag["instructions"])]
        if not rows:
            rows = proof["bodies"][name]["instructions"]
        matches = [row for row in rows if row["rva"] == rva]
        if len(matches) != 1 or matches[0].get("text") != text:
            raise ValueError("XP2 host+20 caller source join changed: " + name)
    return proof


def formation_source() -> dict:
    proof = _source(FORMATION_SOURCE)
    contract = proof.get("contract", {})
    bodies = proof.get("bodies", {})
    if (proof.get("schema") != "civ6-host.xp2-host-slot20-formation.static.v1"
            or proof.get("images") != {"xp2": XP2_CORE_SHA256, "exe": EXE_SHA256}
            or tuple(contract.get("accepted_core_return_prefix", ())) != FORMATION_CORE_RETURN_PREFIX
            or contract.get("shared_parent_sha256") != SOURCE[1]
            or contract.get("absent_service_result") != "null"
            or contract.get("platform_request_submitted") is not False
            or contract.get("platform_success_reported") is not False
            or contract.get("guarded_lifetime_and_thread_required") is not True
            or proof.get("literal") != {"rva": "0x9ceee0", "raw_hex": _FORMATION_LITERAL.hex()}
            or proof.get("listener_vtable") != {"slot_rva": "0x9d1020", "slot": "0x10",
                "target_rva": "0x17fa50", "file_pointer_hex": "50fa178001000000"}
            or proof.get("validation") != {"native_execution": False, "process_memory_read": False,
                                           "runtime_modified": False}):
        raise ValueError("XP2 formation achievement source identity changed")
    expected = {
        "listener_17fa50": ("0x17fa92", "call 0x18017f060"),
        "dispatcher_226e80": ("0x226ed1", "call qword ptr [rax + 0x10]"),
        "producer_1a3290": ("0x1a33a0", "call 0x180226e80"),
        "consumer_65a170": ("0x65a217", "call 0x1800408f0"),
        "getter_0408f0": ("0x4093d", "xor eax, eax"),
    }
    if set(bodies) != set(expected):
        raise ValueError("XP2 formation achievement source bodies changed")
    for name, (rva, text) in expected.items():
        body = bodies[name]
        _verify_body(body, name)
        if sum(row["rva"] == rva and row["text"] == text for frag in body["fragments"]
               for row in frag["instructions"]) != 1:
            raise ValueError("XP2 formation achievement return join changed: " + name)
    return proof


def era_transition_source() -> dict:
    proof = _source(ERA_TRANSITION_SOURCE)
    if (proof["schema"] != "civ6-host.xp2-host-slot20-era-transition.static.v1"
            or proof["images"] != {"xp2": XP2_CORE_SHA256, "exe": EXE_SHA256}
            or tuple(proof["prefix"]) != ERA_TRANSITION_PREFIX
            or proof["literal"] != {"rva": "0x9ceb28", "raw_hex": _ERA_TRANSITION_LITERAL.hex()}
            or proof["native_execution"] is not False
            or proof["platform_success_reported"] is not False):
        raise ValueError("XP2 era-transition achievement source changed")
    expected = {
        "0x177710": (("0x177723", "lea r8, [rip + 0x8573fe]"),
                     ("0x177732", "call 0x18017f060"),
                     ("0x17773d", "call 0x180044f00")),
        "0xda753": (("0xda760", "call qword ptr [rax + 0x10]"),
                    ("0xda763", "mov rdi, rbx"),
                    ("0xda766", "mov rbx, qword ptr [rbx]")),
        "0x284c3f": (("0x284c48", "call 0x1800da700"),
                     ("0x284c4d", "mov rax, qword ptr [rdi + 0x90]")),
    }
    if set(proof["bodies"]) != set(expected):
        raise ValueError("XP2 era-transition achievement windows changed")
    for name, joins in expected.items():
        body = proof["bodies"][name]
        _verify_body(body, name)
        if body["start_rva"] != name or not set(joins) <= {
                (row["rva"], row["text"]) for row in body["instructions"]}:
            raise ValueError("XP2 era-transition achievement call join changed")
    return proof


def raf30_source() -> dict:
    proof = _source(RAF30_SOURCE)
    if (proof["schema"] != "civ6-host.xp2-host-slot20-raf30.static.v1"
            or proof["core_sha256"] != XP2_CORE_SHA256
            or tuple(proof["prefix"]) != RAF30_PREFIX
            or proof["literal"] != {"rva": "0x9d0288", "raw_hex": _RAF30_LITERAL.hex()}
            or proof["native_execution"] is not False
            or proof["platform_success_reported"] is not False):
        raise ValueError("XP2 RAF30 achievement source changed")
    expected = {
        "0x17acf0": {("0x17ad0d", "lea r8, [rip + 0x855574]"),
                     ("0x17ad17", "call 0x18017f060"),
                     ("0x17ad1f", "call 0x18016f6f0")},
        "0x285a9d": {("0x285ab9", "call 0x1800da700"),
                     ("0x285abe", "mov rax, qword ptr [rbx + 0x90]")},
    }
    if set(proof["bodies"]) != set(expected):
        raise ValueError("XP2 RAF30 achievement windows changed")
    for name, joins in expected.items():
        body = proof["bodies"][name]
        _verify_body(body, name)
        if body["start_rva"] != name or not joins <= {
                (row["rva"], row["text"]) for row in body["instructions"]}:
            raise ValueError("XP2 RAF30 achievement call join changed")
    return proof


def city_listener_source() -> dict:
    proof = _source(CITY_LISTENER_SOURCE)
    if (proof["schema"] != "civ6-host.xp2-host-slot20-city-listener.static.v1"
            or proof["core_sha256"] != XP2_CORE_SHA256
            or tuple(proof["prefix"]) != CITY_LISTENER_PREFIX
            or proof["literal"] != {"rva": "0x9cee08", "raw_hex": _CITY_LISTENER_LITERAL.hex()}
            or proof["native_execution"] is not False
            or proof["platform_success_reported"] is not False):
        raise ValueError("XP2 city listener achievement source changed")
    joins = {
        "0x178eaf": {("0x178ebd", "lea r8, [rip + 0x855f44]"),
                     ("0x178ecb", "call 0x18017f060"),
                     ("0x178ed0", "test r15, r15")},
        "0x25c53e": {("0x25c549", "call qword ptr [rax + 0x10]"),
                     ("0x25c54c", "mov rdi, rbx")},
        "0x25d3df": {("0x25d3ec", "call 0x18025c4f0"),
                     ("0x25d3f1", "mov rdx, rbx")},
        "0x25d430": {("0x25d454", "call 0x18025d270"),
                     ("0x25d459", "add rsp, 0x38")},
    }
    if set(proof["bodies"]) != set(joins):
        raise ValueError("XP2 city listener achievement windows changed")
    for name, required in joins.items():
        body = proof["bodies"][name]
        _verify_body(body, name)
        if body["start_rva"] != name or not required <= {
                (row["rva"], row["text"]) for row in body["instructions"]}:
            raise ValueError("XP2 city listener achievement call join changed")
    return proof


def native02_source() -> dict:
    """Verify the exact XP2 callback and receiver that safely ignore null."""
    proof = _source(NATIVE02_SOURCE)
    contract = proof.get("contract", {})
    if (proof.get("schema") != "civ6-host.xp2-host-slot20-native02.static.v1"
            or proof.get("images", {}).get("xp2", {}).get("sha256") != XP2_CORE_SHA256
            or proof.get("parent_profile", {}).get("sha256") != SOURCE[1]
            or tuple(contract.get("accepted_core_return_prefix", ())) != NATIVE02_PREFIX
            or tuple(contract.get("observed_core_return_chain", ())) != NATIVE02_OBSERVED_CHAIN
            or contract.get("shared_parent_sha256") != SOURCE[1]
            or contract.get("host_slot") != "0x20"
            or contract.get("host_global_rva") != "0xb8aa80"
            or contract.get("platform_service_installed") is not False
            or contract.get("platform_request_submitted") is not False
            or contract.get("platform_success_reported") is not False
            or proof.get("validation", {}).get("native_execution") is not False
            or proof.get("validation", {}).get("process_memory_read") is not False
            or proof.get("validation", {}).get("runtime_modified") is not False
            or set(proof.get("bodies", {})) != set(NATIVE02_OBSERVED_CHAIN_BODY_STARTS)):
        raise ValueError("XP2 native02 host+20 source identity changed")
    for ref in proof.get("references", ()):
        path = _path(ref["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("XP2 native02 source reference changed: " + ref["path"])
    trace = proof.get("trace", {})
    trace_path = _path(trace.get("path", ""))
    matches = []
    for line in trace_path.read_bytes().splitlines(keepends=True):
        try:
            row = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (row.get("stage") == "unsupported_host_contract" and row.get("slot") == "0x20"
                and "Unproved XP2 optional achievement caller chain" in row.get("error", "")):
            matches.append((line, row))
    if (len(matches) != 1 or hashlib.sha256(matches[0][0]).hexdigest() != trace.get("line_sha256")
            or tuple(row["rva"] for row in matches[0][1].get("native_stack", ())
                     if row.get("module") == CORE_MODULE) != NATIVE02_OBSERVED_CHAIN):
        raise ValueError("XP2 native02 trace evidence changed")
    for name, body in proof["bodies"].items():
        _verify_body(body, name)
    joins = {
        "0x17fe80": {("0x17fed5", "call 0x18017f060"),
                     ("0x17feda", "mov rbp, qword ptr [rsp + 0x38]"),
                     ("0x17fee9", "ret")},
        "0x2e9de0": {("0x2e9e89", "call qword ptr [rax + 0x10]"),
                     ("0x2e9e8c", "mov rdi, rbx")},
    }
    for start, required in joins.items():
        rows = [row for fragment in proof["bodies"][start].get("fragments", ())
                for row in fragment.get("instructions", ())]
        if not required <= {(row["rva"], row["text"]) for row in rows}:
            raise ValueError("XP2 native02 helper/callback/receiver join changed: " + start)
    receiver_rows = [row for fragment in proof["bodies"]["0x2e9de0"].get("fragments", ())
                     for row in fragment.get("instructions", ())]
    receiver_rows.sort(key=lambda row: int(row["rva"], 16))
    call_index = next(i for i, row in enumerate(receiver_rows) if row["rva"] == "0x2e9e89")
    first_rax = next(row for row in receiver_rows[call_index + 1:]
                     if re.search(r"\b(?:rax|eax|ax|al|ah)\b", row["text"]))
    if first_rax["text"] != "mov rax, qword ptr [rcx]":
        raise ValueError("XP2 native02 receiver reads callback result before overwrite")
    return proof


def congress_source(execution_image):
    """Current-image resolution finalization; historical source stays separate."""
    from .a0_policy_unlock_current import (
        _require_image, CURRENT_PROFILE_ID, CURRENT_CORE_SHA256, CURRENT_EXE_SHA256)
    _require_image(execution_image)
    proof = _source(CONGRESS_SOURCE)
    contract = proof.get('contract', {})
    if (proof.get('schema') != 'civ6-host.xp2-congress-achievement-absence.static.v1'
            or proof.get('execution_profile') != dict(id=CURRENT_PROFILE_ID,
                core_sha256=CURRENT_CORE_SHA256, executable_sha256=CURRENT_EXE_SHA256,
                reference_core_sha256=XP2_CORE_SHA256)
            or proof.get('static_only') is not True
            or any(proof.get(k) is not False for k in
                   ('native_execution', 'process_memory_read', 'runtime_modified'))
            or tuple(contract.get('accepted_core_return_prefix', ())) != CONGRESS_PREFIX
            or contract.get('host_slot') != '0x20'
            or contract.get('host_global_rva') != '0xb8aa80'
            or contract.get('absent_service_result') != 'null'
            or any(contract.get(k) is not False for k in ('service_installed',
                'platform_request_submitted', 'platform_success_reported',
                'caller_result_consumed', 'historical_image_new_route_admitted'))):
        raise ValueError('XP2 Congress achievement source identity changed')
    expected = {
        '0x17f060': (('0x17f095', 'call qword ptr [rax + 0x20]'),
                    ('0x17f09b', 'test rax, rax'), ('0x17f09e', 'je 0x18017f0f1')),
        '0x17cd00': (('0x17cdc1', 'call 0x18017f060'),
                    ('0x17cdc6', 'add rbx, 8')),
        '0x3bc650': (('0x3bc6b6', 'call qword ptr [rax + 0x10]'),
                    ('0x3bc6b9', 'mov rdi, rbx')),
        '0x3bf880': (('0x3bf928', 'add rcx, 0xbb8'),
                    ('0x3bf92f', 'call 0x1803bc650'),
                    ('0x3bf934', 'mov rdx, rbx'), ('0x3bf937', 'mov rcx, r14'),
                    ('0x3bf93a', 'call 0x1803bbac0')),
        'thunk_17fac0': (('0x17fac7', 'jmp 0x18017cd00'),),
        'delegate_ctor_16bd00': (('0x16bd00', 'lea rax, [rip + 0x8655d9]'),),
        'registration_17ec64': (('0x17ec6b', 'call 0x18016bd00'),
                               ('0x17ec73', 'lea rcx, [rsi + 0xbb8]')),
    }
    if set(proof.get('bodies', {})) != set(expected):
        raise ValueError('XP2 Congress achievement body set changed')
    for name, joins in expected.items():
        body = proof['bodies'][name]
        _verify_body(body, name)
        rows = [r for f in body.get('fragments', ()) for r in f['instructions']]
        rows = rows or body['instructions']
        if not set(joins) <= {(r['rva'], r['text']) for r in rows}:
            raise ValueError('XP2 Congress achievement call join changed')
    if proof['bodies']['0x17f060']['sha256'] != source()['bodies']['helper_17f060']['sha256']:
        raise ValueError('XP2 Congress no longer uses the shared null-service helper')
    data = proof.get('data', ())
    if ([(int(r['rva'],16),bytes.fromhex(r['raw_hex'])) for r in data[:3]] != list(_CONGRESS_DATA)
            or len(data) != 4 or data[3] != dict(name='callback_vtable_slot',
                rva='0x9d12f0',target_rva='0x17fac0',raw_hex=(0x18017fac0).to_bytes(8,'little').hex())):
        raise ValueError('XP2 Congress achievement literal or delegate changed')
    return proof


def raf35_source(execution_image):
    from .a0_policy_unlock_current import _require_image

    _require_image(execution_image)
    proof = _source(RAF35_SOURCE)
    spans = {name: (span['rva'], span['bytes']) for name, span in proof['spans'].items()}
    if (proof['schema'] != 'civ6-host.xp2-stock-t61-achievement-frontier.v1'
            or proof['core']['sha256'] != execution_image.image_sha256
            or tuple(proof['refusal']['core_return_stack'][:len(RAF35_PREFIX)]) != RAF35_PREFIX
            or proof['refusal']['slot'] != '0x20'
            or proof['literal'] != dict(rva='0x9d0400', text='RAF_ACHIEVEMENT_35',
                sha256=hashlib.sha256(_RAF35_LITERAL).hexdigest())
            or proof['listener_vtable_slot'] != dict(rva='0x9d0a50', target_rva='0x17fcd0', relocatable=True)
            or spans != {
                'optional_service_helper': ('0x17f060', 176),
                'platform_listener': ('0x17fcd0', 93),
                'native_delegate_dispatch': ('0xfc214', 264),
                'event_producer_join': ('0x1e2e18', 229),
            }
            or proof['claimed_achievement_success'] is not False):
        raise ValueError('Current XP2 RAF35 achievement source differs')
    return proof


def city_capture_listener_source(execution_image):
    from .a0_policy_unlock_current import _require_image

    _require_image(execution_image)
    proof = _source(CITY_CAPTURE_LISTENER_SOURCE)
    spans = {name: (row['rva'], row['bytes']) for name, row in proof['spans'].items()}
    if (proof['schema'] != 'civ6-host.xp2-host-slot20-city-capture-listener.v1'
            or proof['image']['sha256'] != execution_image.image_sha256
            or proof['shared_city_listener']['sha256'] != CITY_LISTENER_SOURCE[1]
            or proof['observed_prefix'] != CITY_CAPTURE_LISTENER_PREFIX
            or proof['refusal']['chain'] != CITY_CAPTURE_LISTENER_PREFIX
            or proof['slot'] != '0x20' or proof['return_path'] != 'native_null_optional_achievement'
            or proof['platform_success_reported'] is not False
            or proof['gameplay_result_is_separate'] is not True
            or spans != {'transfer_calls_city_listener': ('0x144311', 0x33),
                         'combat_calls_city_transfer': ('0x151afb', 0x34)}):
        raise ValueError('Current XP2 city capture achievement source differs')
    city_listener_source()
    return proof


def source_dependencies(*, execution_image=None) -> dict[str, str]:
    """Return immutable proof and source references required by the adapter."""
    proof = source()
    native02 = native02_source()
    formation = formation_source()
    refs = [{"path": SOURCE[0], "sha256": SOURCE[1]}, *proof["references"],
            {"path": FORMATION_SOURCE[0], "sha256": FORMATION_SOURCE[1]}, *formation["references"],
            {"path": ERA_TRANSITION_SOURCE[0], "sha256": ERA_TRANSITION_SOURCE[1]},
            {"path": RAF30_SOURCE[0], "sha256": RAF30_SOURCE[1]},
            {"path": CITY_LISTENER_SOURCE[0], "sha256": CITY_LISTENER_SOURCE[1]},
            {"path": NATIVE02_SOURCE[0], "sha256": NATIVE02_SOURCE[1]}, *native02["references"]]
    city_listener_source()
    native02_source()
    raf30_source()
    era_transition_source()
    current_refs = []
    if execution_image is not None:
        congress = congress_source(execution_image)
        refs.append(dict(path=CONGRESS_SOURCE[0], sha256=CONGRESS_SOURCE[1]))
        raf35_source(execution_image)
        refs.append(dict(path=RAF35_SOURCE[0], sha256=RAF35_SOURCE[1]))
        city_capture_listener_source(execution_image)
        refs.append(dict(path=CITY_CAPTURE_LISTENER_SOURCE[0], sha256=CITY_CAPTURE_LISTENER_SOURCE[1]))
        current_refs = [*congress['references'], *congress['images'].values()]
    pins: dict[str, str] = {}
    for ref in refs:
        path = str(_path(ref["path"]))
        digest = ref["sha256"]
        if path in pins and pins[path] != digest:
            raise ValueError("Conflicting XP2 host+20 source dependency")
        pins[path] = digest
    # New current-image records pin explicit file paths; the historical A0
    # resource-only resolver retains its original strict relative-path rule.
    from .resource_resolution import resolve_path
    for ref in current_refs:
        path = str(resolve_path(Path(ref['path'])).resolve())
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('Conflicting current XP2 host+20 source dependency')
        pins[path] = ref['sha256']
    module_path = str(Path(__file__).resolve())
    module_digest = hashlib.sha256(Path(module_path).read_bytes()).hexdigest()
    if module_path in pins and pins[module_path] != module_digest:
        raise ValueError("XP2 host+20 runtime source pin conflicts")
    pins[module_path] = module_digest
    verify_pinned_files(pins)
    return pins


def _read_exact(read, address: int, length: int) -> bytes:
    value = read(address, length)
    if type(value) is not bytes or len(value) != length:
        raise ValueError("XP2 host+20 live source read was incomplete")
    return value


def verify_live(base: int, read, *, host_pointer: int, execution_image=None) -> dict:
    """Match the pinned Core call chain and host-global owner to live memory."""
    if (type(base) is not int or base <= 0 or not callable(read)
            or type(host_pointer) is not int or host_pointer <= 0):
        raise ValueError("XP2 host+20 verification requires an exact Core and host")
    proof = source()
    native02 = native02_source()
    count = spans = 0
    formation = formation_source()
    era = era_transition_source()
    raf30 = raf30_source()
    city_listener = city_listener_source()
    congress = congress_source(execution_image) if execution_image is not None else None
    congress_bodies = congress['bodies'] if congress is not None else {}
    live_native02 = {name: native02["bodies"][name] for name in ("0x17fe80", "0x2e9de0")}
    for name, body in {**proof["bodies"], **formation["bodies"], **era["bodies"],
                       **live_native02,
                       **raf30["bodies"], **city_listener["bodies"], **congress_bodies}.items():
        fragments = body.get("fragments") or [body]
        for fragment in fragments:
            raw = bytes.fromhex(fragment.get("raw_hex", ""))
            if not raw:
                raise ValueError("XP2 host+20 live body is incomplete: " + name)
            start_rva = int(fragment.get("start_rva", body.get("start_rva", "0")), 16)
            for offset in range(0, len(raw), MAX_READ_BYTES):
                expected = raw[offset:offset + MAX_READ_BYTES]
                if _read_exact(read, base + start_rva + offset, len(expected)) != expected:
                    raise ValueError("XP2 host+20 live source bytes changed: " + name)
                count += len(expected)
                spans += 1
    if _read_exact(read, base + HOST_GLOBAL_RVA, 8) != host_pointer.to_bytes(8, "little"):
        raise ValueError("XP2 HOST global does not reference the pinned owner")
    if _read_exact(read, base + 0x9ceee0, len(_FORMATION_LITERAL)) != _FORMATION_LITERAL:
        raise ValueError("XP2 formation achievement literal changed")
    if _read_exact(read, base + 0x9d1020, 8) != (base + 0x17fa50).to_bytes(8, "little"):
        raise ValueError("XP2 formation achievement listener slot changed")
    if _read_exact(read, base + 0x9ceb28, len(_ERA_TRANSITION_LITERAL)) != _ERA_TRANSITION_LITERAL:
        raise ValueError("XP2 era-transition achievement literal changed")
    if _read_exact(read, base + 0x9d0288, len(_RAF30_LITERAL)) != _RAF30_LITERAL:
        raise ValueError("XP2 RAF30 achievement literal changed")
    if _read_exact(read, base + 0x9cee08, len(_CITY_LISTENER_LITERAL)) != _CITY_LISTENER_LITERAL:
        raise ValueError("XP2 city listener achievement literal changed")
    current_receipt = {}
    if congress is not None:
        for rva, expected in (*_CONGRESS_DATA,
                (0x9d12f0, (base + 0x17fac0).to_bytes(8, 'little'))):
            if _read_exact(read, base + rva, len(expected)) != expected:
                raise ValueError('XP2 Congress achievement live data changed')
            count += len(expected); spans += 1
        current_receipt = dict(congress_source_sha256=CONGRESS_SOURCE[1],
            execution_image_sha256=execution_image.image_sha256)
        for row in raf35_source(execution_image)['spans'].values():
            body = _read_exact(read, base + int(row['rva'], 16), row['bytes'])
            if hashlib.sha256(body).hexdigest() != row['sha256']:
                raise ValueError('XP2 RAF35 achievement live source differs at ' + row['rva'])
            count += len(body)
            spans += 1
        for rva, expected in ((0x9d0400, _RAF35_LITERAL),
                (0x9d0a50, (base + 0x17fcd0).to_bytes(8, 'little'))):
            if _read_exact(read, base + rva, len(expected)) != expected:
                raise ValueError('XP2 RAF35 achievement live data differs')
            count += len(expected)
            spans += 1
        current_receipt['raf35_source_sha256'] = RAF35_SOURCE[1]
        for row in city_capture_listener_source(execution_image)['spans'].values():
            body = _read_exact(read, base + int(row['rva'], 16), row['bytes'])
            if hashlib.sha256(body).hexdigest() != row['sha256']:
                raise ValueError('XP2 city capture achievement live source differs at ' + row['rva'])
            count += len(body)
            spans += 1
        current_receipt['city_capture_listener_source_sha256'] = CITY_CAPTURE_LISTENER_SOURCE[1]
    count += len(_ERA_TRANSITION_LITERAL) + len(_RAF30_LITERAL) + len(_CITY_LISTENER_LITERAL)
    spans += 3
    return {**current_receipt, "source_sha256": SOURCE[1], "native02_source_sha256": NATIVE02_SOURCE[1],
            "formation_source_sha256": FORMATION_SOURCE[1],
            "era_transition_source_sha256": ERA_TRANSITION_SOURCE[1], "raf30_source_sha256": RAF30_SOURCE[1],
            "core_sha256": XP2_CORE_SHA256,
            "city_listener_source_sha256": CITY_LISTENER_SOURCE[1],
            "verified_bytes": count + len(_FORMATION_LITERAL) + 8, "verified_spans": spans + 2,
            "host_global_rva": hex(HOST_GLOBAL_RVA), "native_execution": False}


def select_contract(frames, *, service_installed: bool = False, execution_image=None) -> str:
    """Admit only complete, source-proved Core return prefix."""
    source()
    if service_installed is not False:
        raise ValueError("XP2 optional achievement sink must remain explicitly uninstalled")
    if (type(frames) is not list or not frames
            or any(type(frame) is not dict or set(frame) != {"module", "rva"}
                   or type(frame["module"]) is not str
                   or type(frame["rva"]) is not str
                   or re.fullmatch(r"0x[0-9a-f]+", frame["rva"]) is None
                   for frame in frames)):
        raise ValueError("XP2 achievement caller stack is incomplete")
    core_frames = [frame for frame in frames if frame["module"].startswith("GameCore_")]
    if any(frame["module"] != CORE_MODULE for frame in core_frames):
        raise ValueError("Unproved XP2 optional achievement caller chain")
    returns = tuple(frame["rva"] for frame in core_frames)
    if execution_image is not None:
        congress_source(execution_image)
        if returns[:len(CONGRESS_PREFIX)] == CONGRESS_PREFIX:
            return CONGRESS_SOURCE[1]
        if returns[:len(RAF35_PREFIX)] == RAF35_PREFIX:
            raf35_source(execution_image)
            return RAF35_SOURCE[1]
        if returns[:len(CITY_CAPTURE_LISTENER_PREFIX)] == CITY_CAPTURE_LISTENER_PREFIX:
            city_capture_listener_source(execution_image)
            return CITY_CAPTURE_LISTENER_SOURCE[1]
    if returns[:len(ACCEPTED_CORE_RETURN_PREFIX)] == ACCEPTED_CORE_RETURN_PREFIX:
        return SOURCE[1]
    if returns[:len(NATIVE02_PREFIX)] == NATIVE02_PREFIX:
        native02_source()
        return NATIVE02_SOURCE[1]
    if returns[:len(FORMATION_CORE_RETURN_PREFIX)] == FORMATION_CORE_RETURN_PREFIX:
        formation_source()
        return FORMATION_SOURCE[1]
    if returns[:len(ERA_TRANSITION_PREFIX)] == ERA_TRANSITION_PREFIX:
        era_transition_source()
        return ERA_TRANSITION_SOURCE[1]
    if returns[:len(RAF30_PREFIX)] == RAF30_PREFIX:
        raf30_source()
        era_transition_source()
        return RAF30_SOURCE[1]
    if returns[:len(CITY_LISTENER_PREFIX)] == CITY_LISTENER_PREFIX:
        city_listener_source()
        return CITY_LISTENER_SOURCE[1]
    raise ValueError("Unproved XP2 optional achievement caller chain")

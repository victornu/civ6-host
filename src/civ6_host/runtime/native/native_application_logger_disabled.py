"""Explicit disabled application logging gate for the diagnostic host.

This is an owned host model, not an EXE manager instance. Its partial native-
layout storage is never exposed to any native function. Only the source branch
reading manager BYTE+8=0 and returning NULL is admitted. No GameCore is loaded.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import json
from pathlib import Path
import threading
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_application_logger_disabled.py')))).resolve().parents[1]
PROOF_SHA256 = 'f949a7109949290649fa864d8f4afd01f51fa8e5f9d48ba6f652b69cfb62d732'

def verify_source_evidence():
    raw = _resolve_resource_path(ROOT / 'work/native-application-logger-disabled366.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise ValueError('Changed disabled application logger source')
    proof = json.loads(raw)
    contract = proof['contract']
    if proof['schema'] != 'civ6rl.native_application_logger_disabled.static.v1' or contract['constructor_default_enabled'] is not True or contract['enabled_offset'] != 8 or (contract['enabled_width'] != 1) or (contract['explicit_disabled_profile_only'] is not True) or (contract['automatic_game_acknowledgement'] is not False):
        raise ValueError('Changed disabled application logger contract')
    raw = _resolve_resource_path(ROOT / proof['parent']['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != proof['parent']['sha256']:
        raise ValueError('Changed original application dispatcher source')
    return proof

class DisabledApplicationLogger:
    """One explicit, immutable logging-disabled choice for a dedicated host.

    Native constructor's enabled1 is represented before the deliberate setter0.
    Enabled behavior, EXE allocation/path setup and native vtable exposure are
    not implemented. The owner must be retained for the host's lifetime.
    """

    def __init__(self, *, logging_enabled, current_thread_id=threading.get_native_id):
        if logging_enabled is not False:
            raise ValueError('Application logger requires explicit logging_enabled=False')
        self.proof = verify_source_evidence()
        self._thread_reader = current_thread_id
        self._thread = current_thread_id()
        if type(self._thread) is not int or self._thread <= 0:
            raise ValueError('Expected creating native thread identity')
        self._storage = (C.c_ubyte * self.proof['contract']['manager_size'])()
        self._storage[8] = 1
        self._storage[8] = 0
        self._cache = 0
        self._closed = self._busy = False
        self.getter_calls = self.factory_calls = 0

    def _check(self):
        current = self._thread_reader()
        if type(current) is not int or current != self._thread:
            raise ValueError('Application logger crossed its owner thread')
        if self._closed or self._busy:
            raise ValueError('Application logger is closed or reentrant')
        if self._cache != 0:
            raise ValueError('NonNULL application logger cache is outside disabled profile')
        if self._storage[8] != 0:
            raise ValueError('Actual application logging gate is not disabled')

    def resolve_property_change_logger(self):
        """Return source NULL for100B50→15AC90, never a host+130 status."""
        self._check()
        self._busy = True
        try:
            self.getter_calls += 1
            self.factory_calls += 1
            if self._storage[8] != 0:
                raise ValueError('Application logging gate changed during factory')
            self._cache = 0
            return None
        finally:
            self._busy = False

    def receipt(self):
        self._check()
        return {'source_proof_sha256': PROOF_SHA256, 'profile': 'explicit-disabled-application-logging-gate', 'logging_enabled_byte': int(self._storage[8]), 'cached_logger_pointer': self._cache, 'constructor_default_enabled': True, 'explicit_host_disable': True, 'getter_calls': self.getter_calls, 'factory_calls': self.factory_calls, 'original_EXE_manager_instantiated': False, 'native_storage_exposed': False, 'host_acknowledgement_permitted': False}

    def close(self):
        self._check()
        self._closed = True

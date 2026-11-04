"""Borrowed A prelude plus two bounded diagnostic application dispatch cases.

No DLL is loaded here. Every provider operation uses the pinned native entry
through the required Win64 invocation seam. The caller must turn ANY exception
into a fatal worker exit, never let ctypes invent a return, and retain this
object, B and the Core context until the enclosing native call has finished.

This explicitly chosen diagnostic B is NOT the owned EXE singleton bootstrap.
The omitted borrowed temporary has only local schema/inline-vector lifetime
under the checked profile; its allocation/OOM timing is not reproduced.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _BASE_CORE
from civ6_host.runtime import application_mirror_profiles as _mirror_profiles
from civ6_host.runtime.application_mirror_profiles import mirror_abi as _mirror_abi
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
from civ6_host.runtime.native import native_configuration_finalization as setup
from civ6_host.runtime.native.native_application_mirror_records import bounded_get_player_config
from civ6_host.runtime.native.native_application_property_copy import copy_existing
from civ6_host.runtime.native.native_application_property_copy import verify_source as verify_copy_source
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_application_mirror_dispatch.py')))).resolve().parents[1]
from civ6_host.runtime.native import native_game_value_prelude_mutation as prelude
from civ6_host.runtime.native import native_application_logger_disabled as logger_module
GAME, PLAYER = (779060372, 1829978708)
PROPERTY, INDEX, LAST_TURN_PHASE = (2716180809, 4033489650, 604523296)
ARGUMENT_VTABLE, GETTER, MAP_VTABLE, LOOKUP = (8509496, 7652928, 8507296, 7625904)
PROFILE = 'diagnostic-owned-native-B-null-observer-borrowed-A-existing-views'
GAME_SHA256 = 'eeea976faf3f7f72bb43e5ebd383c9255867d4d135bd6bf7a21d1ee16e89db82'
COPY_SHA256 = '3abc69a0ad859801ca5003a619c2e186e6f6434fa7384e29e175b748e15b6fa5'
LIFETIME_SHA256 = prelude.LIFETIME_SHA256
LOGGER_SHA256 = logger_module.PROOF_SHA256
DISPATCH_SHA256 = 'a1d97e29ebc593a4ec1a802900f21f0ed5be984eae54b2a5ecd2071ce39d404f'

def verify_source_evidence(*, core_sha256=_BASE_CORE):
    if core_sha256 != _BASE_CORE:
        return _mirror_profiles.dispatch_source(core_sha256)
    contract_raw = _resolve_resource_path(ROOT / 'work/native-application-dispatch-contract367.json').read_bytes()
    if hashlib.sha256(contract_raw).hexdigest() != DISPATCH_SHA256:
        raise ValueError('Composed borrowed dispatch contract changed')
    composed = json.loads(contract_raw)
    contract = composed['contract']
    if composed['schema'] != 'civ6rl.native_application_dispatch_contract.static.v1' or contract['admitted_kinds'] != [PLAYER, GAME] or contract['native_return'] != 0 or (contract['player']['input_keys'] != [PROPERTY, INDEX]) or (contract['player']['direct_tags'] != [3, 2]) or (contract['player']['entries'] != 2) or (contract['game']['input_keys'] != [PROPERTY]) or (contract['game']['property_key'] != LAST_TURN_PHASE) or (contract['game']['creates_destination'] is not False) or (contract['closed_host_B']['profile'] != PROFILE) or (contract['full_EXE_application_equivalence'] is not False):
        raise ValueError('Changed closed application dispatch profile')
    for row in composed['parents'].values():
        if hashlib.sha256(_resolve_resource_path(ROOT / row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Changed composed application dispatch parent')
    raw = _resolve_resource_path(ROOT / 'evidence/native-host-game-value-change' / f'{GAME_SHA256}.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != GAME_SHA256:
        raise ValueError('Application dispatch source pin changed')
    game = json.loads(raw)
    if game['images'] != {'core_sha256': setup.CORE_SHA256, 'exe_sha256': setup.EXE_SHA256} or game['contract']['kind'] != GAME or game['contract']['native_return'] != 0 or (game['contract']['deferred_records'] != 0):
        raise ValueError('Changed GAME dispatch ABI/record contract')
    lifetime = prelude.verify_lifetime_source()
    triggers = lifetime['contract']['shared_triggers']
    if triggers['PLAYER_VALUE_CHANGED']['kind'] != PLAYER or triggers['PLAYER_VALUE_CHANGED']['constructor_call_va'] != '0x14010187c' or triggers['GAME_VALUE_CHANGED']['constructor_call_va'] != '0x140101a8d' or (triggers['GAME_VALUE_CHANGED']['journal_in_this_branch'] is not False):
        raise ValueError('Changed common borrowed wrapper branches')
    log = logger_module.verify_source_evidence()
    guards = log['instruction_guards']
    for va, text in {'0x140101a71': 'call 0x140100b50', '0x14010188c': 'call qword ptr [rax + 0x68]', '0x14010191b': 'call 0x14079f710', '0x140101937': 'call 0x1405089d0', '0x140101b2f': 'call 0x1400ff080', '0x140101b3c': 'xor eax, eax'}.items():
        if guards.get(va) != text:
            raise ValueError('Changed ordered application dispatch source')
    verify_copy_source()
    game_rows = {}

    def collect(value):
        if isinstance(value, dict):
            if 'va' in value and 'text' in value:
                game_rows[value['va']] = value['text']
            else:
                for child in value.values():
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(game)
    for va, text in {'0x140101a9f': 'call qword ptr [r8 + 0x58]', '0x140101aa9': 'je 0x140101b05', '0x140101abc': 'call qword ptr [r8 + 0x58]', '0x140101ac6': 'je 0x140101aea', '0x140101ad7': 'call qword ptr [rdx + 0x20]', '0x140101ada': 'mov rdx, rbp', '0x140101add': 'mov rcx, rsi', '0x140101ae0': 'mov r8, rax', '0x140101ae3': 'call 0x14079f710', '0x140101ae8': 'jmp 0x140101b2a', '0x140101b2f': 'call 0x1400ff080'}.items():
        if game_rows.get(va) != text:
            raise ValueError('GAME present-pair assignment source differs')
    return {'composed': composed, 'game': game, 'lifetime': lifetime, 'logger': log, 'setup': setup.verify_source()}

def _read(read, address, length):
    if type(address) is not int or not 0 < address <= (1 << 64) - length or type(length) is not int or (not 0 < length <= 6784):
        raise ValueError('Invalid bounded dispatch read')
    value = read(address, length)
    if type(value) is not bytes or len(value) != length:
        raise ValueError('Short dispatch memory read')
    return value

def _scalar(raw, tag):
    if len(raw) != 24 or struct.unpack_from('<H', raw)[0] != tag or struct.unpack_from('<I', raw, 20)[0] != 0:
        raise ValueError('Argument requires the admitted direct scalar tag/flags')
    return struct.unpack_from('<I', raw, 8)[0]

def _topology(snapshot):
    players = tuple(snapshot['players'])
    pointers = (snapshot['descriptor'], snapshot['normalized'], snapshot['map_normalized'], *players)
    if len(players) != 64 or len(set(pointers)) != 67 or any((type(p) is not int or not 0 < p < (1 << 64) - 88 for p in pointers)):
        raise ValueError('Expected the existing distinct 67-map configuration topology')
    return pointers

class ApplicationDispatchFailure(RuntimeError):

    def __init__(self, dispatcher, error):
        super().__init__('Borrowed application dispatch failed; fatal exit required: ' + str(error))
        self.dispatcher = dispatcher
        self.original_error = error
        self.requires_fatal_worker_exit = True

class BorrowedApplicationDispatcher:
    """One host-owned synchronous dispatcher; many calls, no retry after failure.

    invoke(address, result_ctype, argument_ctypes_including_this, *args) must
    execute the actual native target. Injected pure tests are the only substitute.
    ``journal`` is the existing bounded host player-change list, not an A0 queue.
    ``diagnostic_profile`` and ``logging_enabled`` are explicit host choices.
    They are not evidence about a separate graphical EXE process.
    """

    def __init__(self, base, context, application_owner, *, read, invoke, current_thread_id, journal, journal_limit, diagnostic_profile, logging_enabled, core_sha256=_BASE_CORE):
        self.abi = _mirror_profiles.owner_abi(application_owner, core_sha256)
        if diagnostic_profile != PROFILE:
            raise ValueError('Explicit diagnostic B/prelude profile is required')
        if type(base) is not int or not 0 < base < (1 << 64) - 9437184 or type(context) is not int or (not 0 < context < (1 << 64) - 4096):
            raise ValueError('Invalid retained Core base/context')
        if type(journal) is not list or type(journal_limit) is not int or (not 0 < journal_limit <= 2147483647):
            raise ValueError('Expected the existing bounded player journal')
        self.base, self.context, self.application_owner = (base, context, application_owner)
        self.read, self.invoke, self.current_thread_id = (read, invoke, current_thread_id)
        self.journal, self.journal_limit = (journal, journal_limit)
        self.thread_id = current_thread_id()
        if type(self.thread_id) is not int or self.thread_id <= 0:
            raise ValueError('Expected creating native thread identity')
        self.proofs = verify_source_evidence(core_sha256=core_sha256)
        self.logger = logger_module.DisabledApplicationLogger(logging_enabled=logging_enabled, current_thread_id=current_thread_id)
        self.busy = self.poisoned = self.closed = False
        self.attempts = []
        self.completed_calls = 0

    def _thread(self):
        current = self.current_thread_id()
        if type(current) is not int or current != self.thread_id:
            raise ValueError('Borrowed application dispatch crossed its native thread')
        if self.poisoned or self.closed:
            raise ValueError('Borrowed application dispatcher is poisoned or closed')

    def _invoke(self, address, result, types, *args):
        self._thread()
        value = self.invoke(address, result, tuple(types), *args)
        self._thread()
        return value

    def _call(self, address, result, types, receiver, *args):
        return self._invoke(address, result, (C.c_void_p, *types), receiver, *args)

    def _code(self):
        bodies = [self.proofs['game']['core_functions'][name] for name in ('argument_getter', 'property_lookup')]
        bodies += [self.proofs['setup']['core_functions'][name] for name in ('outer_initialized', 'inner_initialized')]
        for body in bodies:
            instructions = [i for f in body['fragments'] for i in f['instructions']]
            if not instructions:
                raise ValueError('Missing captured native dispatch body')
            for ins in instructions:
                raw = bytes.fromhex(ins['bytes'])
                if _read(self.read, self.base + int(ins['va'], 16) - 6442450944, len(raw)) != raw:
                    raise ValueError('Live application dispatch method differs from source')

    def _owners(self, source_store):
        self._thread()
        owner = self.application_owner
        owner.require_context(self.base, self.context)
        a = setup._linked_snapshot(self.base, self.context, self.read, self._call, core_sha256=self.abi.configuration.core_sha256)
        b = owner.snapshot()
        ap, bp = (_topology(a), _topology(b))
        if source_store != ap[0] or owner.pointer != bp[0] or set(ap) & set(bp):
            raise ValueError('Actual source_store does not match distinct retained A/B owners')
        headers = {p: _read(self.read, p, 88) for p in bp}
        root_allocator = struct.unpack_from('<Q', headers[bp[0]], 32)[0]
        if not root_allocator:
            raise ValueError('Diagnostic B native allocator is NULL')
        for pointer, header in headers.items():
            vt, parent, observer, control, allocator = struct.unpack_from('<QQQQQ', header)
            if vt != self.base + self.abi.configuration.vtable_rva or observer or control or (allocator != root_allocator):
                raise ValueError('Diagnostic B observer/allocator profile changed')
            visited = {pointer}
            while parent:
                if parent not in headers or parent in visited:
                    raise ValueError('Diagnostic B notification parent chain is not closed')
                visited.add(parent)
                parent = struct.unpack_from('<Q', headers[parent], 8)[0]
        if any((_read(self.read, pointer, 88) != raw for pointer, raw in headers.items())):
            raise ValueError('Diagnostic B headers changed during validation')
        return (a, b)

    def _arguments(self, kind, pointer):
        if struct.unpack('<Q', _read(self.read, pointer, 8))[0] != self.base + self.abi.argument_vtable_rva:
            raise ValueError('Unverified notification argument object')
        if struct.unpack('<Q', _read(self.read, self.base + self.abi.argument_vtable_rva + 104, 8))[0] != self.base + self.abi.argument_getter_rva:
            raise ValueError('Unverified notification argument getter slot')
        header = _read(self.read, pointer + 40, 24)
        begin, end, capacity = struct.unpack('<QQQ', header)
        expected = {PROPERTY: 3, INDEX: 2} if kind == PLAYER else {PROPERTY: 3}
        if not begin or end != begin + 32 * len(expected) or (not end <= capacity < 1 << 64):
            raise ValueError('Unexpected exact notification argument vector shape')
        raw = _read(self.read, begin, end - begin)
        fields = {}
        for offset in range(0, len(raw), 32):
            key = struct.unpack_from('<I', raw, offset)[0]
            if key not in expected or key in fields:
                raise ValueError('Unexpected/duplicate notification argument key')
            value_raw = raw[offset + 8:offset + 32]
            value = _scalar(value_raw, expected[key])
            fields[key] = (begin + offset + 8, value_raw, value)
        if set(fields) != set(expected):
            raise ValueError('Missing required notification argument')
        return {'pointer': pointer, 'begin': begin, 'header': header, 'raw': raw, 'fields': fields}

    def _stable_arguments(self, args):
        if _read(self.read, args['pointer'] + 40, 24) != args['header'] or _read(self.read, args['begin'], len(args['raw'])) != args['raw'] or struct.unpack('<Q', _read(self.read, args['pointer'], 8))[0] != self.base + self.abi.argument_vtable_rva:
            raise ValueError('Borrowed notification arguments changed during dispatch')

    def _get_argument(self, args, key):
        expected, raw, value = args['fields'][key]
        actual = self._call(self.base + self.abi.argument_getter_rva, C.c_void_p, (C.c_uint32,), args['pointer'], key)
        if type(actual) is not int or actual != expected or _read(self.read, actual, 24) != raw:
            raise ValueError('Native argument getter returned a foreign/changed variant')
        return value

    def _lookup(self, provider, key):
        result = self._call(self.base + self.abi.configuration.lookup_rva, C.c_void_p, (C.c_uint32,), provider, key)
        if result is not None and (type(result) is not int or result < 0):
            raise ValueError('Invalid nullable native property lookup result')
        return result

    def _append_pair(self, index, key, expected_length):
        if len(self.journal) != expected_length or expected_length >= self.journal_limit:
            raise ValueError('Player journal changed or exceeded its explicit host resource bound')
        self.journal.append((index, key))
        if len(self.journal) != expected_length + 1 or self.journal[-1] != (index, key):
            raise ValueError('Player journal append failed after native copy')

    def dispatch(self, kind, argument, source_store):
        """Return a receipt with native_dispatch_return=0 only on completion.

        This is NOT itself a ctypes callback. Unknown shapes, all errors and
        reentry must end the worker, never ACK. GAME never queues a player pair.
        """
        try:
            self._thread()
            if self.busy:
                raise ValueError('Reentrant application dispatch is outside the closed profile')
        except Exception as error:
            self.poisoned = True
            raise ApplicationDispatchFailure(self, error) from error
        self.busy = True
        try:
            if type(kind) is not int or kind not in (PLAYER, GAME):
                raise ValueError('Unadmitted application notification kind')
            _read(self.read, source_store, 8)
            self._code()
            args = self._arguments(kind, argument)
            key = self._get_argument(args, PROPERTY)
            journal_before = tuple(self.journal)
            if kind == PLAYER and len(journal_before) >= self.journal_limit:
                raise ValueError('Player journal requires a verified consumer before another dispatch')
            if kind == GAME:
                if key != LAST_TURN_PHASE:
                    raise ValueError('GAME diagnostic admits only LAST_TURN_PHASE_TYPE')
                if struct.unpack('<I', _read(self.read, self.base + self.abi.phase_key_rva, 4))[0] != key:
                    raise ValueError('Native LAST_TURN_PHASE_TYPE key changed')
                if self.logger.resolve_property_change_logger() is not None:
                    raise ValueError('Disabled logger unexpectedly supplied an interface')
            a, b = self._owners(source_store)
            self._stable_arguments(args)
            attempt = prelude.NativePreludeAttempt(self.base, self.context, self.application_owner, read=self.read, invoke=self._invoke, current_thread_id=self.current_thread_id, core_sha256=self.abi.configuration.core_sha256)
            self.attempts.append(attempt)
            effects = attempt.apply(source_store, a)
            if effects.get('provider_effects_completed') is not True:
                raise ValueError('Borrowed provider effects did not complete')
            self._stable_arguments(args)
            after_a, after_b = self._owners(source_store)
            if _topology(after_a) != _topology(a) or _topology(after_b) != _topology(b):
                raise ValueError('Native prelude changed a retained top-level map identity')
            receipt = {'kind': kind, 'property_key': key, 'profile': PROFILE, 'source_store_validated': True, 'borrowed_prelude': effects, 'mirrored': False, 'cell_created_in_B': False, 'journal_entries_added': 0, 'source_proof_sha256': self.abi.game_proof_sha256, 'lifetime_source_sha256': self.abi.lifetime_proof_sha256, 'composed_source_sha256': self.abi.dispatch_proof_sha256, 'copy_source_sha256': self.abi.copy_proof_sha256, 'logger_source_sha256': LOGGER_SHA256, 'B_owned_EXE_bootstrap_equivalent': False, 'whole_EXE_application_equivalent': False, 'local_schema_allocation_timing_equivalent': False, 'player_journal_consumer_implemented': False, 'eligible_for_training': False}
            if kind == PLAYER:
                index = self._get_argument(args, INDEX)
                if not 0 <= index < 64:
                    raise ValueError('Player record index is outside admitted 64 existing records')
                record = _mirror_profiles.indexed_player(self.base, self.context, index, read=self.read, lookup=lambda provider, field: self._lookup(provider, field), call=self._call, core_sha256=self.abi.configuration.core_sha256)
                destination = self.application_owner.player(index)
                if record['provider'] != source_store or record['pointer'] != after_a['players'][index] or destination['provider'] != after_b['descriptor'] or (destination['pointer'] != after_b['players'][index]):
                    raise ValueError('Fresh indexed player map does not match retained owner topology')
                copied = copy_existing(self.base, record['pointer'], destination['pointer'], key, read=self.read, call=self._call, core_sha256=self.abi.configuration.core_sha256)
                mirrored = copied.get('mirrored')
                branch = copied.get('native_branch')
                if type(mirrored) is not bool or branch not in ('missing_source', 'missing_destination', 'copy_and_queue') or mirrored != (branch == 'copy_and_queue'):
                    raise ValueError('Invalid native property assignment receipt')
                receipt.update(player_index=index, mirrored=mirrored, native_branch=branch, native_copy=copied)
                if mirrored:
                    self._append_pair(index, key, len(journal_before))
                    receipt['journal_entries_added'] = 1
            else:
                source = self._lookup(after_a['normalized'], key)
                if not source:
                    raise ValueError('Missing GAME source is outside the selected diagnostic branch')
                raw = _read(self.read, source, 24)
                value = _scalar(raw, 2)
                destination = self._lookup(after_b['normalized'], key)
                if destination:
                    copied = copy_existing(self.base, after_a['normalized'], after_b['normalized'], key, read=self.read, call=self._call, core_sha256=self.abi.configuration.core_sha256)
                    if copied.get('mirrored') is not True or copied.get('native_branch') != 'copy_and_queue':
                        raise ValueError('GAME presence changed before native assignment')
                    if _scalar(_read(self.read, destination, 24), 2) != value:
                        raise ValueError('GAME native copy did not preserve the phase value')
                    receipt.update(native_branch='copy_without_journal', mirrored=True, native_copy=copied, source_value=value, destination_present=True, logger=self.logger.receipt(), player_journal_required=False)
                else:
                    receipt.update(native_branch='missing_destination', source_value=value, destination_present=False, logger=self.logger.receipt())
                if _read(self.read, source, 24) != raw:
                    raise ValueError('GAME source changed during destination lookup/copy')
            expected_journal = (*journal_before, (receipt['player_index'], key)) if kind == PLAYER and receipt['mirrored'] else journal_before
            if tuple(self.journal) != expected_journal:
                raise ValueError('Unexpected journal mutation during application dispatch')
            self._stable_arguments(args)
            final_a, final_b = self._owners(source_store)
            if _topology(final_a) != _topology(a) or _topology(final_b) != _topology(b):
                raise ValueError('Retained provider topology changed before borrowed cleanup')
            self._thread()
            self.completed_calls += 1
            receipt.update(bounded_dispatch_completed=True, native_dispatch_return=0, journal_size=len(self.journal), no_Game_rule_substitution=True, borrowed_cleanup_has_no_provider_release=True)
            return receipt
        except Exception as error:
            self.poisoned = True
            raise ApplicationDispatchFailure(self, error) from error
        finally:
            self.busy = False

    def close(self):
        self._thread()
        if self.busy:
            raise ValueError('Cannot close a live borrowed dispatch')
        self.logger.close()
        self.closed = True

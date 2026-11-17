"""XP2 religious-chain session integration with explicit machine-boundary doubles.

This portable module is accepted only after selective installation, with the
private-source import guard already enabled. It never loads an engine process.
"""
import ast
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from dataclasses import replace
from itertools import product
import json
import struct
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.contracts import network_turn, religion_beliefs
from civ6_host.runtime import xp1_prophet_activation as activation
from civ6_host.runtime import xp1_religion_founding as founding
from civ6_host.runtime import xp1_religion_beliefs as beliefs
from civ6_host.runtime import xp1_prophet_activation_source as activation_source
from civ6_host.runtime import xp1_religion_founding_source as founding_source
from civ6_host.runtime import xp1_religion_beliefs_source as beliefs_source
from civ6_host.runtime import xp1_session_view as view, xp1_load_capability
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.source_build_identity import CURRENT_UNSIGNED_LOG_HOST_REFERENCE
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
from civ6_host.runtime import xp2_bbg_inputs
from test_xp1_network_session import Fixture as ParentFixture, reset_reply
from test_xp2_religious_chain_public import GROUPS, KINDS, preceding, state, validate
from test_xp2_religious_unit_operations_public import permissions_preceding
from test_xp1_religion_beliefs_public import terminal_v11
from test_session_capabilities import seal

ADAPTERS = (activation, founding, beliefs)
SOURCES = (activation_source, founding_source, beliefs_source)
FIELDS = ('activation', 'foundation', 'beliefs')
FLAGS = tuple('xp2_' + group for group in GROUPS)
REFUSALS = ('native_prophet_can_start_false',
            'native_religion_foundation_can_start_false', 'native_belief_can_start_false')


def worker_preflight(flag):
    tree = ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
    body = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_open_xp1').body
    blocks = [n for n in body if isinstance(n, ast.If)
              and ast.unparse(n.test) in (flag, 'type(' + flag + ') is not bool')]
    if len(blocks) != 2:
        raise AssertionError('Expected strict Boolean and exact source admission')
    wrapper = ast.parse('def check(' + flag + ', selected, occupation_image, closure): pass').body[0]
    wrapper.body = blocks
    scope = {'_Path': Path}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                 str(worker.__file__), 'exec'), scope)
    return scope['check']


def native_states(obs, mode):
    """Synthetic native metadata around the peer's public phase fixture."""
    result = {}
    for group, field, source in zip(GROUPS, FIELDS, SOURCES):
        value = state(obs, mode)[group]
        own = dict(deepcopy(value['own']), player_id=obs['player_id'], current_game_turn=obs['turn'],
            observation_only=True, action_effect_verified=False, exposed_to_learner=False,
            eligible_for_training=False, source_proof_sha256=source.source_for(_PROFILE)[1])
        result[group] = dict(own=own, **{field: deepcopy(value[field])})
    return result


from test_xp2_religious_unit_operations_session import Fixture as XP2OwnerFixture


class Fixture(XP2OwnerFixture):
    """Reuse the real XP2 graph and source-selected service owners.

    Lua runs the actual authored builders over the existing synthetic XP1 Lua
    object environments. IPO calls and native state mutation are machine seams.
    The runtime suite separately exercises the real IPO and 305 normalizer.
    """
    def __init__(self, family=0):
        super().__init__()
        self.family = family
        self.created = -1 if family < 2 else 4
        self.earned = 0 if family == 0 else 2
        self.holy = family != 0
        self.city_owner = self.unit_owner = self.pid = self.observer = self.x = 0
        self.removed = -1; self.has_prophet = True; self.unit_type = 6; self.moves = 2; self.turn = 8
        self.foreign_holy = self.claimed = self.deny_request = False
        self.holy_city_lookup = None
        self.can_start = self.apply_native = True
        self.equipped = []; self.evaluations = []; self.requested_uid = None
        self.choice = (dict(kind='activate_prophet',unit_id=18,x=1,y=0),
                       dict(kind='found_religion',index=9,hash=0xffffffff),
                       dict(kind='add_belief',index=2,hash=0xffffffff,**{'class':'BELIEF_CLASS_FOLLOWER'}))[family]
        self.payload = struct.pack('<IHH5I',0x8c0f3f36,0,1,18,15,0xffffffff,0,0)
        self.observation['units'] = [dict(id=17,x=0,y=0,owner=0,type=6,moves=2),
                                     dict(id=18,x=1,y=0,owner=0,type=6,moves=2)]
        self.token.observation = deepcopy(self.observation)
        self.saved.xp2_religious_unit_operations = False
        for index, flag in enumerate(FLAGS): setattr(self.saved,flag,index == family)
        for group in GROUPS: setattr(self.saved,'xp1_' + group,False)
        from civ6_host.runtime import xp2_religious_chain_source as chain
        from civ6_host.runtime.xp1_saved_load_logger import XP2_SOURCE
        self.backend._xp2_load_logger_activation = dict(source_sha256=XP2_SOURCE[1])
        proof = chain.verify_source()
        archive_table = chain._archive_source(proof)['vtable']
        for slot in archive_table['slots']:
            address = int(archive_table['rva'],16) + int(slot,16)
            native = struct.unpack('<Q',self.pe.get_data(address,8))[0]
            self.memory.put(self.memory.core_base+address,struct.pack('<Q',
                native-self.pe.OPTIONAL_HEADER.ImageBase+self.memory.core_base))
        for row in proof['callable_vtables'].values():
            rva = int(row['rva'],16)
            for slot in range(len(row['target_rvas'])):
                # Real PE bytes and normal relocation, not values copied from
                # the validator's expected target list.
                address = rva + slot*8
                native = struct.unpack('<Q',self.pe.get_data(address,8))[0]
                self.memory.put(self.memory.core_base+address,struct.pack('<Q',
                    native-self.pe.OPTIONAL_HEADER.ImageBase+self.memory.core_base))
        from civ6_host.runtime.native import native_saved_religion as shared
        from civ6_host.runtime.native import native_religion_diagnostic as commands
        self.stack.enter_context(patch.object(shared,'observe_player',self.observe_native))
        self.stack.enter_context(patch.object(commands,'request_player_operation',self.request))

    def evaluate(self, child, code, name, **kwargs):
        from lupa.lua51 import LuaRuntime
        from test_xp1_prophet_activation import ENV as prophet_env
        from test_xp1_religion_founding import ENV as founding_env
        from test_xp1_religion_beliefs import ENV as beliefs_env
        if child is not self.token.ui_child: raise AssertionError('Foreign chain Lua child')
        self.evaluations.append(name)
        if name in (b'@religion_observation_guards',b'@native_prophet_guards',
                    b'@native_religion_founding_guards',b'@native_religion_belief_guards'):
            return LuaRuntime(encoding=None).execute(code)
        if name == b'@native_religion_observation_turn': return b'8'
        common = (b'@native_own_religion_observation',)
        names = ((b'@explicit_prophet_activation',b'@native_prophet_catalog',
                  b'@native_prophet_revalidation',b'@native_prophet_request',b'@native_prophet_effect'),
                 (b'@explicit_religion_foundation',b'@native_religion_founding_catalog',
                  b'@native_religion_founding_revalidation',b'@native_religion_founding_effect'),
                 (b'@explicit_religion_beliefs',b'@native_religion_belief_catalog',
                  b'@native_religion_belief_revalidation',b'@native_religion_belief_effect'))
        if name not in common + names[self.family]: raise AssertionError('Unexpected chain Lua read '+repr(name))
        env = (prophet_env,founding_env,beliefs_env)[self.family]
        if self.family == 0:
            env = env.replace(b"OperationType='UNITOPERATION_FOUND_RELIGION',Hash=",
                              b"OperationType='UNITOPERATION_FOUND_RELIGION',Index=15,VisibleInUI=true,Hash=")
            env = env.replace(b'visible==false',b"type(visible)=='boolean'")
            env = env.replace(b'host_can_start(u:GetID())',b'host_can_start(u:GetID(),visible)')
        values = {b'PID':self.pid,b'OBSERVER':self.observer,b'TURN':self.turn,b'CREATED':self.created,
                  b'EARNED':self.earned,b'HOLY':self.holy,b'CITYOWNER':self.city_owner,
                  b'REMOVED':self.removed,b'UNITOWNER':self.unit_owner,b'UNITTYPE':self.unit_type,
                  b'MOVES':self.moves,b'HASPROPHET':self.has_prophet,b'UNITX':self.x,
                  b'FOREIGN':self.foreign_holy,b'CLAIMED':self.claimed}
        for key,value in values.items(): env = env.replace(key,str(value).lower().encode())
        env = env.replace(b'EQUIPPED',','.join(map(str,self.equipped)).encode())
        lua = LuaRuntime(encoding=None, unpack_returned_tuples=True)
        if name == b'@native_own_religion_observation' and self.holy_city_lookup is not None:
            lua.globals()[b'host_read_holy_city'] = self.holy_city_lookup[0]
            lua.globals()[b'host_resolve_holy_city'] = self.holy_city_lookup[1]
            env += b"""
religion.GetHolyCityID = function()
 local owner, id = host_read_holy_city()
 return {player=owner,type=2,id=id}
end
local CityManager = {GetCity=function(descriptor)
 local name=host_resolve_holy_city(descriptor.player, descriptor.id)
 if name==nil then return nil end
 return setmetatable({GetName=function() return name end},
  {__index=function(_,key) error('unexpected foreign city getter: '..key) end})
end}
local Locale = {
 Lookup=function(key,name)
  assert(key=='LOC_UI_RELIGION_HOLY_CITY')
  return 'VILLE SAINTE : '..name
 end,
 ToUpper=function(label)
  return string.upper(label)
 end}
"""
        def legal(uid, visible):
            if type(visible) is not bool: raise AssertionError('Native visibility flag is not Boolean')
            self.machine.append(('can_start',name,uid,visible))
            if visible: return True
            return self.can_start and not (self.deny_request and name == b'@native_prophet_request')
        def request(uid, operation):
            self.machine.append(('request',uid,operation)); self.requested_uid=uid
            self.token.transport.pending.append(self.payload)
        lua.globals()[b'host_can_start'] = legal
        lua.globals()[b'host_request'] = request
        return lua.execute(env+code)

    def request(self,core,context,pid,operation,parameters,*,core_sha256,read,religion_permit):
        from civ6_host.runtime.native import native_religion_founding as foundation
        from civ6_host.runtime.native import native_religion_beliefs as belief
        builder = foundation if self.family == 1 else belief
        expected = builder.FOUND_RELIGION if self.family == 1 else builder.ADD_BELIEF
        key = builder.PARAM_RELIGION_TYPE if self.family == 1 else builder.PARAM_BELIEF_TYPE
        if (core is not self.backend.core or context != self.backend.context or pid != 0
                or core_sha256 != XP2_CORE_SHA256 or read != self.read or operation != expected
                or parameters != {key:self.choice['hash'],builder.PARAM_INSERT_MODE:builder.VALUE_EXCLUSIVE}):
            raise AssertionError('Foreign player-operation machine request')
        from civ6_host.runtime.xp2_direct_religion_source import authorize_request
        name = authorize_request(religion_permit,core,context,pid,operation,parameters,
                                 core_sha256=core_sha256,submit=True,allow_empty=False)
        self.machine.append(('native_direct_request',name))
        self.machine.append(('request',operation,deepcopy(parameters)))
        payload = struct.pack('<6I',0xc45de12f,pid,operation,0,0x80000001,2)
        payload += b''.join(struct.pack('<IHH10xI',k,0,2,v) for k,v in parameters.items())
        self.token.transport.pending.append(payload)
        return dict(can_start=None,native_can_start_called=False,request_invoked=True)

    def virtual(self,core,pointer,slot,rva,result,*args):
        if rva != self.token.transport.transport_abi.drain_rva:
            return super().virtual(core,pointer,slot,rva,result,*args)
        def drain(context):
            if core is not self.backend.core or context != self.backend.context:
                raise AssertionError('Foreign native queue owner')
            self.machine.append(('drain',))
            self.memory.put(self.sentinel,struct.pack('<QQ',self.sentinel,self.sentinel))
            if self.family == 0:
                from civ6_host.runtime.native import native_event_15c35863 as event
                address=0x78002000
                self.memory.put(address,struct.pack('<HHI',0,1,self.requested_uid))
                self.owner.dispatch(event.KIND,event.encode_fields(event.EventFields(0,15,address)),0)
            if self.apply_native:
                if self.family == 0:
                    self.removed=self.requested_uid; self.holy=True; self.earned=2
                    self.observation['units']=[u for u in self.observation['units'] if u['id'] != self.removed]
                elif self.family == 1: self.created=self.choice['index']
                else: self.equipped.append(self.choice['index'])
        return drain


class XP2ReligiousChainSessionTests(unittest.TestCase):
    def test_parent_independent_strict_flags_and_actual_xp2_closure(self):
        with ParentFixture() as f:
            f.captured.reference = REFERENCE
            f.executable = resource_root() / CURRENT_UNSIGNED_LOG_HOST_REFERENCE[0]
            base = dict(input_profile='xp2-lan', official_bundle=dict(zip(('path','sha256'), REFERENCE)))
            default = f.session(**base)
            self.assertTrue(all(getattr(default, flag) is False for flag in FLAGS))
            for flag, source in zip(FLAGS, SOURCES):
                for value in (0, 1, None, 'true'):
                    with self.subTest(flag=flag, value=value), self.assertRaises(ValueError):
                        f.session(**base, **{flag:value})
                with self.assertRaises(ValueError): f.session(**{flag:True})
                with self.assertRaisesRegex(ValueError, 'exact admitted'):
                    f.session(**base, **{flag:True})
                options = dict(base, execution_image_profile=_PROFILE.id, **{flag:True})
                with patch.object(source, 'require_actions', side_effect=ValueError('source refused')):
                    with self.assertRaisesRegex(ValueError, 'source refused'): f.session(**options)
                current = f.session(**options)
                for other in (*FLAGS, 'xp2_religious_unit_operations', 'xp1_prophet_activation',
                              'xp1_religion_founding', 'xp1_religion_beliefs', 'xp1_great_people',
                              'xp1_religion_custom_names', 'trade_diagnostic', 'standard_trade'):
                    self.assertIs(getattr(current, other), other == flag)
                from civ6_host.runtime.xp1_session_result import result_provenance
                def reply(session):
                    value = reset_reply(session)
                    value['outcome']['native_victory'].update(result_provenance(XP2_CORE_SHA256))
                    return value
                with patch.object(NativeNetworkSession, '_receive', reply): current.reset()
                path = current.run / 'closure.json'
                self.assertLess(path.stat().st_size, 8*1024*1024)
                closure = json.loads(path.read_text(encoding='utf-8'))
                self.assertIs(closure[flag], True)
                for other in FLAGS:
                    if other != flag: self.assertNotIn(other, closure)
                for path, digest in source.source_dependencies(_PROFILE, reference=REFERENCE).items():
                    self.assertEqual(closure['pins'][str(Path(path).resolve())], digest)
            self.assertEqual(len(f.spawns), 3)  # OS launcher is doubled.

    def test_worker_both_capture_preflights_bool_wire_and_owner_flags(self):
        tree = ast.parse(Path(worker.__file__).read_text(encoding='utf-8'))
        for flag, source in zip(FLAGS, SOURCES):
            check = worker_preflight(flag)
            for reference in (REFERENCE, xp2_bbg_inputs.REFERENCE):
                pins = source.source_dependencies(_PROFILE, reference=reference)
                check(True, NS(reference=reference, family='xp2-lan'), _PROFILE, dict(pins=pins))
                for image, family, ref, retained in ((None, 'xp2-lan', reference, pins),
                    (_XP1_PROFILE, 'xp2-lan', reference, pins), (_PROFILE, 'xp1-lan', reference, pins),
                    (replace(_PROFILE), 'xp2-lan', reference, pins),
                    (_PROFILE, 'xp2-lan', ('foreign','0'*64), pins),
                    (_PROFILE, 'xp2-lan', reference, {})):
                    with self.subTest(flag=flag, reference=reference[1], image=image), self.assertRaises(ValueError):
                        check(True, NS(reference=ref, family=family), image, dict(pins=retained))
            for value in (0, 1, None, 'true'):
                with self.assertRaises(ValueError): check(value, None, None, {})
            check(False, None, None, {})
            exprs = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
                     and ast.unparse(n) == "type(closure.get('" + flag + "', False)) is not bool"]
            self.assertEqual(len(exprs), 1)
            expression = compile(ast.Expression(exprs[0]), str(worker.__file__), 'eval')
            for value in (True, False, 0, 1, None, 'true'):
                self.assertEqual(eval(expression, {'closure':{flag:value}}), type(value) is not bool)
            assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                           and ast.unparse(n) == 'saved.' + flag + ' = ' + flag]
            self.assertEqual(len(assignments), 1)

    def test_view_independent_phases_stock_bbg_and_checkpoint(self):
        for index, unit_operations, mode in product(range(3), (False, True),
                                                    ('activation','foundation','beliefs','spent','absent')):
            # All independent subsets are covered on one retained predecessor;
            # all other retained predecessors exercise the complete chain.
            options_set = product((False, True), repeat=3) if index == 0 and not unit_operations else [(True,)*3]
            for options in options_set:
                with self.subTest(index=index, units=unit_operations, mode=mode, options=options):
                    decisions, obs = preceding(index, unit_operations=unit_operations)
                    prior = deepcopy(decisions); native = native_states(obs, mode)
                    saved = SavedLoadOwner.__new__(SavedLoadOwner)
                    for group in GROUPS: setattr(saved, 'explicit_' + group, {'stale':True})
                    with ExitStack() as stack:
                        queries = []
                        for enabled, group, adapter in zip(options, GROUPS, ADAPTERS):
                            def query(actual, observation, group=group):
                                self.assertIs(actual, saved); self.assertIs(observation, obs)
                                setattr(saved, 'explicit_' + group, deepcopy(native[group]))
                                return native[group]
                            q = stack.enter_context(patch.object(adapter, 'catalogue', side_effect=query))
                            queries.append(q)
                            if enabled: getattr(view, '_add_xp2_' + group)(saved, obs, decisions)
                    seal(decisions); validate(decisions, obs)
                    self.assertEqual({k:v for k,v in decisions['families'].items() if k not in KINDS}, prior['families'])
                    for enabled, group, adapter, query in zip(options, GROUPS, ADAPTERS, queries):
                        self.assertEqual(query.call_count, int(enabled))
                        self.assertEqual(group in decisions, enabled)
                        if enabled:
                            self.assertEqual(decisions[group], state(obs, mode)[group])
                            self.assertEqual(adapter.actions(native[group]),
                                [r['action'] for r in decisions['candidates'] if r['action']['kind'] == KINDS[GROUPS.index(group)]])
                    restored, receipt = network_turn.checkpoint_catalogue(decisions, prior, obs, core_sha256=XP2_CORE_SHA256)
                    self.assertEqual(restored, prior)
                    if any(options):
                        self.assertEqual(receipt['added_public_fields'], [g for g,e in zip(GROUPS,options) if e])
                    else: self.assertIsNone(receipt)

    def test_view_waiting_permissions_closed_and_actual_read_dispatch_order(self):
        for phase, strategic, tactical in product(('active','waiting','closed'), (False,True), (False,True)):
            decisions, obs = permissions_preceding(strategic=strategic, tactical=tactical, state=phase)
            saved = SavedLoadOwner.__new__(SavedLoadOwner)
            native = native_states(obs, 'activation')
            unavailable = phase != 'active' or not strategic
            for group, adapter in zip(GROUPS, ADAPTERS):
                setattr(saved, 'explicit_' + group, {'stale':True})
                with patch.object(adapter, 'catalogue', return_value=native[group]) as query:
                    getattr(view, '_add_xp2_' + group)(saved, obs, decisions, actions_closed=phase=='closed')
                self.assertEqual(query.call_count, int(not unavailable))
                if unavailable:
                    self.assertIsNone(decisions[group]); self.assertIsNone(getattr(saved, 'explicit_' + group))
            seal(decisions); validate(decisions, obs, closed=phase=='closed')
        prior, obs = preceding(); reduced = terminal_v11(prior); before = deepcopy(reduced)
        for group, adapter in zip(GROUPS, ADAPTERS):
            with patch.object(adapter, 'catalogue', side_effect=AssertionError('Closed query')):
                getattr(view, '_add_xp2_' + group)(saved, obs, reduced, actions_closed=True)
            self.assertIsNone(getattr(saved, 'explicit_' + group))
        self.assertEqual(reduced, before)
        # Execute only the real final view dispatch statements with spies. The
        # heavy native initial snapshot is not replaced with another reader.
        tree = ast.parse(Path(view.__file__).read_text(encoding='utf-8'))
        selected = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.BoolOp) and ast.unparse(n.test).startswith('core_sha256 == XP2_CORE_SHA256')
                    and any(flag in ast.unparse(n.test) for flag in FLAGS)]
        selected.sort(key=lambda n:n.lineno)
        self.assertEqual(len(selected), 3)
        module = compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])), str(view.__file__), 'exec')
        for options in product((False,True), repeat=3):
            calls=[]; owner=NS(**dict(zip(FLAGS,options)))
            scope=dict(core_sha256=XP2_CORE_SHA256, XP2_CORE_SHA256=XP2_CORE_SHA256,
                       saved=owner, observation=obs, decisions={}, actions_closed=False)
            for group in GROUPS:
                scope['_add_xp2_'+group] = lambda *a, group=group, **kw: calls.append(group)
            exec(module, scope)
            self.assertEqual(calls, [g for g,e in zip(GROUPS,options) if e])


    def fixture(self, family=0):
        f = Fixture(family); self.addCleanup(f.close); return f

    def execute_worker(self, f, *, available=True, result=None):
        from civ6_host.runtime import xp1_session_inputs
        decisions = dict(candidates=[dict(action=deepcopy(f.choice))] if available else [])
        with ExitStack() as stack:
            stack.enter_context(patch.object(view,'read',return_value=({},deepcopy(f.token.observation),decisions)))
            stack.enter_context(patch.object(xp1_session_inputs,'_write_once',return_value={'fixture':True}))
            stack.enter_context(patch.object(xp1_load_capability,'capability_source_scope',return_value=nullcontext()))
            execute = stack.enter_context(patch.object(f.saved,'execute',
                **({'wraps':f.saved.execute} if result is None else {'return_value':result})))
            value = worker._execute_xp1(f.saved,f.choice,0,0,Path(__file__).parent/'fixture-closure.json')
            return value, execute.call_count

    def test_actual_owner_three_actions_effect_refusal_and_drained_ready(self):
        for family,allowed in ((0,True),(0,False),(1,True),(2,True)):
            with self.subTest(family=GROUPS[family],can_start=allowed):
                f = self.fixture(family); adapter=ADAPTERS[family]
                self.assertIs(type(f.saved),SavedLoadOwner); self.assertIs(type(f.token),SavedContinuation)
                self.assertIs(type(f.backend.prefix),SavedLoadServices)
                self.assertEqual(f.backend.load_abi.core_sha256,XP2_CORE_SHA256)
                self.assertEqual(f.token.transport.transport_abi.core_sha256,XP2_CORE_SHA256)
                offered=adapter.catalogue(f.saved,f.token.observation)
                self.assertIn(f.choice,adapter.actions(offered))
                # Query remains eligible; the official request/revalidation is
                # the false path, not an invented successful empty archive.
                if family==0: f.deny_request=not allowed
                f.saved._running=False
                value,count=self.execute_worker(f)
                self.assertEqual(count,1)
                self.assertEqual(value,dict(status='completed' if allowed else 'refused',
                    reason=None if allowed else REFUSALS[family],requested_action=f.choice))
                self.assertEqual(f.token.sequence,1);self.assertFalse(f.backend.busy);self.assertFalse(f.saved.poisoned)
                self.assertEqual((f.token.transport.pending,f.deferred.pending),([],[]))
                self.assertEqual(f.token.publication_count,int(allowed))
                self.assertEqual(f.deferred.consumed_count,int(allowed and family==0))
                self.assertEqual(len([r for r in f.machine if r[0]=='request']),int(allowed))
                if family==0:
                    checks=[r for r in f.machine if r[0]=='can_start']
                    self.assertTrue(checks);self.assertEqual(len(checks)%2,0)
                    for loose,strict in zip(checks[::2],checks[1::2]):
                        self.assertEqual(loose[1:3],strict[1:3])
                        self.assertIs(loose[3],True);self.assertIs(strict[3],False)
                else:
                    self.assertFalse([r for r in f.machine if r[0]=='can_start'])
                    self.assertIn(('native_direct_request','FOUND_RELIGION' if family==1 else 'ADD_BELIEF'),f.machine)
                effects=[data for name,data in f.emitted if name=='official_explicit_religion_effect']
                self.assertEqual(len(effects),int(allowed))
                if allowed:
                    self.assertEqual(effects[0]['action'],f.choice)
                    self.assertFalse(effects[0]['automatic_choices_applied'])
                    if family==0:
                        self.assertTrue(effects[0]['receipt']['unit_consumed'])
                        self.assertEqual(f.earned,2)
                        self.assertEqual([u['id'] for u in f.token.observation['units']],[17])
                    elif family==1:self.assertEqual(f.created,f.choice['index'])
                    else:self.assertEqual(f.equipped,[f.choice['index']])
                # A refused command completes its protocol interval and still
                # allows an ordinary query; neither path invents pending work.
                with f.saved._attempt(): after=adapter.catalogue(f.saved,f.token.observation)
                if not allowed:self.assertEqual(after,offered)
                f.token.check_close();f.close()

    def test_founded_holy_city_outside_own_roster_preserves_public_religion_and_choices(self):
        f = self.fixture(2)
        observation = f.token.observation
        intact = beliefs.catalogue(f.saved, observation)
        self.assertIn(f.choice, beliefs.actions(intact))

        for descriptor in ((0, 7), (1, 65536)):
            with self.subTest(descriptor=descriptor):
                lookups = []
                f.holy_city_lookup = (lambda: descriptor,
                                      lambda *identity: lookups.append(identity))
                missing = beliefs.catalogue(f.saved, observation)
                public = religion_beliefs.project_snapshot(missing['own'], 0, 8,
                                                           observation=observation)
                self.assertEqual(lookups, [descriptor, descriptor])
                self.assertEqual(public['holy_city'], dict(player=-1, type=2, id=-1))
                self.assertFalse(public['holy_city_present'])
                self.assertNotIn(religion_beliefs.HOLY_CITY_DISPLAY_LABEL, public)
                self.assertEqual(public['own_religion'], intact['own']['own_religion'])
                self.assertEqual(beliefs.actions(missing), beliefs.actions(intact))

        f.holy_city_lookup = (lambda: (1, 23456), lambda *_: 'QUÉBEC'.encode('utf-8'))
        foreign = beliefs.catalogue(f.saved, observation)
        public = religion_beliefs.project_snapshot(foreign['own'], 0, 8,
                                                   observation=observation)
        self.assertEqual(public['holy_city_display_label'], 'VILLE SAINTE : QUÉBEC')
        self.assertEqual(public['holy_city'], dict(player=-1, type=2, id=-1))
        self.assertFalse(public['holy_city_present'])
        self.assertEqual(public['own_religion'], intact['own']['own_religion'])
        published = dict(schema=religion_beliefs.SCHEMA, player_id=0, turn=8,
                         own=public, beliefs=foreign['beliefs'])
        religion_beliefs.validate(published, 0, 8, observation=observation)
        self.assertEqual(religion_beliefs.actions(published), beliefs.actions(intact))

        names = iter((b'QUEBEC', b'PARIS'))
        f.holy_city_lookup = (lambda: (1, 23456), lambda *_: next(names))
        with self.assertRaisesRegex(Exception, 'holy city changed during observation'):
            beliefs.catalogue(f.saved, observation)

        readings = iter(((0, 7), (0, 8)))
        f.holy_city_lookup = (lambda: next(readings), lambda *_: None)
        with self.assertRaisesRegex(Exception, 'holy city changed during observation'):
            beliefs.catalogue(f.saved, observation)
        self.assertEqual(f.machine, [])

    def test_continuation_flags_never_inherit_xp1_or_accept_foreign_action(self):
        for family, flag, group in zip(range(3),FLAGS,GROUPS):
            f=self.fixture(family)
            for mode in ('disabled','nonbool','xp1_only','no_owner','bool_identity','extra_parameter'):
                action=deepcopy(f.choice); session=f.saved
                setattr(f.saved,flag,True); setattr(f.saved,'xp1_'+group,False)
                if mode=='disabled':setattr(f.saved,flag,False)
                elif mode=='nonbool':setattr(f.saved,flag,1)
                elif mode=='xp1_only':setattr(f.saved,flag,False);setattr(f.saved,'xp1_'+group,True)
                elif mode=='no_owner':session=None
                elif mode=='bool_identity':action['unit_id' if family==0 else 'index']=True
                else:action['custom_name']='unqualified'
                with self.subTest(family=group,mode=mode),self.assertRaises((ValueError,RuntimeError)):
                    f.token.execute(action,session=session)
                self.assertFalse(any(row[0]=='request' for row in f.machine))
            setattr(f.saved,flag,True); setattr(f.saved,'xp1_'+group,False)
            # The worker requery withdraws an expired choice before owner.execute.
            value,count=self.execute_worker(f,available=False)
            self.assertEqual(value['reason'],'native_action_no_longer_available');self.assertEqual(count,0)
            f.close()

    def test_worker_receipt_exact_profile_scalar_identity_site_and_refusal(self):
        for family, source in enumerate(SOURCES):
            f=self.fixture(family)
            completed=dict(status='completed',source_sha256=source.source_for(_PROFILE)[1])
            if family==0:
                completed.update(unit_id=18,x=1,y=0,founding_site=dict(player=0,type=2,id=65536))
            else:
                completed.update(selected_index=f.choice['index'],selected_hash=f.choice['hash'])
                if family==2:completed['selected_class']=f.choice['class']
            request=dict(can_start=False,request_invoked=False)
            if family==0:request['request_submitted']=False
            refused=dict(status='refused',source_sha256=source.source_for(_PROFILE)[1],
                         refusal_code=REFUSALS[family],request=request)
            for effect in (completed,refused) if family==0 else (completed,):
                value,count=self.execute_worker(f,result=dict(action=f.choice,effect=effect))
                self.assertEqual(value['status'],effect['status']);self.assertEqual(count,1)
            bad=[dict(completed,source_sha256=source.SOURCE[1]),dict(completed,status='pending'),
                 dict(refused,request=dict(request,can_start=0)),
                 dict(refused,request=dict(request,request_invoked=True)),dict(refused,refusal_code='invented')]
            scalar='unit_id' if family==0 else 'selected_index'
            bad.extend((dict(completed,**{scalar:True}),dict(completed,**{scalar:completed[scalar]+1})))
            if family==0:
                for site in (dict(player=1,type=2,id=65536),dict(player=False,type=2,id=65536),
                             dict(player=0,type=True,id=65536),dict(player=0,type=2,id=True)):
                    bad.append(dict(completed,founding_site=site))
                bad.append(dict(refused,request=dict(can_start=False,request_invoked=False)))
            if family!=0:bad.append(refused)
            if family==2:bad.append(dict(completed,selected_class='BELIEF_CLASS_FOUNDER'))
            for effect in bad:
                with self.subTest(family=GROUPS[family],effect=effect),self.assertRaises(RuntimeError):
                    self.execute_worker(f,result=dict(action=f.choice,effect=effect))
            self.assertEqual(f.machine,[]);f.close()


if __name__=='__main__':
    unittest.main()

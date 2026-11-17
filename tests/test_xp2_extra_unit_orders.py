"""Additional orders reuse the source-bound Lua, owner and public transport."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaRuntime
import pefile

from civ6_host import SessionClient
from civ6_host.contracts import capability_unit_orders as contract, network_turn
from civ6_host.runtime import expansion_city_growth, network_timer, xp2_extra_unit_orders as extra
from civ6_host.runtime import xp2_bbg_inputs, xp2_bundle_inputs, xp2_lan_unit_commands
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256, XP1_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.native import native_saved_unit_orders as shared
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
from civ6_host.runtime.paths import resource_root
from test_xp1_unit_orders import LUA_SETUP
from test_xp2_great_person_activation import seal
from test_xp2_human_perspective import PerspectiveFixture


def initial_response():
    path = resource_root()/('work/xp2-workmove/stock-writer/native-runs/'
                            'run-59f1539157f14da286bd9e1c1fb43f07/events.jsonl')
    if path.stat().st_size > 3*1024**2:
        raise ValueError('Unexpected retained response size')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != '649cef3fd68b1d2a34af1250b7b57b2bc8a3f4fdac0fbad45d1306fa158eedf5':
        raise ValueError('Retained native response changed')
    return json.loads(raw.splitlines()[5440])


class ExtraUnitOrdersTests(TestCase):
    def test_both_captures_and_relocated_live_descriptors(self):
        from struct import pack, unpack

        for reference in (xp2_bundle_inputs.REFERENCE,xp2_bbg_inputs.REFERENCE):
            self.assertGreater(len(extra.source_dependencies(reference,_PROFILE)),5)
        with self.assertRaises(ValueError):
            extra.source_dependencies(('foreign','0'*64),_PROFILE)
        base = 0x250000000
        with pefile.PE(_PROFILE.path,fast_load=True) as image:
            def read(address,size):
                rva = address-base
                raw = image.get_data(rva,size)
                if any(rva == row['table']['rva'] for row in extra.verify_source()['operations']):
                    pointers = unpack('<'+'Q'*(size//8),raw)
                    return pack('<'+'Q'*len(pointers),*(p-0x180000000+base for p in pointers))
                return raw
            core = SimpleNamespace(_handle=base,_civ6_host_execution_image=_PROFILE)
            lifetime = (core,object(),object(),object(),object(),xp2_bundle_inputs.REFERENCE)
            backend = SimpleNamespace(core=core,runtime=SimpleNamespace(read=read),
                                      load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256))
            saved = SimpleNamespace(backend=backend)
            with patch.object(expansion_city_growth,'_owner',return_value=lifetime):
                extra.bind(saved)
                self.assertTrue(extra.enabled(saved))
            with patch.object(expansion_city_growth,'_owner',return_value=(*lifetime[:-1],('foreign','0'*64))):
                with self.assertRaises(ValueError):
                    extra.enabled(saved)

    def test_lua_visibility_legality_and_parameterless_requests(self):
        lua = LuaRuntime(max_memory=4*1024**2)
        lua.execute(LUA_SETUP)
        for index, row in enumerate(extra.verify_source()['operations']):
            lua.execute("GameInfo.UnitOperations['%s']={Hash=%d,VisibleInUI=true}" %
                        (row['name'],row['hash']-2**32))
        options = dict(include_extended=True,core_sha256=XP2_CORE_SHA256)
        text = lua.execute(shared.catalog_source(0,8,**options).decode())
        value = shared.parse_catalog(text.encode(),0,8,include_extended=True)
        self.assertEqual(value['extensions'],contract.extension_metadata())
        offered = [a for a in shared.actions(value) if a['item_type'] in contract.EXTENDED_OPERATIONS]
        self.assertEqual(len(offered),2)
        for action in offered:
            self.assertEqual(lua.execute(shared.request_source(action,0,8,**options).decode()),'submitted')
        self.assertEqual(lua.globals().requests,2)
        lua.execute('moves=0')
        value = shared.parse_catalog(lua.execute(shared.catalog_source(0,8,**options).decode()).encode(),
                                     0,8,include_extended=True)
        self.assertFalse(any(a['item_type'] in contract.EXTENDED_OPERATIONS for a in shared.actions(value)))
        with self.assertRaises(ValueError):
            shared.catalog_source(0,8,include_extended=True,core_sha256=XP1_CORE_SHA256)
        with self.assertRaises(ValueError):
            shared.parse_catalog(text.encode(),0,8)

    def test_public_client_protocol_and_exact_historical_projection(self):
        response = initial_response()
        previous = deepcopy(response['decisions'])
        observation = response['observation']
        unit = observation['units'][0]
        choices = response['decisions']
        choices['unit_orders']['extensions'] = contract.extension_metadata()
        action = dict(kind='unit_order',unit_id=unit['id'],route='operation',
                      item_type=contract.EXTENDED_OPERATIONS[0],hash=0xe547bc17)
        choices['unit_orders']['offers'].append(dict(action=action,legal=True))
        candidate = network_turn.digest(action)
        choices['candidates'].append(dict(candidate_id=candidate,action=action))
        choices['families']['unit_order']['candidate_ids'].append(candidate)
        seal(choices)
        projected,transition = network_turn.checkpoint_catalogue(choices,previous,observation,
                                                               core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected,previous)
        self.assertIn('unit_orders.extensions',transition['added_public_fields'])
        identity = DiagnosticEpisodeIdentity(response['episode_id'],response['game_generation'])
        protocol = NetworkProtocol(identity,response['nonce'],initial_turn=observation['turn'],
                                   core_sha256=XP2_CORE_SHA256)
        validate_network_response(response,protocol,'reset')
        protocol.accept_response(response)
        def request(query):
            reply = deepcopy(response)
            reply.update(operation='act',sequence=query['sequence'],applied_action=action,
                command_result=dict(status='completed',reason=None,requested_action=action))
            decisions = reply['decisions']
            decisions['sequence'] = query['sequence']
            for group in decisions.values():
                if type(group) is dict and 'sequence' in group:
                    group['sequence'] = query['sequence']
            own = next(row for row in decisions['unit_orders']['units'] if row['unit_id']==unit['id'])
            own.update(activity_type=2,ready=False)
            seal(decisions)
            protocol.commit_reply(query,reply)
            protocol.accept_response(reply)
            return reply
        client = SessionClient(SimpleNamespace(reset=lambda:response,request=request,abort=Mock()))
        view = client.reset()
        view = client.act(observation['player_id'],view['decisions']['decision_id'],candidate)
        self.assertEqual(client.command_result['requested_action'],action)
        self.assertFalse(next(r for r in view['decisions']['unit_orders']['units'] if r['unit_id']==unit['id'])['ready'])

    def test_borrowed_orders_use_current_player_and_real_composed_transport(self):
        for name,hashed in ((contract.EXTENDED_OPERATIONS[0],0xe547bc17),
                            (contract.EXTENDED_OPERATIONS[1],0x9c0b44c6)):
            with self.subTest(name=name):
                f = PerspectiveFixture()
                self.addCleanup(f.close)
                f.enable_turn_fixture()
                f.enable_research_fixture()
                f.offers[1] = (name,hashed)
                f.strategic_allowed = True
                f.turn_rows[2] = (0,0,0)
                protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256,identity=f.token.identity,
                                           session=dict(turn=8),catalogue=None)
                protocol.selected = lambda query: network_turn.select_capability(protocol.catalogue,query['selection'])
                with patch.object(extra,'enabled',return_value=True),patch.object(network_timer,'read',return_value=False):
                    _,_,observation,choices,_ = xp2_lan_unit_commands.read_reply(f.saved,protocol,
                        dict(sequence=1,player_id=1,operation='observe'),(0,1))
                    protocol.catalogue = choices
                    network_turn.validate_catalogue(choices,protocol.identity,1,8,
                                                   player_id=1,observation=observation)
                    candidate = next(r['candidate_id'] for r in choices['candidates']
                                     if r['action'].get('item_type')==name)
                    _,_,_,after,receipt = xp2_lan_unit_commands.read_reply(f.saved,protocol,
                        dict(sequence=2,player_id=1,operation='act',selection=dict(
                             decision_id=choices['decision_id'],candidate_id=candidate)),(0,1))
                self.assertEqual(receipt['status'],'completed')
                self.assertEqual(receipt['requested_action']['item_type'],name)
                self.assertEqual(after['unit_orders']['extensions'],contract.extension_metadata())
                self.assertEqual(f.token.observation['player_id'],0)

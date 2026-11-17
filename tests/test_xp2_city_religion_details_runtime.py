"""XP2 city reader in the saved service and source boundaries, with Lua doubles."""

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock, patch

from lupa.lua51 import LuaError, LuaRuntime

from civ6_host.contracts import city_religion
from civ6_host.runtime import xp1_city_religion as shared
from civ6_host.runtime import xp2_city_religion_source as source
from civ6_host.runtime import xp2_bbg_inputs, xp2_bundle_inputs
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, _XP1_PROFILE
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp2_bbg_nested_events import BBGNestedScriptRuntime
from test_xp1_city_religion_details_runtime import _LUA, file_reader


def owner(reference,read,*,runtime_class=NativeScriptRuntime):
    prefix = SavedLoadServices.__new__(SavedLoadServices)
    runtime = runtime_class.__new__(runtime_class)
    runtime.registry = NS(validate=Mock())
    core = NS(_handle=0x180000000,_civ6_host_execution_image=_PROFILE)
    backend = NS(core=core,context=0x40,prefix=prefix,check_thread=Mock(),
                 runtime=NS(read=read),load_abi=NS(core_sha256=XP2_CORE_SHA256),
                 captured_bundle=NS(reference=reference))
    prefix.backend,prefix.core,prefix.context,prefix.runtime = backend,core,0x40,runtime
    prefix.ui_child,prefix.closed,prefix.quarantined = object(),False,False
    return NS(backend=backend,prefix=prefix,_check_query=Mock())


class XP2CityReligionDetailsRuntimeTests(TestCase):
    @classmethod
    def setUpClass(cls):
        image = resolve_path(Path(_PROFILE.path)).read_bytes()
        if sha256(image).hexdigest() != _PROFILE.image_sha256:
            raise AssertionError('Filed XP2 image differs')
        cls.read = staticmethod(file_reader(image))

    def test_dependencies_select_only_exact_capture_and_visible_ui(self):
        self.assertEqual(shared.source_for(_PROFILE),source.SOURCE)
        self.assertEqual(shared.source_for(_XP1_PROFILE),shared.DETAILS_SOURCE)
        proof = source.verify_source()
        stock = xp2_bundle_inputs.REFERENCE
        bbg = xp2_bbg_inputs.REFERENCE
        self.assertTrue(shared.supports(stock,_PROFILE))
        self.assertTrue(shared.supports(bbg,_PROFILE))
        self.assertFalse(shared.supports(stock,_XP1_PROFILE))
        self.assertFalse(shared.supports(list(stock),_PROFILE))
        for reference,profile,other in ((stock,'xp2-stock','xp2-bbg751'),(bbg,'xp2-bbg751','xp2-stock')):
            pins = shared.source_dependencies(_PROFILE,include_details=True,reference=reference)
            self.assertIn(proof['captured_inputs'][profile]['database']['sha256'],pins.values())
            self.assertNotIn(proof['captured_inputs'][other]['database']['sha256'],pins.values())
            self.assertEqual(proof['bbg_ui_selection']['sha256'] in pins.values(),reference==bbg)
            self.assertTrue(all(row['sha256'] in pins.values() for row in proof['stock_ui']))
            self.assertEqual(pins[str(Path(_PROFILE.path).resolve())],_PROFILE.image_sha256)
        for bad in (None,('other',stock[1]),list(stock)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                shared.source_dependencies(_PROFILE,include_details=True,reference=bad)
        with self.assertRaises(ValueError):
            shared.source_dependencies(_PROFILE,reference=stock)

    def test_installed_pe_spans_and_both_bound_lua_owners(self):
        self.assertGreater(source.verify_live(0x180000000,self.read),20)
        for relative in (0x68a2e1,0x6923fe,0x9c09f8):
            def damaged(address,size):
                data = self.read(address,size)
                offset = 0x180000000+relative-address
                return data if not 0<=offset<size else data[:offset]+bytes([data[offset]^1])+data[offset+1:]
            with self.subTest(relative=relative),self.assertRaisesRegex(ValueError,'Live Gathering Storm'):
                source.verify_live(0x180000000,damaged)
        for reference,runtime_class in ((xp2_bundle_inputs.REFERENCE,NativeScriptRuntime),
                                        (xp2_bbg_inputs.REFERENCE,BBGNestedScriptRuntime)):
            read = Mock(side_effect=self.read)
            saved = owner(reference,read,runtime_class=runtime_class)
            p = saved.prefix
            with patch('civ6_host.runtime.core_script_services.check_bound',return_value=object()) as lease:
                source.bind_prefix(p)
                count = read.call_count
                self.assertGreater(count,20)
                source.bind_prefix(p)
                self.assertEqual(read.call_count,count)
                lease.assert_called_with(p.runtime,p.context,p.core)
                p.runtime.registry.validate.assert_called_with(p.ui_child)
                p.ui_child = object()
                with self.assertRaisesRegex(ValueError,'another saved lifetime'):
                    source.bind_prefix(p)
        refused = owner(xp2_bbg_inputs.REFERENCE,Mock(),runtime_class=NativeScriptRuntime)
        with self.assertRaisesRegex(ValueError,'exact saved capture'):
            source.bind_prefix(refused.prefix)
        refused.backend.runtime.read.assert_not_called()

    def test_exact_xp2_selection_uses_shared_own_city_query_and_parser(self):
        saved = owner(xp2_bundle_inputs.REFERENCE,Mock())
        obs = dict(player_id=0,turn=42,width=4,height=3,plots=[],
                   cities=[dict(id=65536,owner=0),dict(id=65538,owner=0)])
        lua = LuaRuntime(encoding=None)
        controls = dict(owner=0,turn=42,observer=0,malformed=False)
        incoming_calls = []
        values = {0:0.5,2:-0.50390625,3:-0.5}
        def incoming(index):
            incoming_calls.append(index)
            return values[index]
        g = lua.globals()
        g.city_owner = lambda:controls['owner']
        g.local_turn = lambda:controls['turn']
        g.local_observer = lambda:controls['observer']
        g.malformed = lambda:controls['malformed']
        g.incoming = incoming
        saved.prefix.runtime.evaluate_text = evaluate = Mock(
            side_effect=lambda child,chunk,name,capacity:lua.execute(_LUA+chunk))
        with patch.object(source,'bind_prefix') as bind:
            result = shared.read_details(saved,obs)
            bind.assert_called_once_with(saved.prefix)
            saved._check_query.assert_called_once_with()
            self.assertEqual(evaluate.call_args.args,(saved.prefix.ui_child,
                shared.readback_source(0,42,obs,include_details=True),b'@xp2_own_city_religion_details'))
            self.assertEqual(incoming_calls,[3,0,2])
            self.assertEqual(result,dict(schema=city_religion.DETAILS_SCHEMA,player_id=0,turn=42,
                cities=[dict(city_id=65536,majority_religion=3,religions=[
                  dict(religion_index=0,followers=0,pressure_per_turn=1,lifetime_pressure=1),
                  dict(religion_index=2,followers=1,pressure_per_turn=-1,lifetime_pressure=-8388608),
                  dict(religion_index=3,followers=4,pressure_per_turn=0,lifetime_pressure=8388608),
                ]),dict(city_id=65538,majority_religion=-1,religions=[])]))
            controls['observer'] = 1
            with self.assertRaises(LuaError):
                shared.read_details(saved,obs)

"""Private own-target projection on the same Lua calls; no native execution."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve()
STAGED=HERE.parents[2].name=='private-targets'
if STAGED:
    STAGE=HERE.parents[2]; REVIEW=STAGE.parent; LAB=REVIEW.parents[2]; HOST=LAB.parent/'civ6-host'
else:
    HOST=HERE.parents[1]; LAB=Path(os.environ['CIV6_HOST_RESOURCE_ROOT'])
    REVIEW=LAB/'work/trade-common-client/congress-review-staging';STAGE=REVIEW/'private-targets'
sys.path[:0]=[str(HOST/'src'),str(HOST/'tests'),str(LAB/'work/lua-test-deps')]
import civ6_host.runtime,civ6_host.runtime.native
if STAGED:
    civ6_host.runtime.__path__.insert(0,str(STAGE/'files/src/civ6_host/runtime'))
    civ6_host.runtime.native.__path__.insert(0,str(STAGE/'files/src/civ6_host/runtime/native'))
from civ6_host.runtime.native import native_saved_world_congress as active
from civ6_host.runtime.native import native_world_congress_review as reader
from civ6_host.runtime import xp2_world_congress_source as profile
from lupa.lua51 import LuaRuntime,LuaError


def fixture(path,name):
    tree=ast.parse(path.read_text(encoding='utf8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
ACTIVE=fixture(LAB/'work/trade-common-client/congress-api-staging-runtime/test_staging_runtime.py','FIXTURE')
REVIEW_SETUP=fixture(REVIEW/'tests/test_native_world_congress_review.py','SETUP')


class PrivateTargetTests(unittest.TestCase):
    def active(self,enabled):
        lua=LuaRuntime(encoding=None,max_memory=12*1024*1024)
        lua.globals().segment=1;lua.globals().turnActive=True;lua.globals().favor=100
        lua.execute(ACTIVE.encode())
        lua.globals().PlayerOperations=lua.table_from({k.encode():v for k,v in profile.enum_values().items()})
        raw=lua.execute(active.source(0,61,3,administrative_targets=enabled))
        return active.parse(raw,0,61,3,administrative_targets=enabled),lua

    def review(self,configure=''):
        lua=LuaRuntime(encoding=None,max_memory=12*1024*1024)
        lua.execute(REVIEW_SETUP.encode())
        lua.execute(b"state.review.Resolutions[0]=fixtureResolution();state.review.Resolutions[0].PlayerSelections[0].ResolutionTarget='2'")
        lua.execute(configure.encode())
        return lua

    def parsed(self,lua):
        return reader.parse_envelope(lua.execute(reader.source(0,61,19,administrative=True)),0,61,19)

    def test_active_own_choice_mapping_keeps_public_mask_and_legacy_wire(self):
        value,lua=self.active(True);legacy,old=self.active(False)
        self.assertEqual(value['public'],legacy['public'])
        self.assertEqual(list(lua.globals().calls.values()),list(old.globals().calls.values()))
        self.assertNotIn('resolution_targets',legacy['private'])
        self.assertEqual(value['private']['resolution_targets'],[dict(resolution_hash=0xffffffff,
            resolution_type='FIXTURE',target_type='PlayerType',targets=[0,7])])
        hidden=value['public']['resolutions'][0]['targets'][1]
        self.assertIsNone(hidden['value']);self.assertIsNone(hidden['player_id'])
        with self.assertRaises(ValueError):active.parse(json.dumps(value).encode(),0,61,3)
        with self.assertRaises(ValueError):active.parse(json.dumps(legacy).encode(),0,61,3,administrative_targets=True)

    def test_active_private_identity_length_visible_value_and_bool_are_strict(self):
        original,_=self.active(True)
        for mutate in (lambda v:v['private']['resolution_targets'][0].update(resolution_hash=1),
                       lambda v:v['private']['resolution_targets'][0].update(targets=[0]),
                       lambda v:v['private']['resolution_targets'][0].update(targets=[1,7]),
                       lambda v:v['private']['resolution_targets'][0].update(targets=[True,7])):
            value=deepcopy(original);mutate(value)
            with self.assertRaises(ValueError):active.parse(json.dumps(value).encode(),0,61,3,administrative_targets=True)

    def test_review_sidecar_only_own_player_target_and_public_schema_unchanged(self):
        lua=self.review();value=self.parsed(lua)
        public=reader.parse(lua.execute(reader.source(0,61,19)),0,61,19)
        self.assertEqual(public,value['public'])
        self.assertEqual(value['private'],dict(player_id=0,turn=61,sequence=19,turn_segment=123,
            resolutions=[dict(resolution_type='RES_ONE',target_type='PlayerType',option=1,votes=2,target_player_id=2)]))
        own=next(v for v in public['resolutions'][0]['votes'] if v['voter']['player_id']==0)
        self.assertIsNone(own['target']['player_id']);self.assertIsNone(own['target']['value'])
        self.assertNotIn('target_player_id',json.dumps(public))
        self.assertNotIn('private',public)
        lua.execute(b"state.review.Resolutions[0].TargetType='ResourceType';state.review.Resolutions[0].ChosenThing='LOC_TARGET';for _,v in pairs(state.review.Resolutions[0].PlayerSelections)do v.ResolutionTarget='LOC_TARGET'end")
        self.assertEqual(self.parsed(lua)['private']['resolutions'],[])

    def test_review_index_mapping_and_explicit_minus_one_are_not_request_indices(self):
        lua=self.review("local r=state.review.Resolutions[0];r.PossibleTargets={'3','2'};r.PlayerSelections[0].ResolutionTarget='1'")
        self.assertEqual(self.parsed(lua)['private']['resolutions'][0]['target_player_id'],3)
        lua.execute(b"state.review.Resolutions[0].PlayerSelections[0].ResolutionTarget='-1'")
        self.assertEqual(self.parsed(lua)['private']['resolutions'][0]['target_player_id'],-1)

    def test_review_private_identity_own_vote_correspondence_and_visible_target_are_strict(self):
        original=self.parsed(self.review())
        changes=[lambda v:v['private'].update(sequence=20),
                 lambda v:v['private'].update(player_id=1),
                 lambda v:v['private']['resolutions'].append(deepcopy(v['private']['resolutions'][0])),
                 lambda v:v['private']['resolutions'][0].update(option=2),
                 lambda v:v['private']['resolutions'][0].update(votes=3),
                 lambda v:v['private']['resolutions'][0].update(target_player_id=True)]
        for change in changes:
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):reader.parse_envelope(json.dumps(value).encode(),0,61,19)
        visible=self.parsed(self.review("state.review.Resolutions[0].PlayerSelections[0].ResolutionTarget='1'"))
        visible['private']['resolutions'][0]['target_player_id']=2
        with self.assertRaises(ValueError):reader.parse_envelope(json.dumps(visible).encode(),0,61,19)
        with self.assertRaises(ValueError):reader.parse_envelope(json.dumps(original).encode(),True,61,19)

    def test_same_ui_admission_rejects_active_phase_before_any_review_getter(self):
        for stage in (11,12,13):
            lua=self.review('state.segment='+str(stage))
            with self.assertRaisesRegex(LuaError,'unavailable during session'):
                self.parsed(lua)
            self.assertEqual(lua.eval(b'state.reads'),0)
        for value in (None,1,'true'):
            with self.assertRaises(ValueError):reader.source(0,61,19,administrative=value)
            with self.assertRaises(ValueError):active.source(0,61,3,administrative_targets=value)


if __name__=='__main__':unittest.main()

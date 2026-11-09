"""Real reader/validator/matcher with native results mocked, not normalized."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest

from lupa.lua51 import LuaError,LuaRuntime
from civ6_host.runtime.native import native_world_congress_review as reader
from civ6_host.runtime import xp2_congress_cycle as cycle
from civ6_host.runtime.configuration_profiles import _source
from civ6_host.contracts import world_congress_review as contract
from civ6_host.contracts import world_congress as actions
import test_congress_private_targets as fixtures
import test_xp2_congress_cycle as cycle_fixtures


class ReviewOptionTests(unittest.TestCase):
    def lua(self):
        lua=LuaRuntime(encoding=None,max_memory=12*1024*1024)
        lua.execute(fixtures.REVIEW_SETUP.encode())
        lua.execute(b'state.review.Resolutions[0]=fixtureResolution()')
        return lua

    def parsed(self,lua):
        return reader.parse_envelope(lua.execute(reader.source(0,61,19,administrative=True)),0,61,19)

    def official_projection(self,lua):
        proof=_source(reader.SOURCE)
        row=next(row for row in proof['files'] if row['id']=='popup')
        raw=Path(row['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        text=raw.decode('utf-8-sig');start=text.index('function PopulateReview()')
        start=text.index('local aVotes:number = 0;',start)
        end=text.index('instance.UpVoteLabel:SetText(bVotes);',start)
        totals=re.sub(r':\s*(?:number|boolean|table|object|string)\b','',text[start:end])
        first=text.index('voterInstance.UpVoteLabel:SetText(kData.OptionChosen ~= 1',end)
        last=text.index('local playerName:string',first)
        voter=text[first:last]
        # Execute the installed UI arithmetic and per-voter branches verbatim.
        lua.execute(('function officialTotals(kResolutionData)\n'+totals+'return aVotes,bVotes end').encode())
        lua.execute(('function officialVoter(kData) local out={} local voterInstance={} '
            "for _,name in ipairs({'UpVoteLabel','DownVoteLabel','UpVoteStack','DownVoteStack'})do "
            'local key=name;voterInstance[key]={SetText=function(_,v)out[key]=v end,SetHide=function(_,v)out[key]=v end}end\n'
            +voter+'return out end').encode())

    def test_raw_int32_matches_official_lua_and_private_projection(self):
        lua=self.lua();self.official_projection(lua)
        for option in (-0x80000000,-1,0,1,2,3,0x7fffffff):
            lua.execute(('state.review.Resolutions[0].PlayerSelections[0].OptionChosen=%d'%option).encode())
            value=self.parsed(lua);row=value['public']['resolutions'][0]
            native=lua.globals().state.review.Resolutions[0]
            expected=lua.globals().officialTotals(native)
            self.assertEqual((row['votes_a'],row['votes_b']),expected)
            own=next(v for v in row['votes'] if v['voter']['player_id']==0)
            self.assertEqual(own['option'],option);self.assertEqual(own['option_label'],'A')
            self.assertEqual(value['private']['resolutions'][0]['option'],option)
            displayed=lua.globals().officialVoter(native.PlayerSelections[0])
            self.assertEqual(displayed[b'DownVoteLabel'],2 if option==1 else 0)
            self.assertEqual(displayed[b'UpVoteLabel'],0 if option==1 else 2)
            self.assertFalse('acknowledged' in value['public'])

    def test_bad_native_option_reports_field_and_bounded_value(self):
        for expression,shown in (('2147483648','2147483648'),('-2147483649','-2147483649'),
                                 ('0.5','0.5'),('true','true'),('nil','nil'),("'0'",'<string>')):
            lua=self.lua()
            lua.execute(('state.review.Resolutions[0].PlayerSelections[0].OptionChosen='+expression).encode())
            with self.subTest(expression=expression),self.assertRaisesRegex(LuaError,
                    re.escape('invalid congress review OptionChosen value='+shown)):
                self.parsed(lua)

    def test_signed_native_resolution_votes_follow_official_totals_without_clamp(self):
        lua=self.lua();self.official_projection(lua)
        for option in (1,0,2):
            for count in (-0x80000000,-1,0,0x7fffffff):
                lua.execute(('local v=state.review.Resolutions[0].PlayerSelections[0];'
                             'v.OptionChosen=%d;v.Votes=%d'%(option,count)).encode())
                value=self.parsed(lua);row=value['public']['resolutions'][0]
                expected=lua.globals().officialTotals(lua.globals().state.review.Resolutions[0])
                self.assertEqual((row['votes_a'],row['votes_b']),expected)
                self.assertEqual(value['private']['resolutions'][0]['votes'],count)
        lua.execute(b'state.review.Resolutions[0].PlayerSelections[0].Votes=-2147483649')
        with self.assertRaisesRegex(LuaError,'invalid congress review Votes value=-2147483649'):
            self.parsed(lua)

    def test_matching_raw_nonchoice_option_never_becomes_ballot_ack(self):
        public=cycle_fixtures.catalogue();action=cycle_fixtures.ballot(public)
        expected=cycle._expected(public,action)
        original=cycle_fixtures.review_for(public,action)
        self.assertEqual(action['resolutions'][0]['option'],2)
        for option in (-0x80000000,-1,0,3,0x7fffffff):
            value=deepcopy(original);value['resolutions'][0]['votes'][0]['option']=option
            parsed=reader.parse(json.dumps(value).encode(),value['player_id'],value['turn'],value['sequence'])
            result=cycle.match_ballot(expected,parsed)
            self.assertEqual(result['result_status'],'unresolved')
            self.assertEqual(result['reason'],'resolution_vote_or_target_mismatch')
            self.assertFalse(result['transport_acknowledged']);self.assertFalse(result['checkpoint_release_qualified'])
        result=cycle.match_ballot(expected,original)
        self.assertEqual(result['result_status'],'exact_ballot_matches')
        self.assertFalse(result['transport_acknowledged'])
        for field,value in (('option',0),('option',-1),('votes',-1),('votes',0)):
            invalid=deepcopy(action);invalid['resolutions'][0][field]=value
            with self.assertRaises(ValueError):actions.validate_action(invalid)


if __name__=='__main__':unittest.main()

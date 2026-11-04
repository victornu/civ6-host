"""Offline reviewer contracts; small synthetic rows do not qualify native turns.

Only observation/identity decoding and the already-covered scheduler body are
fixtures here. The parser, continuity, submit/update and FIFO reviewers are the
actual authored functions, extracted without loading any engine.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from civ6_host.contracts.network_turn import validate_turn_controls
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.stdout_transport_profiles import iter_records

REPO=Path(__file__).resolve().parents[1]
QUALIFIER=REPO/'tools/qualify_xp1_configuration.py'
EPISODE='00000000-0000-0000-0000-000000000001'


def functions():
    def observation(raw,pid):
        result=json.loads(raw)
        if result['player_id']!=pid:raise ValueError('fixture perspective mismatch')
        return result
    def command(action):
        if type(action) is not dict or set(action)!={'kind'} or action['kind'] not in ('end_turn','force_end_turn','unready_turn'):
            raise ValueError('fixture action shape')
    def decode(payload,*,core_sha256):
        if len(payload)!=8 or struct.unpack('<II',payload)!=(467357532,0):
            raise ValueError('fixture completion archive')
        return dict(player_id=0)
    ns=dict(Path=Path,json=json,hashlib=hashlib,DiagnosticEpisodeIdentity=DiagnosticEpisodeIdentity,
        iter_records=iter_records,
        parse_player_observation=observation,UNIT_SOURCE=('fixture','unit-source'),
        UI_SOURCE=('fixture','ui-source'),XP1_CORE_SHA256='xp1',validate_command=command,
        validate_turn_controls=validate_turn_controls,decode_archive=decode,
        reconcile_action_jobs=lambda before,after,rows,**kwargs:dict(offline_scheduler_fixture=True))
    names={'saved_load_events','saved_load_validate_transition','saved_load_validate_turn_transport',
           'saved_load_validate_turn'}
    nodes=[n for n in ast.parse(QUALIFIER.read_text(encoding='utf-8')).body
           if isinstance(n,ast.FunctionDef) and n.name in names]
    for node in nodes:
        node.body=[n for n in node.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(QUALIFIER),'exec'),ns)
    return ns


class TurnIntervals(unittest.TestCase):
    def setUp(self):
        self.ns=functions();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'events.jsonl'

    def parse(self,rows,**kwargs):
        self.path.write_bytes(b''.join(json.dumps(r).encode()+b'\n' for r in rows))
        return self.ns['saved_load_events'](self.path,**kwargs)[1]

    def markers(self,phase,seq):
        name='unit_commands' if phase=='command' else 'turn_update'
        return [dict(stage='before_xp1_saved_'+name,protocol_sequence=seq),
                dict(stage='xp1_saved_'+name+'_returned',protocol_sequence=seq)]

    def test_mixed_intervals_keep_protocol_gaps_and_exact_selected_jobs(self):
        command=self.markers('command',2);update=self.markers('update',5)
        rows=[dict(stage='xp1_saved_player_view_returned'),*command,update[0],
              dict(stage='fixture_job_event',number=9),update[1]]
        result=self.parse(rows,allow_turn_updates=True,require_interval='turn_update',command_sequence=5)
        self.assertEqual([(r['phase'],r['protocol_sequence']) for r in result['_transition_intervals']],
                         [('unit_commands',2),('turn_update',5)])
        self.assertEqual(result['turn_update_job_interval']['jobs'],[rows[-2]])
        self.assertEqual(len(result['_command_intervals']),1)
        self.assertEqual(len(result['_update_intervals']),1)

    def test_default_parser_does_not_admit_updates_or_repeated_commands(self):
        with self.assertRaisesRegex(ValueError,'Unknown saved native interval'):
            self.parse(self.markers('update',1),require_interval='turn_update')
        with self.assertRaisesRegex(ValueError,'Repeated saved Load result event'):
            self.parse(self.markers('command',1)+self.markers('command',2))

    def test_overlap_reversal_incomplete_and_foreign_return_are_refused(self):
        command=self.markers('command',2);update=self.markers('update',3)
        bad=[[*command,self.markers('update',2)[0]],
             [command[0],update[0],command[1],update[1]],
             [update[0]], [command[0],update[1]],
             [update[0],dict(stage='before_xp1_saved_loaded_close'),update[1]]]
        for rows in bad:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                self.parse(rows,allow_turn_updates=True)


class TurnReceipts(unittest.TestCase):
    def setUp(self):
        self.ns=functions()
        self.before=dict(player_id=0,turn=1,width=2,height=2,units=[],cities=[])
        self.previous=dict(episode_id=EPISODE,game_generation='native-'+EPISODE,
            sequence=4,publication_count=4,observation=self.before)
        self.action=dict(kind='force_end_turn')
        self.result=dict(action=self.action,effect=dict(status='completed',reason=None,requested_action=self.action),
            observation_before=copy.deepcopy(self.before),observation_after=copy.deepcopy(self.before),
            jobs_before={'fixture':1},jobs_after={'fixture':1},episode_id=EPISODE,game_generation='native-'+EPISODE,
            sequence=5,publication_count=6,unit_source={'source_sha256':'unit-source'},
            public_runtime_admitted=False,complete_action_space=False,game_update_called=False,
            same_save_official_transition_compared=False)
        self.controls=dict(schema='civ6-host.turn-controls.v1',player_id=0,turn=1,active=True,
            active_complete=True,can_unready=False,timer_elapsed=False)
        self.changed=dict(self.controls,active=False,active_complete=False)
        self.archive='8627c0d70000000068640b72'
        self.echo=struct.pack('<II',467357532,0).hex()
        self.gate=dict(stage='xp1_turn_request_ui_revalidated',action=self.action,
            turn_availability=dict(end_turn=False,force_end_turn=True,unready_turn=False),
            source_sha256='ui-source',core_sha256='xp1')
        self.rows=[self.gate,
            dict(stage='native_forced_end_turn_parameters_verified',player_id=0,reason='UserForced',
                 native_string_setter_used=True,native_reason_converter_used=True,string_roundtrip_verified=True),
            dict(stage='before_native_end_turn_request',player=0,action='0x2cc9a6b5'),
            self.queued(self.archive),
            dict(stage='native_end_turn_serialization_verified',player=0,archive_hex=self.archive,native_parameter_object=True),
            *self.delivered(self.archive),self.queued(self.echo),
            dict(stage='before_native_game_turn_complete_echo',archive_hex=self.echo,player_id=0,archive_fabricated=False),
            *self.delivered(self.echo),
            dict(stage='native_game_turn_complete_echo_verified',archive_hex=self.echo,player_id=0,
                 core_dispatcher_used=True,processed_before_next_public_update=True),
            dict(stage='official_lan_turn_request_effect',player_id=0,action=self.action,
                 before=self.controls,after=self.changed,network_ack_inferred=False,
                 turn_advanced=False,strategic_training_ready=False)]
        self.interval=dict(begin={'event':{'protocol_sequence':8}},returned={'event':{'protocol_sequence':8}},
                           commands=self.rows,jobs=[])

    @staticmethod
    def queued(payload):
        return dict(stage='native_command_archive_queued',archive_hex=payload,bytes=len(bytes.fromhex(payload)),
                    queue_count=1,delivery_pending=True,action_applied=False)

    @staticmethod
    def delivered(payload):
        return [dict(stage='native_command_received_in_core_queue',archive_hex=payload,
                     native_owned_copy=True,action_applied=False),
                dict(stage='before_native_command_queue_drain'),
                dict(stage='native_command_queue_drained',native_dispatcher_used=True)]

    def validate(self,*,update=False):
        self.ns['saved_load_validate_transition'](self.result,self.interval,self.previous,update=update)
        return self.ns['saved_load_validate_turn'](self.result,self.interval,self.result['jobs_before'],update=update)

    def test_internal_sequence_is_not_protocol_sequence(self):
        receipt=self.validate()
        self.assertEqual(receipt['turn_request_status'],'completed')
        self.assertFalse(receipt['network_ack_inferred'])
        self.assertEqual(receipt['transport']['delivered_archives'],[self.archive,self.echo])

    def test_changed_episode_observation_sequence_and_false_ack_are_refused(self):
        for key,value in [('sequence',8),('sequence',True),('episode_id','other'),
                          ('publication_count',4),('game_update_called',True)]:
            original=self.result[key];self.result[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.validate()
            self.result[key]=original
        self.result['observation_before']=dict(self.before,turn=2)
        with self.assertRaises(ValueError):self.validate()
        self.result['observation_before']=copy.deepcopy(self.before)
        self.rows[-1]['network_ack_inferred']=True
        with self.assertRaisesRegex(ValueError,'actual qualified native control'):self.validate()

    def test_fifo_cannot_drop_forge_or_reorder_completion(self):
        original=copy.deepcopy(self.rows)
        for mutation in ('drop_receive','archive_mismatch','fabricated_echo','missing_echo_return','unchanged_controls'):
            self.interval['commands']=copy.deepcopy(original);rows=self.interval['commands']
            if mutation=='drop_receive':rows.pop(next(i for i,r in enumerate(rows) if r['stage']=='native_command_received_in_core_queue'))
            elif mutation=='archive_mismatch':next(r for r in rows if r['stage']=='native_command_received_in_core_queue')['archive_hex']='ff'
            elif mutation=='fabricated_echo':next(r for r in rows if r['stage']=='before_native_game_turn_complete_echo')['archive_fabricated']=True
            elif mutation=='missing_echo_return':rows.pop(next(i for i,r in enumerate(rows) if r['stage']=='native_game_turn_complete_echo_verified'))
            else:rows[-1]['after']=copy.deepcopy(rows[-1]['before'])
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate()

    def test_poll_authenticates_one_update_without_action_or_ack(self):
        self.result.update(action=None,effect=None,game_update_called=True,publication_count=5,
                           observation_after=dict(self.before,turn=2))
        self.interval['commands']=[dict(stage='before_native_game_update',outer_slot='0x90',game_slot='0x30'),
                                  dict(stage='native_game_update_returned',eligible_for_training=False)]
        self.assertEqual(self.validate(update=True)['native_turn_advanced'],1)
        for mutation in ('missing_return','duplicate_update','fake_effect','fake_action'):
            result=copy.deepcopy(self.result);rows=copy.deepcopy(self.interval['commands'])
            if mutation=='missing_return':self.interval['commands'].pop()
            elif mutation=='duplicate_update':self.interval['commands']+=rows
            elif mutation=='fake_effect':self.result['effect']={'status':'completed'}
            else:self.result['action']=self.action
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate(update=True)
            self.result=result;self.interval['commands']=rows

    def test_refused_ui_gate_does_not_become_an_ack_or_native_command(self):
        self.gate['turn_availability']['force_end_turn']=None
        self.result.update(effect=dict(status='refused',reason='native_turn_ui_gate_unknown',requested_action=self.action),
                           publication_count=4)
        self.interval['commands']=[self.gate]
        receipt=self.validate()
        self.assertEqual(receipt['turn_request_status'],'refused')
        self.assertEqual(receipt['transport']['delivered_archives'],[])
        self.result['effect']['status']='completed';self.result['effect']['reason']=None
        self.result['publication_count']=5
        with self.assertRaises(ValueError):self.validate()

    def test_repeated_inactive_force_authenticates_submission_only(self):
        self.result['effect'].update(status='submitted',reason='native_turn_controls_unchanged')
        self.rows[-1].update(stage='official_lan_turn_request_submitted',
                             before=copy.deepcopy(self.changed),after=copy.deepcopy(self.changed))
        self.assertEqual(self.validate()['turn_request_status'],'submitted')
        for mutation in ('fake_completion','wrong_reason','changed_controls','active','wrong_kind','false_ack'):
            original_result=copy.deepcopy(self.result); original_rows=copy.deepcopy(self.rows)
            if mutation=='fake_completion':self.result['effect']['status']='completed'
            elif mutation=='wrong_reason':self.result['effect']['reason']=None
            elif mutation=='changed_controls':self.rows[-1]['after']['active']=True
            elif mutation=='active':
                self.rows[-1]['before']['active']=True; self.rows[-1]['after']['active']=True
            elif mutation=='wrong_kind':
                self.result['action']={'kind':'end_turn'}
                self.result['effect']['requested_action']={'kind':'end_turn'}
                self.rows[0]['action']={'kind':'end_turn'}
                self.rows[0]['turn_availability']['end_turn']=True
                self.rows[-1]['action']={'kind':'end_turn'}
            else:self.rows[-1]['network_ack_inferred']=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate()
            self.result=original_result; self.rows=original_rows; self.interval['commands']=self.rows


if __name__=='__main__':unittest.main()

"""Minimal explicit-choice client: one JSON command and public response per line.

Install matching civ6-host-client/runtime wheels first. The caller supplies a
qualified private configuration; this example never prepares a world or chooses
an action. It uses the same client API that a custom model would use.
"""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--mode',choices=('hotseat','lan'),default='hotseat')
    args=parser.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8'))
    required={'resources','official_bundle','ui_profile','prepared_capture','private_resources','session_options'}
    if type(config) is not dict or set(config)!=required or type(config['session_options']) is not dict:
        raise ValueError('Expected explicit host resources, capture, profile and session_options')
    if set(config['session_options']) & (required-{'session_options'}):
        raise ValueError('Session options cannot override resource identities')
    from civ6_host import HotseatClient, SessionClient
    from civ6_host.runtime.backend import LocalHotseatBackend, NetworkBackend
    backend_config={k:v for k,v in config.items() if k!='session_options'}
    if args.mode=='lan':
        if backend_config.pop('ui_profile') is not None:
            raise ValueError('LAN must not reuse a Hotseat UI profile')
        backend=NetworkBackend(**backend_config,**config['session_options'])
        client=SessionClient(backend)
    else:
        backend=LocalHotseatBackend(**backend_config,**config['session_options'])
        client=HotseatClient(backend)
    try:
        for line in sys.stdin:
            command=json.loads(line)
            if type(command) is not dict:raise ValueError('Command must be an object')
            operation=command.get('op')
            if args.mode=='lan':
                if operation in ('reset','close') and set(command)=={'op'}:
                    response=getattr(client,operation)()
                elif operation in ('observe','poll') and set(command)=={'op','player_id'}:
                    response=getattr(client,operation)(command['player_id'])
                elif operation=='act' and set(command) in (
                        {'op','player_id','decision_id','candidate_id'},
                        {'op','player_id','decision_id','candidate_id','parameters'}):
                    response=client.act(command['player_id'],command['decision_id'],
                        command['candidate_id'],command.get('parameters'))
                elif operation=='session' and set(command)=={'op'}:
                    response=client.session_state
                elif operation=='command_result' and set(command)=={'op'}:
                    response=client.command_result
                else:
                    raise ValueError('Use an explicit actor for LAN observe/poll/act; reset/close/session/command_result take no actor')
            elif operation in ('reset','observe','close') and set(command)=={'op'}:
                response=getattr(client,operation)()
            elif operation=='act' and set(command) in (
                    {'op','decision_id','candidate_id'},
                    {'op','decision_id','candidate_id','parameters'}):
                response=client.act(command['decision_id'],command['candidate_id'],
                                    parameters=command.get('parameters'))
            elif operation=='player_view' and set(command)=={'op','player_id'}:
                response=client.player_view(command['player_id'])
            else:
                raise ValueError('Use reset, observe, act with decision_id/candidate_id, player_view with player_id, or close')
            print(json.dumps(response,ensure_ascii=False,separators=(',',':')),flush=True)
            if operation=='close':return 0
    finally:
        client.abort()
    return 0


if __name__=='__main__':raise SystemExit(main())

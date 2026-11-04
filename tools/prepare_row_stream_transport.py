"""Stage an exact file-transport derivative; never install it or start Civ6."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA256='333c5755b080fd7d00f53802c3ee606380fbd197a118411cf568662e082549c2'

def derive(source, addition):
    def change(old,new):
        nonlocal source
        if source.count(old)!=1:raise ValueError('Capture transport source boundary changed')
        source=source.replace(old,new)
    change('  local function uiAvailability(command)',addition+'\n\n  local function uiAvailability(command)')
    change('      and command.op~="database_capture" and command.op~="ui_availability"',
           '      and command.op~="database_capture" and command.op~="database_row_stream" and command.op~="ui_availability"')
    change('    elseif command.op=="database_capture" then databaseCapture(command)',
           '    elseif command.op=="database_capture" then databaseCapture(command)\n    elseif command.op=="database_row_stream" then databaseRowStream(command)')
    return source

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA256:raise ValueError('Unreviewed file transport source')
    addition=ROOT/'lua/capture_row_stream.lua';text=derive(raw.decode('utf8'),addition.read_text(encoding='utf8'))
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists():raise ValueError('Fresh private staging directory required')
    output.mkdir(parents=True);target=output/'Civ6RLFileTransport.lua';target.write_text(text,encoding='utf8',newline='\n')
    def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    report=dict(schema='civ6-host.row-stream-transport-preparation.v1',source=ref(args.source),addition=ref(addition),
        output=ref(target),preparer=ref(Path(__file__)),installed=False,official_game_started=False)
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':main()

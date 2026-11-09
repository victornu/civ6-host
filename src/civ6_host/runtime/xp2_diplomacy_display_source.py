"""Selected XP2 Lua dialogue/read boundaries, with independent source identity."""
import hashlib
from pathlib import Path

from .execution_images import identity
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/bbg751-turn-source-scope/war-confirmation/major-dialogue/source-profile.json',
        'c174fdd3559007895a8bf1dbdaf0e0cbcf3b0ae8cf807788b34d331dbb856c3f')
NAMES=frozenset(('RequestSession','AddResponse','CloseSession','HasQueuedSession',
    'IsSessionIDOpen','GetKeyName','FindTextKey','FindReasonTextKey',
    'FindReasonAgendaTextKey','GetDiplomaticAI','GetDiplomaticStateIndex',
    'IsRevealed','IsResourceVisible'))


def source(*,execution_image):
    identity(execution_image)
    if execution_image.id!='xp2-gamecore-current-092abfbb':
        raise ValueError('XP2 dialogue display runtime is not admitted')
    value=load_pinned_json(resolve_path(resource_root()/SOURCE[0]),SOURCE[1])
    if (value['schema']!='civ6-host.xp2-dialogue-lua-boundary-source.v1'
            or value['actual_image']['sha256']!=execution_image.image_sha256
            or value['reference_core_sha256']!=execution_image.reference_core_sha256
            or {row['name'] for row in value['bindings']}!=NAMES
            or len(value['functions'])!=20
            or value['from_mood_absent_from_common_event'] is not True
            or value['scope']['queued_exit'] is not False):
        raise ValueError('XP2 dialogue Lua/source selection changed')
    from .xp2_statement_source import source as statement_source
    statement=statement_source(execution_image=execution_image)
    if 345504345 in {int(row['key'],16) for row in statement['common_statement_fields']}:
        raise ValueError('XP2 statement now supplies the previously absent FromMood field')
    return value


def source_dependencies(*,execution_image):
    value=source(execution_image=execution_image)
    refs=[dict(path=str(resource_root()/SOURCE[0]),sha256=SOURCE[1]),
          value['extractor'],value['capture_helper'],*value['official_files'].values(),
          *value['shared_sources'].values()]
    from .native import native_diplomacy_display986 as display
    from .native import native_diplomacy_default as handler
    from .native import native_revealed_plot_observation as revealed
    refs.extend(dict(path=str(path),sha256=sha) for path,sha in (
        (display.PROOF,display.PROOF_SHA),(handler.PROOF_PATH,handler.PROOF_SHA256),
        (revealed._PROOF_PATH,revealed._PROOF_SHA256)))
    pins={}
    for row in refs:
        path=resolve_path(Path(row['path'])).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('XP2 dialogue source dependency changed: '+str(path))
        pins[str(path)]=row['sha256']
    return pins


def verify_live(base,read,*,execution_image):
    value=source(execution_image=execution_image)
    for name,body in value['functions'].items():
        for fragment in body['fragments']:
            raw=bytes.fromhex(fragment['raw_hex'])
            if hashlib.sha256(raw).hexdigest()!=fragment['sha256']:
                raise ValueError('XP2 dialogue capture changed: '+name)
            address=base+int(fragment['start_rva'],16)
            for offset in range(0,len(raw),4096):
                expected=raw[offset:offset+4096]
                if read(address+offset,len(expected))!=expected:
                    raise ValueError('XP2 dialogue Lua binding changed: '+name)
    return value

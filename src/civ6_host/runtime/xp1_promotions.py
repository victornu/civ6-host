"""Source-bound promotions for the stock Rise and Fall capture."""

from hashlib import sha256
from pathlib import Path
from struct import pack

from civ6_host.contracts.unit_promotions import validate_action, validate_catalogue
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .native import native_saved_promotions as promotions
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1trade/xp1-unit-promotion-source.json',
          'b044f7604ceae2b474667b0332bb307f4ed4a8446067fca8bf2f34bbab94b204')
_ARCHIVE = 0x493830af
_REGISTRY_SLOT = 14


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def verify_source():
    proof = _source(SOURCE)
    route,packet = proof['route'],proof['packet']
    if (proof['schema'] != 'civ6-host.xp1-unit-promotion.static.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['gameplay_rules_reimplemented'] is not False
            or (proof['image']['sha256'],proof['image']['reference_core_sha256']) !=
               (_XP1_PROFILE.image_sha256,XP1_CORE_SHA256)
            or (route['command'],route['parameter'],route['result']) != (0xb4edd43f,0xc8b78a39,0x315247e7)
            or (packet['message_type'],packet['format'],packet['length']) != (_ARCHIVE,'<IHH6I',32)
            or packet['expected_constants'] != dict(entity_type=1,command_slot=_REGISTRY_SLOT,
                    auxiliary_flags=0,parameter_type=1,parameter_metadata=0)):
        raise ValueError('Rise and Fall promotion source differs')
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Promotion sources require the installed Rise and Fall image')
    proof = verify_source()
    promotions.verify_source()
    witnesses = proof['witnesses']
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]),dict(path=REFERENCE[0],sha256=REFERENCE[1]),
            proof['image'],proof['executable'],*proof['parents'].values(),*proof['ui_sources'].values()]
    refs.extend(row['trace'] for key,row in witnesses.items() if key!='fixture')
    refs.extend(witnesses['fixture'][key] for key in ('checkpoint','database'))
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root()/path)
        if pins.setdefault(str(path.resolve()),row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall promotion source pins')
    verify_pinned_files(pins)
    return pins


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    backend, prefix = saved.backend,saved.prefix
    core = backend.core
    if (getattr(saved,'xp1_promotions',False) is not True
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(backend.captured_bundle.reference,getattr(core,'_civ6_host_execution_image',None))):
        raise ValueError('Promotion requires the exact Rise and Fall saved owner')
    lifetime = (core,prefix)
    if getattr(saved,'_xp1_promotion_lifetime',None) == lifetime:
        return
    proof = verify_source()
    base, read = core._handle,backend.runtime.read
    for span in (*proof['core_bodies'],*proof['enums'].values()):
        raw = bytes.fromhex(span['raw_hex'])
        if (len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']
                or read(base+span['rva'],len(raw)) != raw):
            raise ValueError('Live Rise and Fall promotion code differs')
    for row in proof['bindings'].values():
        raw = bytes.fromhex(row['bytes_hex'])
        name = row['name'].encode('ascii')+b'\0'
        if (read(base+row['registration_rva'],len(raw)) != raw
                or read(base+row['name_rva'],len(name)) != name):
            raise ValueError('Live Rise and Fall promotion registration differs: '+row['name'])
    for table in proof['tables'].values():
        for slot in table['slots']:
            pointer = base+slot['target_rva']
            if read(base+table['rva']+slot['offset'],8) != pointer.to_bytes(8,'little'):
                raise ValueError('Live Rise and Fall promotion vtable differs')
    saved._xp1_promotion_lifetime = lifetime


def catalogue(saved, observation):
    _bind(saved,active=False)
    pid,turn = observation['player_id'],observation['turn']
    raw = promotions.catalog(saved.prefix,turn,player_id=pid)
    result = dict(player_id=pid,turn=turn,offers=raw['offers'],units=[
        dict(unit_id=row['unit_id'],experience_points=int(row['experience_token']),promotions=row['promotions'])
        for row in raw['units']])
    validate_catalogue(result,pid,turn,observation=observation)
    saved.explicit_promotions = raw
    return result


def validate_archive(payload, actor, action):
    validate_action(action)
    if type(payload) is not bytes or type(actor) is not int or not 0<=actor<=63:
        raise ValueError('Invalid Rise and Fall promotion archive or actor')
    expected = pack('<IHH6I',_ARCHIVE,actor,1,action['unit_id'],_REGISTRY_SLOT,0,1,0,action['hash'])
    if payload != expected:
        raise ValueError('Rise and Fall promotion archive differs from the selected promotion')
    return sha256(payload).hexdigest()


def apply(saved, action, observation):
    _bind(saved,active=True)
    return promotions.apply(saved,saved.prefix,action,observation['turn'],observation,
        player_id=observation['player_id'],archive_validator=validate_archive)

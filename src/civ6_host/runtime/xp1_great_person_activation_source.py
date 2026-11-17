"""Installed XP1 command activation source; no class-wide native acceptance claim."""
from hashlib import sha256
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .xp1_saved_load import REFERENCE
from . import xp1_prophet_activation_source as shared
from . import xp1_unit_orders_profile as commands

SOURCE = ('work/x1trade/great-person-activation-stage/9d56cd2ca813c46fe43e39e3e94526c31e4c4116e0be6e3089dff6e8d9edc045.json',
          '9d56cd2ca813c46fe43e39e3e94526c31e4c4116e0be6e3089dff6e8d9edc045')
EFFECT_SOURCE = ('work/x1trade/great-person-activation-stage/b052bddbcca73a87a41eb781780e7b535eaccf981f05fd7238f8c5783367c0ae.json',
                 'b052bddbcca73a87a41eb781780e7b535eaccf981f05fd7238f8c5783367c0ae')
COMPLETION_SOURCE = ('work/x1trade/great-person-activation-runtime-stage/cae30ea920564f9044a96ff8334d2ba5781fed9c81e72af56fe8b30be2194309.json',
                     'cae30ea920564f9044a96ff8334d2ba5781fed9c81e72af56fe8b30be2194309')
COMMAND_HASH = 0x165502d8
ARCHIVE_KIND = 0x493830af


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def verify_source():
    proof = _source(SOURCE)
    contract, route = proof['public_contract'], proof['route']
    if (proof['schema'] != 'civ6-host.xp1-great-person-activation.static.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or proof['image']['reference_abi_sha256'] != XP1_CORE_SHA256
            or proof['native_execution'] is not False
            or (contract['name'],contract['hash_u32'],contract['parameters']) !=
               ('UNITCOMMAND_ACTIVATE_GREAT_PERSON',COMMAND_HASH,())
            or contract['wrong_name_present'] is not False
            or (route['UI_CanStartCommand'],route['UI_RequestCommand'],route['archive_kind']) !=
               ('0x5dbb50','0x5de980',hex(ARCHIVE_KIND))
            or proof['code_spans']['apply']['entry_rva'] != '0x56fb20'
            or proof['code_spans']['legality']['entry_rva'] != '0x56ef90'
            or proof['code_spans']['post_command_notification']['entry_rva'] != '0x35330'
            or proof['callable_vtables']['activation_command']['targets'][2:7] !=
               ('0x56ef90','0x6b4ee0','0x56fb20','0x35250','0x360f0')
            or proof['validation']['native_acceptance_claimed'] is not False):
        raise ValueError('Installed Great Person command source differs')
    effect = _source(EFFECT_SOURCE)
    if effect['source']['sha256'] != SOURCE[1] or effect['native_execution'] is not False:
        raise ValueError('Great Person effect scope differs')
    completion = _source(COMPLETION_SOURCE)
    if (completion['schema'] != 'civ6-host.xp1-gp-activation.completion-review.v1'
            or completion['image'] != proof['image'] or completion['native_execution'] is not False
            or completion['parents'][0]['sha256'] != SOURCE[1]
            or completion['new_span']['rva'] != '0x179320'):
        raise ValueError('Great Person completion source differs')
    commands.verify_source()
    return proof


def require_actions():
    proof = verify_source()
    shared.require_actions()
    from . import xp1_great_work_source as works
    unit_source = getattr(works,'unit_source',None)
    if not callable(unit_source):
        raise ValueError('Great Person activation requires the qualified Great Work unit producer')
    unit_source(_XP1_PROFILE)
    from .native.native_event_fc7db95e import verify_source_evidence
    verify_source_evidence()
    for ref in proof['references']:
        _source((ref['path'],ref['sha256']))
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Great Person activation requires the exact installed Rise and Fall image')
    proof = require_actions()
    from . import xp1_great_work_source as works
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .execution_images import runtime_source_pins
    pins = shared.source_dependencies(image)
    selected_commands=runtime_source_pins(commands.source_dependencies(),execution_image=image)
    for dependencies in (works.source_dependencies(image),selected_commands):
        for path,digest in dependencies.items():
            if pins.setdefault(path,digest) != digest:
                raise ValueError('Great Person source dependency conflict')
    refs = [dict(path=p,sha256=h) for p,h in (SOURCE,EFFECT_SOURCE,COMPLETION_SOURCE)]
    refs += [*proof['references'],*proof['ui'],proof['observed_database']]
    for row in refs:
        path=str(resolve_path(resource_root()/row['path']).resolve())
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Great Person source dependency conflict')
    verify_pinned_files(pins)
    return pins


def verify_live(base, read, *, image):
    if image is not _XP1_PROFILE or type(base) is not int or base<=0 or not callable(read):
        raise ValueError('Great Person source requires its installed image and owned reader')
    proof=verify_source()
    spans=[row for body in proof['code_spans'].values() for row in body['fragments']]
    spans.append(proof['getters']['registration_window'])
    spans.append(_source(COMPLETION_SOURCE)['new_span'])
    for row in spans:
        address=base+int(row['rva'],16)
        raw=b''.join(read(address+i,min(4096,row['length']-i)) for i in range(0,row['length'],4096))
        if sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Live Great Person activation source differs at '+row['rva'])
    for row in proof['callable_vtables'].values():
        expected=b''.join((base+int(rva,16)).to_bytes(8,'little') for rva in row['targets'])
        if read(base+int(row['rva'],16),len(expected))!=expected:
            raise ValueError('Live Great Person activation vtable differs')
    commands.verify_live(base,read,core_sha256=XP1_CORE_SHA256)
    return dict(source_sha256=SOURCE[1],complete_spans=len(spans),native_execution=False)


def bind_prefix(prefix, *, action=False):
    # These are the existing same-image script/A0/removal/turn/transport owners;
    # this does not select the Prophet operation or invoke its religion logic.
    shared.bind_prefix(prefix,action=action)
    from . import xp1_great_work_source as works
    require_actions()
    backend=prefix.backend
    consumer=prefix.event_arguments.consumer
    for row in verify_source()['events']:
        if not consumer.handles_kind(int(row['kind'],16)):
            raise ValueError('Great Person activation has an unqualified event owner: '+row['kind'])
    lifetime=(prefix.core,prefix,prefix.runtime)
    if getattr(prefix,'_xp1_great_person_activation_lifetime',None)!=lifetime:
        verify_live(prefix.core._handle,backend.runtime.read,image=prefix.core._civ6_host_execution_image)
        works.verify_live(prefix.core,backend.runtime.read)
        prefix._xp1_great_person_activation_lifetime=lifetime

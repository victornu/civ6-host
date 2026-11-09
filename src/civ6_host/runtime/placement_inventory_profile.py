"""Source and lifetime binding for the visible own-city placement inventory."""
from dataclasses import dataclass
from pathlib import Path
import hashlib

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from . import xp1_production_placement_profile as placement

SOURCE=('work/host-extensions/xp1-placement-inventory-static/source-v1.json',
        'c8bec08656482cd145eff777f5c91338a52c3b20aff57ad3b50d5caf5e281fa1')
_EXTRA=(0x671b0,0x16f220,0x16f4f0,0x109f0,0x9b6a0,0x9a140,0x25b20,
        0x6a27f0,0x6a2ad0,0x16e0f0,0xde050)


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_inventory_source import SOURCE as selected
        return selected
    raise ValueError('Unknown placement inventory engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_inventory_source import verify_source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Placement inventory requires the qualified XP1 source')
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-placement-inventory-source.v1'
            or p['image']['sha256']!=core_sha256 or p['native_execution'] is not False
            or p['process_memory_read'] is not False
            or set(p['functions'])!={hex(rva) for rva in _EXTRA}
            or p['validation']!=dict(all_instruction_bytes_match_image=True,bindings=24,supplemental_bodies=11)):
        raise ValueError('Placement inventory source identity changed')
    for ref in p['references']:
        _source((ref['path'],ref['sha256']))
    for name,binding in p['bindings'].items():
        ref=binding['source']; original=_source((ref['path'],ref['sha256']))
        if original['bindings'][name]['callback_rva']!=binding['callback_rva']:
            raise ValueError('Placement inventory binding differs from its selected source')
    facts=p['facts']
    if (facts['district_type_absent']['value']!=-1 or facts['wonder_type_absent']['value']!=-1
            or facts['wonder_type_absent']['value_kind']!='GameInfo.Buildings.Index'
            or facts['district_complete']['nonnegative_plot_argument_checks_type'] is not False
            or facts['building_complete']['argument']!='native type index, not hash'):
        raise ValueError('Placement inventory sentinel/completion contract changed')
    # Type conversion returns a supplied in-range index unchanged. District
    # lookup resolves by actual plot coordinates; the collector cross-checks
    # the type separately because IsComplete(type, plotID) does not do so.
    for key,required in {
        '0x671b0':('call 0x1800109f0','call 0x180025b20','cmp r15d, dword ptr [rax + 4]',
                   'cmp r14d, dword ptr [rax + 8]'),
        '0x16f220':('call 0x1806a27f0','mov eax, ebx','call 0x18016e0f0'),
        '0x16f4f0':('call 0x1806a2ad0','mov eax, ebx','call 0x1800de050'),
    }.items():
        instructions={row['text'] for row in p['functions'][key]['instructions']}
        if not set(required)<=instructions:
            raise ValueError('Placement inventory descendant source changed: '+key)
    return p


def source_dependencies(core_sha256=XP1_CORE_SHA256, *, execution_image=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_inventory_source import source_dependencies as selected
        return selected(core_sha256,execution_image=execution_image)
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 inventory ABI')
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown placement inventory engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    result=dict(placement.source_dependencies());p=verify_source()
    for ref in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['image'],p['extractor'],*p['references']):
        path=str(resolve_path(resource_root()/ref['path']).resolve())
        if path in result and result[path]!=ref['sha256']:
            raise ValueError('Conflicting placement inventory source dependency')
        result[path]=ref['sha256']
    return result


def verify_live(base,read,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_inventory_source import verify_live as selected
        return selected(base,read)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown placement inventory engine')
    from .xp1_status_profiles import _instruction_spans
    if type(base) is not int or base<=0 or not callable(read):
        raise ValueError('Placement inventory needs its selected live module and reader')
    spans=_instruction_spans(verify_source())
    for rva,raw in spans:
        if read(base+rva,len(raw))!=raw:
            raise ValueError('Placement inventory descendant changed at '+hex(rva))
    return len(spans)


@dataclass(frozen=True)
class VerifiedInventorySource:
    owner:object
    core:object
    base:int
    source_sha256:str
    placement_receipt:object
    instruction_read_spans:int


def bind_owner(owner,core,read):
    """Once per exact native lifetime; no action/turn-active prerequisite."""
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_placement_inventory_source import bind_owner as selected
        return selected(owner,core,read)
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256!=XP1_CORE_SHA256
            or type(core._handle) is not int or core._handle<=0 or read!=owner.runtime.read):
        raise ValueError('Placement inventory source owner mismatch')
    original=placement.bind_owner(owner,core,read)
    old=getattr(owner,'_placement_inventory_source_receipt',None)
    if old is not None:
        if (type(old) is not VerifiedInventorySource or old.owner is not owner or old.core is not core
                or old.base!=core._handle or old.source_sha256!=SOURCE[1]
                or old.placement_receipt is not original):
            raise ValueError('Placement inventory receipt belongs to another native lifetime')
        return old
    p=verify_source()
    # The original binder has verified its full closure. Only the new source
    # and reproducible capture supplement need an additional file digest.
    from .paths import resource_root
    from .resource_resolution import resolve_path
    for ref in (dict(path=SOURCE[0],sha256=SOURCE[1]),p['extractor']):
        path=resolve_path(resource_root()/ref['path'])
        with Path(path).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=ref['sha256']:
                raise ValueError('Placement inventory dependency changed: '+str(path))
    result=VerifiedInventorySource(owner,core,core._handle,SOURCE[1],original,verify_live(core._handle,read))
    owner._placement_inventory_source_receipt=result
    return result

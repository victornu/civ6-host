"""Exact XP2 UI influence bindings for the shared envoy algorithms.

Query registrations and request entrypoints are separate proofs. The original
engine computes influence. These pins admit a bounded native trial, not full
effect/cache qualification; unknown services still refuse and an action needs
strict native effect readback before it can be reported as completed.
"""
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256, _source as pinned_source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/bbg751-envoys/source/source-query-v1.json',
          '9b06e3693cc5b90f0b12a0a7509e13d0804b3174ec14fef59efebd8964446593')
UI_SOURCE = ('work/bbg751-envoys/ui-source-v1.json',
             'ef7be28b176194c8895543347dbbeea192becdc8d6bd635f8862451793fae2e5')
APPLICATION = ('work/bbg751-envoys/source/source-application-v1.json',
               '43f388eaeb49e854d0d4b186b4f3f55a8844b6306f6a8431d946d8d01edf6062')
RUNTIME = ('work/bbg751-envoys/runtime-source-v2.json',
           'a3f8d10892a014466a2e25270e68f39ed17630ed34301a3c8a99914d83403b35')
CALLBACKS = {
    'GetDiplomacy': (0x6a8c90, 0x6a98d0),
    'GetInfluence': (0x6a8c90, 0x6a9cf0),
    'HasMet': (0x6ae510, 0x6b01b0),
    'GetAliveMinors': (0x6b1d20, 0x6b27b0),
    'CanGiveInfluence': (0x6b12f0, 0x6b16a0),
    'CanGiveTokensToPlayer': (0x6b12f0, 0x6b16f0),
    'CanReceiveInfluence': (0x6b12f0, 0x6b17b0),
    'GetTokensReceived': (0x6b12f0, 0x6b1b30),
    'GetTokensToGive': (0x6b12f0, 0x6b1ba0),
    'IsGivingTokensConsidered': (0x6b12f0, 0x6b1bf0),
    'SetGivingTokensConsidered': (0x6b12f0, 0x6b1c40),
}


def source():
    # Keep the detailed disassemblies as pinned source evidence, not large
    # parsed/frozen Python graphs inside each 512-MiB native process.
    proof = pinned_source(RUNTIME)
    if (proof['schema'] != 'civ6-host.xp2-envoys-runtime-source.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or int(proof['image']['image_base'], 16) != 0x180000000
            or set(proof['bindings']) != set(CALLBACKS)
            or len(proof['blocks']) != 21 or proof['native_execution'] is not False):
        raise ValueError('XP2 influence query source identity differs')
    for name, reference in (('query',SOURCE),('application',APPLICATION),('ui',UI_SOURCE)):
        if (proof['parents'][name]['path'],proof['parents'][name]['sha256']) != reference:
            raise ValueError('XP2 influence detailed source parent differs')
    for name, (registrar, callback) in CALLBACKS.items():
        row = proof['bindings'][name]
        if (row['registrar_rva'] != registrar or row['callback_rva'] != callback
                or row['helper_rva'] != 0xdab0
                or not any(b['group']=='query_callback' and b['name']==name
                           and b['rva']==callback for b in proof['blocks'])):
            raise ValueError('XP2 influence method registration differs: '+name)
    return proof


def application_source():
    proof = source()['application']
    if (set(proof['root_rvas']) != {'0x30c100','0x30cbe0','0x30d3ed','0x2ead90'}
            or proof['target_effect_requires_native_readback'] is not True):
        raise ValueError('XP2 envoy request/application entrypoint source differs')
    rows = proof['critical_instructions']
    for address, instruction in {
            '0x30d446':'cmp eax, 0x99ec0bce',
            '0x30d4b3':'mov edx, 0x483191c',
            '0x30d50a':'call 0x1802ead90',
            '0x2eadaf':'call 0x1802eaaa0',
            '0x2eadc6':'call 0x1802edaf0'}.items():
        if rows.get(address) != instruction:
            raise ValueError('XP2 native envoy entrypoint instruction differs')
    return proof


def source_dependencies(*, execution_image=None):
    from hashlib import sha256
    from civ6_host.contracts import envoys
    from . import xp2_envoys
    from .native import native_envoy_actions as native
    query = source()
    ui = pinned_source(UI_SOURCE)
    application_source()
    legacy = native.verify_source()
    result = {str(resolve_path(resource_root()/p).resolve()): h
              for p,h in (SOURCE, UI_SOURCE, APPLICATION, RUNTIME)}
    for row in (*query['parents'].values(),query['generator']):
        path=resolve_path(resource_root()/row['path'])
        if sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('XP2 envoy projection source dependency changed')
        result[str(path.resolve())]=row['sha256']
    for row in (query['image'], *ui['files'].values()):
        path = resolve_path(Path(row['path']))
        # The Core row records the capture/reference image. Under an explicit
        # execution profile, preserve it as provenance and let the shared
        # materializer project only this exact image identity to the selected
        # runtime hash. All UI rows remain live-hash checked as before.
        is_core_provenance = row is query['image'] and execution_image is not None
        if not is_core_provenance:
            if sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('XP2 envoy pinned UI/image dependency changed')
            result[str(path.resolve())] = row['sha256']
    if (ui['schema'] != 'civ6-host.xp2-envoys-ui-source.v1'
            or ui['files']['bbg_modinfo']['citystates_replacements']
            or ui['files']['bbg_modinfo']['citystates_ui_files']):
        raise ValueError('XP2/BBG envoy UI selection differs')
    for row in legacy['parents'].values():
        result[str(resolve_path(native.ROOT/row['path']).resolve())] = row['sha256']
    result[str(resolve_path(native.ROOT/'evidence/native-envoy-actions'/
        (native.PROOF_SHA256+'.json')).resolve())] = native.PROOF_SHA256
    for module in (envoys, native, xp2_envoys):
        path = Path(module.__file__).resolve()
        result[str(path)] = sha256(path.read_bytes()).hexdigest()
    path = Path(__file__).resolve()
    result[str(path)] = sha256(path.read_bytes()).hexdigest()
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(
        result, execution_image=execution_image,
        provenance_images=(query['image'],),
    )


def bind_owner(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    b, p = saved.backend, saved.prefix
    core, base = b.core, b.core._handle
    if b.load_abi.core_sha256 != XP2_CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Envoys require the selected live XP2 engine')
    lifetime = (core, p)
    if getattr(saved, '_xp2_envoy_lifetime', None) == lifetime:
        return
    proof = source()
    application_source()
    read = b.runtime.read
    for body in proof['blocks']:
        raw = bytes.fromhex(body['raw_hex'])
        if len(raw) != body['length'] or read(base+body['rva'], len(raw)) != raw:
            raise ValueError('Live XP2 influence callback or registrar body differs')
    for name, row in proof['bindings'].items():
        raw = name.encode('ascii')+b'\0'
        if read(base+row['name_rva'],len(raw)) != raw:
            raise ValueError('Live XP2 influence method name differs')
    saved._xp2_envoy_lifetime = lifetime

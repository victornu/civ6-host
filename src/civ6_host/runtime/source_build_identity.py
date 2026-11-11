"""One source-build identity boundary shared by native host components.

Association proves exact build/source provenance, never native compatibility.
Only reviewed immutable build records in the registry can be admitted.
"""
from pathlib import Path
import hashlib
import json
from .configuration_profiles import _source
from .resource_resolution import resolve_path

XP2_HOST_COMPONENT_SHA='268a43bc7e06b383adfa13d2c084d2d7966ca8ffc9782044a0103ca36967f4f7'

SOURCE_BUILDS = {
    'd5f15e2c314831234b5056dd041d253ab6e542bfa6070ee7327f8e17b3c3f3c8': {
        'reference': ('work/native-host-xp2-current-strings-unsigned-log-build01/build.json',
                      '60956421113f7e6c9781e1cb84af55e8f5610047bed01d70576ad32e04e55ecd'),
        'manifest_sha256': '547f4338e4be0525ed03633086e6bb40cf7e3bcd94191aa0dbce8c15927aaf52',
        'profile': 'xp2-current-strings-unsigned-log-source-v1',
        'local_components_sha256': '66dfbd20ad375a1d0e6ffdc7721432d97b977d911bc5a40571978d30bc16acc1',
    },
    '106018516854f1e28d34814f24e08d3834eee0272f143b3daba0d4a5c571bc5e': {'reference': ('work/native-host-xp2-current-strings-build01/build.json', '391f78fcb31aff04b3c552122fb1143e3380fdca94ad6bbdb639ffbf63d50fa3'), 'manifest_sha256': '7e67158f208f19cd9d29c36ce940a8c6082096ae750bf925884a63ce51f7b303', 'profile': 'xp2-current-strings-source-v1', 'local_components_sha256': '3395536556c736fc598c0f012097a47cb8406ddc816487b2c412bc0b99e42127'},
    'c8fa420876ffbdaafaf4df82dfe4ad72187ceb146995afb65f98f5242267e52f': {'reference': ('work/native-host-xp2-current-havok-build01/build.json', '4df115a7abcc3a6906730b7febed4735ca381cfb685d648d04ad9c451808d175'), 'manifest_sha256': '502731d5db3592d62391b7d2b5eeadc1706ac45eee8ffe1e84b8dd38e618fe4d', 'profile': 'xp2-bbg-current-havok-201979', 'local_components_sha256': '5dd9276167f97a115f68db71681ccaebd4f6e26bca36af682af6a825bb564292'},
    '61953897b696b45a7998126392f5759c7b34ed045551ff7d597ffa3eaa2fafda': {
        'reference': ('work/native-host-xp2-bbg-ui-build03/build.json',
                      '0c01abf9c1afc8db20a25cfdc5c1ce54151fd20bb7ac3512f94417679132bd11'),
        'manifest_sha256': '4ede5cab72b03ba0261f4e0275df48bf99fc3501af6053666b651cb3ff6374d3',
        'profile': 'xp2-bbg-private-property-table',
    },
    '01e6cd9c49af96cc3f1a58aac5f111722cdf02e037916d7de811b005a461ea6f': {
        'reference': ('work/native-host-xp2-bbg-ui-build02/build.json',
                      '2e28a78751556086e7e3de97d76ad2b5b93634adab18bd52db1dd6ad325139ce'),
        'manifest_sha256': '07300f3d5bc052a8eb593751bc11cc3c2261b422e2f1a8f08786a466d4eabc8e',
        'profile': 'xp2-bbg-private-property-table',
    },
    '383bbbdbe57f3ccb453c2584faf98476659c180035a597ae70c8ce5ea78c8da5': {
        'reference': ('work/native-host-xp2-bbg-ui-build01/build.json',
                      'aa7ea06faa37b301bdad69b7909f641f3354035d567186728aceb4a13c70358b'),
        'manifest_sha256': '6b17c31d97eaab204b4a29a8af997e7cf7e61a66ce14d1454738987de1ac8bc5',
        'profile': 'xp2-bbg-private-property-table',
    },
    '99d0847958bf641266b3f352983122b27defa005f729cc644db773cdc5ca88ca': {
        'reference': ('work/native-host-xp2-bbg-build01/build.json',
                      '25245e947039f4a7573cc3c9174341402cf401a467c284a8f65b2b445dbd3bca'),
        'manifest_sha256': 'e67a75ce5c7512ebbc725840cb6925484183acd598d05dee9d561c3b75396e02',
        'profile': 'xp2-bbg-private-property-table',
    },
    'a3d977a4aa09d3f4f88a393f59e32f5a34d12d79db48606c39c4b9e09994f799': {
        'reference': ('work/native-host-xp2-ui-build01/build.json',
                      '8c3a8ebdf2212362f633f987b281a767f7b8db79f999d151ff355bf59f95fac2'),
        'manifest_sha256':'6161b97528317f98dc915bbaea8dcce7f72c186466c25240c2fd640bdc41f66b',
        'profile':'xp2-official-ui-bindings-with-script-services',
        'local_components_sha256':'9f19b72385bd66dac550920fbe8aa40ad8b78553209cbf651fe940371c8c789b',
    },
    'c82e631d710b36daa1a6213543eb62f98e2849fbbe34232365c7556e66cb849e': {
        'reference': ('work/native-host-xp2-jobs-build01/build.json',
                      'b4a830499a32d35bf1e7cff0e5a47fb2914cc164e6f9a83679f40668bea16582'),
        'manifest_sha256':'9dd2dd36283d6dafc7be96404bbe6421f398e6e66937213d6df825121ca0995c',
        'profile':'xp2-explicit-job-core-with-script-services',
    },
    '5ecf107b748ffa57ca63712c3e1cf05e8e383e3c7ce14668003cdb68e6a47e7d': {'reference': ('work/native-host-xp2-script-contexts-build01/build.json', 'b75dabd302c0047a124ab48b9d93b83f8ca7af55b29254597e87cc957f4ec4b1'), 'manifest_sha256': '7f20ba44d9d2aeac94ebd7264847032b2bb6d52b63aeeb1f97aa2624b722f394', 'profile': 'official-xp2-scoped-script-contexts'},
    '067460feab09229fdc2ccdf08febfe189ed907d3a1f6d81e03350932b01cde24': {'reference': ('work/native-host-xp2-mutable-map-build03/build.json', '3cd3d12595e2a56dba151b9f68ea601095029c662da122a75d51965cc392f711'), 'manifest_sha256': '93dc2627e05a19ef213e87b692c865edf03eac8a3b92ab2f17b33b48c71035ba', 'profile': 'official-xp2-mutable-gameevents-map'},
    'f1ed3126b90c2a675ef6c54b16d376cd7863a028c51c033376f0a09d4638a0df': {'reference': ('work/native-host-xp2-mutable-map-build02/build.json', '020ef68f6c586fb16a9b924f15777b1043ee1b86e18503e62c1994fa3b942807'), 'manifest_sha256': 'cb512bb389c28018a035e64f7f4d00806cd8a4c024d17168ca13ef443549ad8e', 'profile': 'official-xp2-mutable-gameevents-map'},
    'a17a82af1a9e5a429af4a1ef82e88b80d3213699118ec1cece14e88516d761d4': {'reference': ('work/native-host-xp2-script-api-build01/build.json', '6e4ed70f48cb01d8655dda6d49b152bbd24f95376616254d4347e4bf892ee8ad'), 'manifest_sha256': 'e2f9c00df9ef1169e309221839dbbeccc027981d43733f0e5289f108eb27ec3a', 'profile': 'official-game-api-profiles-xp2'},
    '949949ddca0ec61a55e3368bf062f46fcdb4b2f7dc52f25a49acc4758664224f': {
        'reference': ('work/native-host-xp1-ui-build01/build.json',
                      '842ee9a916b247e23c68e55fed10e6edb00413ce4762b9fe706baa018c074010'),
        'manifest_sha256':'6da2aba65afe87cb8c304eb2a0b59d83a511d330a5e51a6ca07686360dd9449a',
        'profile':'xp1-official-ui-bindings',
        'local_components_sha256':'ff178f7f50fc483b4da4c7f1d0541d746503a7f89cfb406647e9318094e71d63',
    },
    'ef3d85f1baa913888a1c48802e0862592cecf1e1dffff0e6964ffba1f146411f': {
        'reference': ('work/native-host-xp1-postload-build01/build.json',
                      '36edef5ffb199f080fa5b01dea0969377bc386844b166013d37dcd1fa5d35269'),
        'manifest_sha256':'7dffc41201d312d8b4c8c8dd4e67591c118a1d624ea1000cb76f967daacc4f20',
        'profile':'xp1-postload-category-null',
    },
    '09b7a2e1f049120d8483e01c81859d2796d0cd7882897587f66980c27a4ec7a6': {
        'reference': ('work/native-host-xp1-jobs-build01/build.json',
                      'a3f0dea1be0bd59f66d8e02615997da766c189e2f6ff561215bd7dee4feb2b8b'),
        'manifest_sha256':'75d2965e3d9602c7f9a576157de45bd04b54e1467d7c5d0dd73b72ace63c9052',
        'profile':'xp1-explicit-job-core',
    },
}


def verify_source_build(executable, *, required_components):
    path=Path(executable).resolve(strict=True)
    raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    selected=SOURCE_BUILDS.get(digest)
    if selected is None:
        raise ValueError('Native source build has not been registered')
    reference = selected['reference']
    receipt = resolve_path(Path(executable).parent / 'build.json')
    local = selected.get('local_components_sha256')
    if local and receipt.is_file():
        if receipt.resolve(strict=True) != receipt:
            raise ValueError('Native build record is redirected')
        with receipt.open('rb') as stream:
            receipt_bytes = stream.read(8 * 1024 * 1024 + 1)
        if len(receipt_bytes) > 8 * 1024 * 1024:
            raise ValueError('Native build record is oversized')
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        if receipt_sha != reference[1]:
            reference = (str(receipt), receipt_sha)
            build = json.loads(receipt_bytes)
        else:
            local = None
            build = _source(reference)
    else:
        local = None
        build = _source(reference)
    artifact=build.get('executable',{})
    if (build.get('schema')!='civ6-host.native-build.v1'
            or build.get('status')!='source_build_unqualified'
            or build.get('profile')!=selected['profile']
            or build.get('source_manifest_sha256')!=selected['manifest_sha256']
            or build.get('compiler_exit_code')!=0 or build.get('compiler_reaped') is not True
            or artifact.get('sha256')!=digest or artifact.get('bytes')!=len(raw)
            or resolve_path(Path(artifact.get('path',''))).resolve(strict=True)!=path):
        raise ValueError('Native build record differs from its exact artifact')
    sources={}
    dependencies = {reference[0]: reference[1]}
    for row in build['sources']:
        key=row['build_path']
        component = resolve_path(Path(row['path']))
        if local and (component != path.parent / 'inputs' / key
                      or not component.is_relative_to(path.parent / 'inputs')
                      or '..' in component.parts or component.resolve(strict=True) != component):
            raise ValueError('Local native source must be its canonical staged input')
        if key in sources or hashlib.sha256(component.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Native build input differs or is duplicated')
        sources[key]=row['sha256']
        dependencies[row['path']] = row['sha256']
    if local:
        canonical = json.dumps(sources, sort_keys=True, separators=(',', ':')).encode('utf-8')
        if hashlib.sha256(canonical).hexdigest() != local:
            raise ValueError('Local native source set differs from the reviewed profile')
    if not required_components or any(sources.get(k)!=v for k,v in required_components.items()):
        raise ValueError('Native source component is not admitted by this build')
    return dict(host_sha256=digest,build_reference=list(reference),build_dependencies=dependencies,
                source_manifest_sha256=selected['manifest_sha256'],
                profile=selected['profile'],sources=sources,
                executable_path=str(path),native_compatibility_claimed=False)


# This reviewed derived host changes typed Havok export guards only. These
# are distinct actual source hashes, not aliases for historical components.
CURRENT_HAVOK_HOST_REFERENCE = ('work/native-host-xp2-current-havok-build01/civ6rl-native-python.exe', 'c8fa420876ffbdaafaf4df82dfe4ad72187ceb146995afb65f98f5242267e52f')
CURRENT_HAVOK_BUILD_PROFILE = 'xp2-bbg-current-havok-201979'
_CURRENT_HAVOK_COMPONENT_TRANSITION = {'script_game_event_aggregators.inc': ('c9c385462d83ba35b5f23898d310ba3f437313aedeb56dd125f1d8c6b8e375e7', '62ada8288b9bc96689364730e10330b094e13dfca915839caa49e8e6da5b1bb9'), 'gamecore_python_host.c': ('268a43bc7e06b383adfa13d2c084d2d7966ca8ffc9782044a0103ca36967f4f7', '10ea12fc6159a3556ef46af734b113dde8022dfd725191e417fc50f948978c73'), 'script_game_event_result_map.inc': ('b90214047bf68869cfd13c214d7791c2fc6df5c2c61a7fef1106468bc1a65edd', '33f26c314f65b43e51c1172d2489582e1f0cc15863625481f356da396a619e3e'), 'script_aux_b8.inc': ('4dbb70603b94ba654f074e37968fa92e1c42e2991d97e5dd200b200cb10e1771', '5e3958f0725874f8de7585ea6711b0b5723d0769567d880cea02c8724553eea5')}

# An explicit derived composition adds copied string arguments; retained hosts
# keep their own source transition and are never relabelled as this build.
CURRENT_STRINGS_HOST_REFERENCE = ('work/native-host-xp2-current-strings-build01/civ6rl-native-python.exe', '106018516854f1e28d34814f24e08d3834eee0272f143b3daba0d4a5c571bc5e')
CURRENT_STRINGS_BUILD_PROFILE = 'xp2-current-strings-source-v1'
CURRENT_UNSIGNED_LOG_HOST_REFERENCE = (
    'work/native-host-xp2-current-strings-unsigned-log-build01/civ6rl-native-python.exe',
    'd5f15e2c314831234b5056dd041d253ab6e542bfa6070ee7327f8e17b3c3f3c8',
)
CURRENT_STRINGS_HOST_REFERENCES = (CURRENT_STRINGS_HOST_REFERENCE, CURRENT_UNSIGNED_LOG_HOST_REFERENCE)
CURRENT_STRINGS_BUILD_PROFILES = tuple(SOURCE_BUILDS[sha]['profile'] for _, sha in CURRENT_STRINGS_HOST_REFERENCES)
_CURRENT_STRINGS_COMPONENT_TRANSITION = {
    **_CURRENT_HAVOK_COMPONENT_TRANSITION,
    'script_game_event_dispatch_legacy.inc': ('6c666a6f5e8d0702c47f3ed3a5f6ca66037eccb8963ce394b61777e9bf49d73b', '34b1949f2383b776cc59ebfedabeadd5ddb2a3510348505e1e16bb0395093fd0'),
    'script_game_event_result_map.inc': ('b90214047bf68869cfd13c214d7791c2fc6df5c2c61a7fef1106468bc1a65edd', 'ab7fa2c648238f8b3f6c1eb2ea53897ecfe718df045625788889d2bc29610c1e'),
}


def _xp2_source_component_transitions(host_sha256):
    if host_sha256 == CURRENT_UNSIGNED_LOG_HOST_REFERENCE[1]:
        return {
            **_CURRENT_STRINGS_COMPONENT_TRANSITION,
            'gamecore_python_host.c': (
                XP2_HOST_COMPONENT_SHA, '21c2706ea8c2119e3bc29a73d8cbe4ef8d1a64fc4d2c078f75eedbf78451a7e4'),
        }
    if host_sha256 == CURRENT_STRINGS_HOST_REFERENCE[1]:
        return _CURRENT_STRINGS_COMPONENT_TRANSITION
    if host_sha256 == CURRENT_HAVOK_HOST_REFERENCE[1]:
        return _CURRENT_HAVOK_COMPONENT_TRANSITION
    return {}


def xp2_component_requirements(executable, requirements):
    """Select actual component pins for this explicitly registered host build."""
    expected = dict(requirements)
    path = Path(executable).resolve(strict=True)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    for name, (historical, current) in _xp2_source_component_transitions(digest).items():
        if name in expected:
            if expected[name] not in (historical, current):
                raise ValueError('Selected XP2 host has no transition for component '+name)
            expected[name] = current
    return expected


def xp2_source_component(build, name, reference_sha256):
    """Return the actual pin of one component in its reviewed source build."""
    pair = _xp2_source_component_transitions(build.get('host_sha256')).get(name)
    if pair is not None:
        if reference_sha256 not in pair:
            raise ValueError('No reviewed source transition for '+name)
        return pair[1]
    return reference_sha256

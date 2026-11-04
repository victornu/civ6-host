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

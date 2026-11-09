"""Private BBG subscription to the official LoadGameViewStateDone sequence event.

Raw saved Load precedes that event. The headless lifecycle delivers the
retained callback in its HKS child once the loaded GameCore view is ready.
"""
from .configuration_profiles import _source

_SOURCE = ('work/native-xp2-bbg751/run-2e954f8a7a76/load_game_view_event_static.json',
           '13b455ba1d53ccdbc93b9b5685114b7aa99d668ab0c83bf30638470b4a9bff58')
_INSTALL = b"""
assert(Events == nil, 'Foreign Events namespace')
local listener
local attempted = false
local ready = {}
function ready.Add(callback)
    assert(type(callback) == 'function' and listener == nil, 'Unexpected load-view subscription')
    listener = callback
end
function ready.Remove(callback)
    assert(listener == callback and listener ~= nil, 'Unexpected load-view unsubscription')
    listener = nil
end
function ready.Count()
    return listener and 1 or 0
end
Events = {LoadGameViewStateDone = ready}
function Civ6HostDispatchLoadGameViewStateDone()
    assert(listener ~= nil and not attempted, 'Unexpected load-view delivery')
    attempted = true
    listener()
    return 'listener-returned'
end
"""


def install(runtime, child):
    evidence = _source(_SOURCE)
    refs = evidence['exe']['xrefs']
    if (evidence['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or len(refs) != 1 or refs[0]['rva'] != '0x46f5f4'
            or refs[0]['target'] != '0xfd87e8'):
        raise ValueError('BBG LoadGameViewStateDone source differs')
    runtime.execute(child, _INSTALL, b'@bbg751_load_view_event_subscription')



def deliver(publication):
    """Run the existing BBG listener at the completed headless view boundary."""
    from .xp1_cache_publication import COMPLETED_STAGE, SavedCachePublication
    from .xp2_bbg_inputs import is_reference

    if type(publication) is not SavedCachePublication:
        raise TypeError('Load-view delivery requires the real publication owner')
    backend = publication.owner
    if (not is_reference(backend.captured_bundle.reference)
            or backend._xp1_publication_attempt is not publication
            or backend.stage != COMPLETED_STAGE or backend.busy or backend.poisoned
            or publication.completed is not True or publication.result['post190_called'] is not True):
        raise ValueError('Load-view delivery requires the completed BBG publication')
    contexts = backend.prefix.contexts
    scripts = [pointer for pointer, name in contexts.names.items() if name == b'bbg_script']
    if len(scripts) != 1 or scripts[0] not in contexts.loaded:
        raise ValueError('BBG load-view listener has no live, loaded script context')
    child = contexts.lifetime._contexts[scripts[0]]
    runtime = backend.prefix.runtime
    result = runtime.evaluate_text(child,
        b'return Civ6HostDispatchLoadGameViewStateDone()', b'@bbg751_view_ready_dispatch', capacity=64)
    if result != b'listener-returned':
        raise RuntimeError('BBG load-view listener did not return')
    backend.emit('xp2_bbg_load_view_ready_delivered', event='LoadGameViewStateDone',
                 listeners=1, cache_published=True, game_update_called=False)

"""Refuse accidental imports of the historical lab or a learner in this runtime."""
import importlib.abc
from pathlib import Path
import sys
import types

_DENIED=frozenset(('civ6rl','tools','torch'))
_AUDIT_INSTALLED=False


class _HostOnlyImports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in _DENIED:
            raise ImportError('Historical lab/learner code is forbidden in the installed host: '+fullname)


def enable():
    global _AUDIT_INSTALLED
    from .resource_resolution import enable_read_boundary
    enable_read_boundary()
    found=sorted(name for name in sys.modules if name.split('.')[0] in _DENIED)
    if found:raise RuntimeError('Host process already imported forbidden code: '+','.join(found[:4]))
    if not any(isinstance(x,_HostOnlyImports) for x in sys.meta_path):sys.meta_path.insert(0,_HostOnlyImports())
    if not _AUDIT_INSTALLED:
        from .paths import resource_root
        private=resource_root()
        installed=Path(__file__).resolve().parents[1]
        def refuse_private_python(event,args):
            if event!='exec' or not args or not isinstance(args[0],types.CodeType):return
            filename=Path(args[0].co_filename)
            if not filename.is_absolute():return
            path=filename.resolve()
            if path.is_relative_to(private) and not path.is_relative_to(installed):
                raise RuntimeError('Private resources are data, not executable Python: '+str(path))
        sys.addaudithook(refuse_private_python)
        _AUDIT_INSTALLED=True

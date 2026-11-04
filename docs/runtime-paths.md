# Runtime resource root

The native backend uses private game resources from a separately configured directory. Before importing the backend, the launcher must set `CIV6_HOST_RESOURCE_ROOT` to an absolute path that already exists and is a directory. The setting is captured when the path module is imported; a missing, invalid, or changed value requires a new process with corrected configuration.

```python
from civ6_host.runtime.paths import resource_root

resources = resource_root()
```

The first successful call resolves symlinks and freezes the canonical path for that process. A later call fails if the setting changes or the directory becomes invalid. Start a separate process to use a different resource root.

There is no fallback to the current directory, installed package, or `civ6-rl-lab`. The module is portable to import and does not load GameCore DLLs, PyTorch, or private game data.

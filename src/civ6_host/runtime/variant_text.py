"""Read-only UTF-16 projection for the source-qualified native Lua converter.

Uses the same fixed byte capacity and surrogate rules as the C A0 service.
The caller owns checked reads, stability tracking and the aggregate budget.
"""
from __future__ import annotations

MAX_UTF16_UNITS = 1024 * 1024


def lua_utf16_snapshot(pointer, copy, remember):
    if not pointer:
        return None, 0
    raw = bytearray()
    for index in range(MAX_UTF16_UNITS + 1):
        unit = copy(pointer + index * 2, 2, track=False)
        if unit == b'\0\0':
            remember(pointer, bytes(raw) + unit)
            break
        raw.extend(unit)
    else:
        raise ValueError('UTF-16 source exceeds bounded scan')
    output = bytearray()
    for character in raw.decode('utf-16-le', 'surrogatepass'):
        encoded = character.encode('utf-8', 'surrogatepass')
        if len(output) + len(encoded) > 1023:
            break
        output.extend(encoded)
    return bytes(output), len(raw) // 2

/* C-only AUX+A0 table variant adapter. Lua errors stay on native frames. */
#include <stdint.h>

typedef void (__cdecl *PushScalar)(void *, void *, const void *);
typedef void (__cdecl *PushMap)(void *, void *, const void *, unsigned char);

typedef struct {
    uint16_t tag;
    uint16_t padding;
    uint32_t reserved;
    const void *payload;
    uint32_t size;
    uint32_t flags;
} CoreVariant;

static void *expected_owner;
static PushScalar push_scalar;
static PushMap push_map;

__declspec(dllexport) int __cdecl Civ6HostBindTradeTableVariant(
    void *owner, PushScalar scalar, PushMap map
) {
    if (!owner || !scalar || !map || expected_owner) return 0;
    push_scalar = scalar;
    push_map = map;
    expected_owner = owner;
    return 1;
}

__declspec(dllexport) int __cdecl Civ6HostUnbindTradeTableVariant(void *owner) {
    if (!owner || expected_owner != owner) return 0;
    expected_owner = 0;
    push_scalar = 0;
    push_map = 0;
    return 1;
}

void __ud2(void);
#pragma intrinsic(__ud2)

__declspec(dllexport) void __cdecl Civ6HostPushTradeTableVariant(
    void *owner, void *state, const CoreVariant *variant
) {
    if (!owner || owner != expected_owner) {
        __ud2();
        return;
    }
    if (variant && variant->tag == 10 && variant->payload
        && variant->size == 0 && variant->flags == 0x05000000u) {
        /* The official tag-10 branch passes its map pointer with names=true. */
        push_map(owner, state, variant->payload, 1);
        return;
    }
    push_scalar(owner, state, variant);
}

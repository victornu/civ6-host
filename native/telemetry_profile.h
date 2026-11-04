/* Explicit headless telemetry profile for the pinned EXE/Core ABI.
 * EXE9B0600 exports a borrowed static object. Core73AE60/73AD30 own
 * actual record serialization into this storage. This profile starts with
 * slot0, empty rings, no EXE presentation subscribers, and retains records.
 * It does not claim the graphical EXE's entire telemetry initialization.
 * Evidence: native-telemetry-event-system.json (source capture).
 */
#define LAB_TELEMETRY_BYTES 0x806280u
#define LAB_TELEMETRY_SLOT 0x80u
#define LAB_TELEMETRY_SEGMENT 0x400080u
#define LAB_TELEMETRY_CAPACITY 0x400000u
#define LAB_TELEMETRY_LOCK 0x806200u
__declspec(align(128)) static unsigned char lab_telemetry[LAB_TELEMETRY_BYTES];
static DWORD lab_telemetry_thread=0;

static __declspec(noreturn) void telemetry_refused(const char* reason) {
    fprintf(stdout,"{\"stage\":\"native_telemetry_profile_refused\",\"reason\":\"%s\"}\n",reason);
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(),78);
    abort();
}

static void telemetry_check(void) {
    DWORD current=GetCurrentThreadId();
    if (!lab_telemetry_thread) {
        lab_telemetry_thread=current;
        fprintf(stdout,"{\"stage\":\"native_telemetry_storage_initialized\","
            "\"bytes\":%u,\"alignment\":128,\"slot_index\":0,"
            "\"profile\":\"explicit empty headless telemetry storage\","
            "\"original_exe_initialization_reproduced\":false,\"eligible_for_training\":false}\n",
            LAB_TELEMETRY_BYTES);
        fflush(stdout);
    }
    if (current!=lab_telemetry_thread)
        telemetry_refused("unverified concurrent telemetry writer");
    if (((uintptr_t)lab_telemetry & 127u) || *(uint32_t*)(lab_telemetry+4)!=0)
        telemetry_refused("unverified telemetry slot or alignment");
    if (*(uint32_t*)(lab_telemetry+LAB_TELEMETRY_SLOT)>LAB_TELEMETRY_CAPACITY ||
        *(uint32_t*)(lab_telemetry+LAB_TELEMETRY_SLOT+LAB_TELEMETRY_SEGMENT)>LAB_TELEMETRY_CAPACITY)
        telemetry_refused("telemetry cursor exceeds native capacity");
}

__declspec(dllexport) void* __cdecl EXP_GetTelemetryEventSystem(void) {
    telemetry_check();
    return lab_telemetry;
}

/* Read-only diagnostic getter; no ring cursor reset or synthetic event. */
__declspec(dllexport) void* __cdecl LAB_GetTelemetryDiagnosticStorage(void) {
    telemetry_check();
    if (*(uint32_t*)(lab_telemetry+LAB_TELEMETRY_LOCK)!=0)
        telemetry_refused("telemetry snapshot requested while native lock is held");
    return lab_telemetry;
}

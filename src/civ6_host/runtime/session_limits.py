"""Standard supervised lifetime ceilings, independent of learner budgets.

XP1's instrumented saved Load can exceed 90 seconds before its first reply.
The instrumented persistence smoke test took about 400 seconds to load, play
one turn and save. Allow an explicit 1500-second bound for a multi-turn XP1
continuation that produces a unit without restarting between turns.
XP2's retained placement preparation costs about 130 seconds to start and found
a city, then about 59 seconds per instrumented turn. Its explicit multi-turn
qualification originally needed a 900-second ceiling. The retained current-image
T62 reset alone now measures 799.84 seconds including parent preparation;
its child startup is 719.47 seconds. Allow an explicitly selected 1800-second
bound for a useful lifecycle continuation and Save/Destroy in the same process.
Session defaults remain unchanged; this is not a throughput qualification.
The shared 512 MiB Job and output limits remain unchanged.
"""
XP1_MAX_SECONDS = 1500
XP2_MAX_SECONDS = 1800


def standard_lifetime_limit(input_profile):
    if input_profile=='xp2-lan':return XP2_MAX_SECONDS
    return XP1_MAX_SECONDS if input_profile=='xp1-lan' else 180

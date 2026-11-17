"""Standard supervised lifetime ceilings, independent of learner budgets.

The independent Rise and Fall levy checkpoint restored the turn-24 observation
and choices in 1084 seconds. Its next AI turn was still progressing when the
1800-second watchdog stopped the worker at poll 16. Allow an explicit
3600-second bound for a slow checkpoint replay, decision window and Save in
the same process. The caller must request the larger budget.
XP2's retained placement preparation costs about 130 seconds to start and found
a city, then about 59 seconds per instrumented turn. Its explicit multi-turn
qualification originally needed a 900-second ceiling. The retained current-image
T62 reset alone now measures 799.84 seconds including parent preparation;
its child startup is 719.47 seconds. Allow an explicitly selected 1800-second
bound for a useful lifecycle continuation and Save/Destroy in the same process.
Session defaults remain unchanged; this is not a throughput qualification.
The shared 512 MiB Job and output limits remain unchanged.
"""
XP1_MAX_SECONDS = 3600
XP2_MAX_SECONDS = 1800


def standard_lifetime_limit(input_profile):
    if input_profile=='xp2-lan':return XP2_MAX_SECONDS
    return XP1_MAX_SECONDS if input_profile=='xp1-lan' else 180

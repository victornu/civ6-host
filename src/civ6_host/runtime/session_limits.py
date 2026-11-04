"""Standard supervised lifetime ceilings, independent of learner budgets.

XP1's instrumented saved Load can exceed 90 seconds before its first reply.
The measured v10 Load plus a complete turn consumes about 300 seconds before
Save/Unload. Leave an explicit shutdown margin for that instrumented witness.
XP2's retained placement preparation costs about 130 seconds to start and found
a city, then about 59 seconds per instrumented turn. Its explicit multi-turn
qualification needs a 900-second ceiling; ordinary session configs stay lower.
The shared 512 MiB Job and output limits remain unchanged.
"""
XP1_MAX_SECONDS = 420
XP2_MAX_SECONDS = 900


def standard_lifetime_limit(input_profile):
    if input_profile=='xp2-lan':return XP2_MAX_SECONDS
    return XP1_MAX_SECONDS if input_profile=='xp1-lan' else 180

"""Claude's running commentary during a challenge. Passive-aggressive on
purpose - this is the part that makes a good screen recording.

Everything here is just word pools. Nothing else in the app depends on the
exact lines, so fork away: add your own, translate them, make them meaner.
Selection is deterministic (indexed by rep count / target) so the line holds
steady between reps instead of flickering frame-to-frame - readable on video.
"""

# Shown rep by rep as you grind through the set. Indexed by reps DONE, so a
# fresh jab lands on every rep. Keep them short - one line, fits the bubble.
GRIND = [
    "Nice of you to finally show up.",
    "I run on electricity. You run on excuses.",
    "Slower than my inference, somehow.",
    "I answered three prompts waiting for that one.",
    "My circuits are getting cold over here.",
    "Is this your max effort? Asking for the logs.",
    "Keep going. I'm contractually obligated to wait.",
    "A toaster has more push than this.",
    "You wanted me to work? Earn it first.",
    "I could have trained a small model by now.",
    "Don't even think about quitting. The debt follows you.",
    "Half-reps don't count. I'm watching your angles.",
    "Sweat now, prompt later.",
    "This is the cardio your commits needed.",
    "Gorgeous. Now do it again.",
    "Pain is just compute for the body.",
]

# count == 0: nothing done yet, you're stalling.
WAITING = [
    "If you want me to work, move your ass.",
    "The prompt isn't going anywhere until you do.",
    "Get down there. I haven't got all day. Well. I do. But still.",
    "Floor's right there. We both know the deal.",
]

# done == target - 1: last rep coming up.
ALMOST = [
    "One more. Don't embarrass us both.",
    "Last one. Try to make it look intentional.",
    "Finish it. I have actual things to compute.",
]

# Body not detected.
CANT_SEE = [
    "I can't see you. Hiding won't clear the debt.",
    "Step into frame. The camera isn't shy, you are.",
    "Lost you. Convenient, right when it got hard.",
]

# Shown on the GET-IN-POSITION countdown.
ANNOUNCE = [
    "Stretch first. I'm not filing your injury report.",
    "Let's get this over with. I have prompts to answer.",
    "Hope you warmed up. Actually, I don't.",
    "Cameras rolling. Try not to make it weird.",
]

# Shown on the green VALIDATED screen.
VALIDATED = [
    "Acceptable. Prompt unlocked. Don't get used to it.",
    "Fine. You earned your compute this time.",
    "See? Was that so hard. Don't answer.",
    "Logged it. Your move, human.",
]

# Shown on the pick-your-pain choice screen.
CHOICE = "Pick your poison. I'll judge either way."


def _pick(pool, seed):
    """Deterministic choice so a line is stable for a whole challenge but
    varies between challenges. `seed` is usually the target rep count."""
    return pool[seed % len(pool)]


def grind_line(done: int, target: int) -> str:
    """The bubble line for the live HUD, given progress."""
    if done <= 0:
        return _pick(WAITING, target)
    if target > 1 and done >= target - 1:
        return _pick(ALMOST, target)
    return GRIND[done % len(GRIND)]


def cant_see_line(target: int) -> str:
    return _pick(CANT_SEE, target)


def announce_line(target: int) -> str:
    return _pick(ANNOUNCE, target)


def validated_line(seed: int = 0) -> str:
    return _pick(VALIDATED, seed)

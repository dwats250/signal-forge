from __future__ import annotations

from signal_forge.execution.models import ReviewDeviationType, ReviewResult


def generate_review_result(
    *,
    followed_entry: bool,
    followed_stop: bool,
    followed_exit: bool,
    result_R: float,
) -> ReviewResult:
    followed = {
        "entry": followed_entry,
        "stop": followed_stop,
        "exit": followed_exit,
    }
    failures = [name for name, kept in followed.items() if not kept]
    if len(failures) > 1:
        deviation = ReviewDeviationType.MULTIPLE
    elif failures == ["entry"]:
        deviation = ReviewDeviationType.ENTRY
    elif failures == ["stop"]:
        deviation = ReviewDeviationType.STOP
    elif failures == ["exit"]:
        deviation = ReviewDeviationType.EXIT
    elif result_R < 0:
        deviation = ReviewDeviationType.DISCIPLINED_LOSS
    else:
        deviation = ReviewDeviationType.NONE

    return ReviewResult(
        followed_entry=followed_entry,
        followed_stop=followed_stop,
        followed_exit=followed_exit,
        deviation_type=deviation,
        result_R=result_R,
    )

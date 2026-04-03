from .models import EdgeComponent, ScoreCard


def score_component(component: EdgeComponent) -> ScoreCard:
    s = component.score
    if s is None:
        raise ValueError(f"Component '{component.name}' has no score fields set.")

    total = (
        s.persistence * 0.25
        + (6 - s.crowding) * 0.20
        + s.clarity * 0.20
        + s.regime_fit * 0.20
        + s.exploitability * 0.15
    )
    s.total_score = round(total, 2)
    return s

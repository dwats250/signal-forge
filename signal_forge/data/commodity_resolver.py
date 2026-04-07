from __future__ import annotations

LAST_GOOD: dict[str, float] = {}


def validate_price(symbol: str, price: float | None) -> bool:
    if price is None:
        return False
    if symbol == "GOLD":
        return 1000 < price < 4000
    if symbol == "WTI":
        return 20 < price < 200
    return price > 0


def resolve_commodity(symbol: str, fetch_primary, fetch_secondary=None):
    # 1. primary
    price = fetch_primary()
    if validate_price(symbol, price):
        LAST_GOOD[symbol] = price
        return price

    print(f"{symbol} primary invalid: {price}")

    # 2. secondary
    if fetch_secondary:
        price = fetch_secondary()
        if validate_price(symbol, price):
            LAST_GOOD[symbol] = price
            return price

    # 3. last known good
    if symbol in LAST_GOOD:
        print(f"{symbol} using last known good")
        return LAST_GOOD[symbol]

    # 4. unavailable
    print(f"{symbol} unavailable")
    return None

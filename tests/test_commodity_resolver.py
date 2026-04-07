from __future__ import annotations

import unittest

from signal_forge.data import commodity_resolver


class CommodityResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        commodity_resolver.LAST_GOOD.clear()

    def test_resolve_commodity_uses_secondary_after_invalid_primary(self) -> None:
        price = commodity_resolver.resolve_commodity(
            "WTI",
            fetch_primary=lambda: 9.0,
            fetch_secondary=lambda: 82.5,
        )

        self.assertEqual(price, 82.5)
        self.assertEqual(commodity_resolver.LAST_GOOD["WTI"], 82.5)

    def test_resolve_commodity_uses_last_good_when_sources_fail(self) -> None:
        commodity_resolver.LAST_GOOD["GOLD"] = 2350.0

        price = commodity_resolver.resolve_commodity(
            "GOLD",
            fetch_primary=lambda: None,
            fetch_secondary=lambda: 5000.0,
        )

        self.assertEqual(price, 2350.0)


if __name__ == "__main__":
    unittest.main()

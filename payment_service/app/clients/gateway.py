from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ChargeResult:
    ok: bool
    reason: str | None = None


class FakeGateway:
    """Имитация внешнего платёжного шлюза (эквайринга, ПР3: внешняя система контекста «Оплата»)."""

    def __init__(self, limit: int = 100000) -> None:
        self.limit = limit

    def charge(self, amount: Decimal, card_token: str | None) -> ChargeResult:
        if card_token == "tok_fail":
            return ChargeResult(False, "card_declined")
        if amount > self.limit:
            return ChargeResult(False, "limit_exceeded")
        return ChargeResult(True)

    def refund(self, amount: Decimal) -> ChargeResult:
        return ChargeResult(True)

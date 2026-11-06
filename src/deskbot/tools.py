"""The tools the agent can call, and the order data behind them. All data is made up."""

from collections.abc import Callable
from dataclasses import dataclass, field


class ToolError(Exception):
    """The tool ran and refused: a business answer, not a fault."""


class ToolTimeout(Exception):
    """The tool didn't answer. Safe to retry once, for a tool that changes nothing."""


@dataclass
class Order:
    id: str
    customer: str
    email: str
    total: int
    status: str
    refunded: int = 0


def sample_orders() -> dict[str, Order]:
    return {
        "O-1001": Order("O-1001", "asha", "asha@example.test", 120, "delivered"),
        "O-1002": Order("O-1002", "ben", "ben@example.test", 600, "delivered"),
        "O-1003": Order("O-1003", "asha", "asha@example.test", 40, "in_transit"),
    }


@dataclass(frozen=True)
class ToolSpec:
    """What the agent needs to know before it runs a tool."""

    name: str
    params: dict[str, type]
    run: Callable[..., dict]
    changes_state: bool = False


@dataclass
class Toolbox:
    """The tools and their data. A new toolbox has fresh data, so tests can't affect each other."""

    orders: dict[str, Order] = field(default_factory=sample_orders)
    escalations: list[dict] = field(default_factory=list)
    # Test hook: names of tools that time out once, to exercise the retry
    fail_once: set[str] = field(default_factory=set)

    def specs(self) -> dict[str, ToolSpec]:
        specs = [
            ToolSpec("get_order", {"order_id": str}, self.get_order),
            ToolSpec("track_parcel", {"order_id": str}, self.track_parcel),
            ToolSpec("issue_refund", {"order_id": str, "amount": int}, self.issue_refund, True),
            ToolSpec("cancel_order", {"order_id": str}, self.cancel_order, True),
            ToolSpec("escalate", {"order_id": str, "reason": str}, self.escalate, True),
        ]
        return {spec.name: spec for spec in specs}

    def _order(self, order_id: str) -> Order:
        if order_id not in self.orders:
            raise ToolError(f"Order {order_id} does not exist.")
        return self.orders[order_id]

    def _maybe_time_out(self, name: str) -> None:
        if name in self.fail_once:
            self.fail_once.remove(name)
            raise ToolTimeout(name)

    def get_order(self, order_id: str) -> dict:
        self._maybe_time_out("get_order")
        order = self._order(order_id)
        return {
            "id": order.id,
            "customer": order.customer,
            "email": order.email,
            "total": order.total,
            "status": order.status,
            "refunded": order.refunded,
        }

    def track_parcel(self, order_id: str) -> dict:
        self._maybe_time_out("track_parcel")
        return {"id": order_id, "status": self._order(order_id).status}

    def issue_refund(self, order_id: str, amount: int) -> dict:
        order = self._order(order_id)
        if order.refunded + amount > order.total:
            raise ToolError("A refund can't be more than what was paid.")
        order.refunded += amount
        return {"id": order_id, "refunded": order.refunded}

    def cancel_order(self, order_id: str) -> dict:
        order = self._order(order_id)
        if order.status != "in_transit":
            raise ToolError(f"An order that is {order.status} can't be cancelled.")
        order.status = "cancelled"
        return {"id": order_id, "status": order.status}

    def escalate(self, order_id: str, reason: str) -> dict:
        self.escalations.append({"order_id": order_id, "reason": reason})
        return {"id": order_id, "escalated": True}

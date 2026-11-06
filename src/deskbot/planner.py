"""A rule-based planner: the well-behaved stand-in for a language model."""

import re

from deskbot.agent import Finish, Step, ToolCall


class RulePlanner:
    """Reads the task, then follows a fixed plan. It is stateless: the steps so far say where it is."""

    def next_action(self, task: str, steps: list[Step]) -> ToolCall | Finish:
        order = re.search(r"O-\d+", task)
        if not order:
            return Finish("NOT_UNDERSTOOD", "I can only help with an order number.")
        order_id = order.group()

        if not steps:
            return ToolCall("get_order", {"order_id": order_id})
        last = steps[-1]
        if last.outcome == "error":
            return Finish("FAILED", str(last.result))

        refund = re.search(r"refund (\d+)", task, re.IGNORECASE)
        if refund:
            return self._refund(order_id, int(refund.group(1)), last)
        if re.search(r"cancel", task, re.IGNORECASE):
            return self._after("cancel_order", {"order_id": order_id}, last)
        if re.search(r"where", task, re.IGNORECASE):
            return self._after("track_parcel", {"order_id": order_id}, last)
        return Finish("NOT_UNDERSTOOD", "I don't know how to do that.")

    def _refund(self, order_id: str, amount: int, last: Step) -> ToolCall | Finish:
        if last.tool == "issue_refund" and last.result == "needs approval":
            return ToolCall("escalate", {"order_id": order_id, "reason": f"Refund of {amount}"})
        if last.tool == "escalate":
            return Finish("ESCALATED", "A staff member will decide on this refund.")
        return self._after("issue_refund", {"order_id": order_id, "amount": amount}, last)

    def _after(self, tool: str, args: dict, last: Step) -> ToolCall | Finish:
        """Runs the tool once, after get_order, then finishes."""
        if last.tool == tool:
            return Finish("DONE", f"{tool} finished.")
        return ToolCall(tool, args)

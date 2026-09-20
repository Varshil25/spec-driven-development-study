"""Net-balance computation and minimal-transaction settlement.

All money is integer cents. Ordering everywhere derives from the supplied
participant-list order, so output is deterministic (research.md Decisions 2 & 3;
Constitution Principle V). US3 layers remainder conservation guards on top.
"""

from dataclasses import dataclass

from splitter.parser import Expense


@dataclass(frozen=True)
class Payment:
    """A proposed transfer from a net debtor to a net creditor."""

    from_name: str
    to_name: str
    amount_cents: int


def allocate_shares(total_cents: int, n: int) -> list[int]:
    """Split ``total_cents`` into ``n`` shares that sum exactly to the total.

    ``base = total_cents // n`` for everyone; the first ``r = total_cents % n``
    participants (in supplied order) get ``+1`` cent, so shares sum to the total
    exactly and any two differ by at most one cent (FR-004; research.md Dec. 2).
    """
    base, remainder = divmod(total_cents, n)
    return [base + 1 if i < remainder else base for i in range(n)]


def compute_nets(participants: list[str], expenses: list[Expense]) -> list[int]:
    """Return each participant's ``net_cents = paid_cents - share_cents``.

    Results are in supplied participant order; they sum to zero (conservation).
    """
    paid = {name: 0 for name in participants}
    for expense in expenses:
        paid[expense.payer] += expense.amount_cents

    total = sum(paid.values())
    shares = allocate_shares(total, len(participants))
    return [paid[name] - shares[i] for i, name in enumerate(participants)]


def minimal_payments(participants: list[str], nets: list[int]) -> list[Payment]:
    """Greedily match largest debtor with largest creditor (research.md Dec. 3).

    Produces at most ``k - 1`` payments for ``k`` non-zero balances (SC-003),
    and the payment amounts sum to the total imbalance exactly (FR-008). Ties are
    broken by supplied participant order for deterministic output.
    """
    # Preserve supplied order as the tie-break key.
    debtors = [[name, -net] for name, net in zip(participants, nets) if net < 0]
    creditors = [[name, net] for name, net in zip(participants, nets) if net > 0]

    payments: list[Payment] = []
    while debtors and creditors:
        # Largest magnitude first; ties keep earlier supplied-order entries.
        debtors.sort(key=lambda d: -d[1])
        creditors.sort(key=lambda c: -c[1])
        debtor, creditor = debtors[0], creditors[0]

        transfer = min(debtor[1], creditor[1])
        payments.append(Payment(debtor[0], creditor[0], transfer))

        debtor[1] -= transfer
        creditor[1] -= transfer
        if debtor[1] == 0:
            debtors.pop(0)
        if creditor[1] == 0:
            creditors.pop(0)

    return payments


def settle(participants: list[str], expenses: list[Expense]) -> list[Payment]:
    """Compute the minimal settlement for a group (top-level orchestration).

    Asserts conservation invariants so no cent is ever lost or invented
    (FR-008, FR-009; Constitution Principle II).
    """
    nets = compute_nets(participants, expenses)
    assert sum(nets) == 0, "net balances must sum to zero (conservation)"

    payments = minimal_payments(participants, nets)

    total_imbalance = sum(net for net in nets if net > 0)
    assert sum(p.amount_cents for p in payments) == total_imbalance, (
        "payments must sum to the total imbalance (conservation)"
    )
    return payments

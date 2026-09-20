"""Settlement + conservation tests (T008 US1, T019/T024 appended later).

Covers net-balance computation, equal-share assignment, minimal-transaction
settlement, the already-settled case, and the SC-003 bound
(FR-005, FR-006, FR-007, FR-010).
"""

from splitter.parser import Expense
from splitter.settle import (
    Payment,
    allocate_shares,
    compute_nets,
    minimal_payments,
    settle,
)


def E(payer, amount_cents, description="x"):
    return Expense(payer=payer, amount_cents=amount_cents, description=description)


class TestShareAllocation:
    def test_even_division(self):
        assert allocate_shares(4000, 4) == [1000, 1000, 1000, 1000]

    def test_shares_sum_to_total(self):
        assert sum(allocate_shares(3000, 2)) == 3000


class TestNets:
    def test_net_is_paid_minus_share(self):
        # total 3000, equal share 1500 each; Alice paid 3000, Bob 0.
        nets = compute_nets(["Alice", "Bob"], [E("Alice", 3000), E("Bob", 0)])
        assert nets == [1500, -1500]

    def test_nets_sum_to_zero(self):
        nets = compute_nets(
            ["A", "B", "C"], [E("A", 3000), E("B", 600), E("C", 0)]
        )
        assert sum(nets) == 0


class TestSettle:
    def test_single_minimal_transfer(self):
        pays = settle(["Alice", "Bob"], [E("Alice", 3000), E("Bob", 0)])
        assert pays == [Payment("Bob", "Alice", 1500)]

    def test_already_settled_is_empty(self):
        pays = settle(["Alice", "Bob"], [E("Alice", 1000), E("Bob", 1000)])
        assert pays == []

    def test_payments_zero_every_balance(self):
        parts = ["A", "B", "C", "D"]
        exps = [E("A", 4000), E("B", 0), E("C", 0), E("D", 0)]
        nets = compute_nets(parts, exps)
        pays = settle(parts, exps)
        applied = dict(zip(parts, nets))
        for pay in pays:
            applied[pay.from_name] += pay.amount_cents
            applied[pay.to_name] -= pay.amount_cents
        assert all(v == 0 for v in applied.values())

    def test_sc003_transaction_bound(self):
        parts = ["A", "B", "C", "D"]
        exps = [E("A", 4000), E("B", 0), E("C", 0), E("D", 0)]
        nets = compute_nets(parts, exps)
        nonzero = sum(1 for n in nets if n != 0)
        assert len(settle(parts, exps)) <= nonzero - 1

    def test_minimal_payments_matches_settle(self):
        parts = ["Alice", "Bob"]
        nets = compute_nets(parts, [E("Alice", 3000), E("Bob", 0)])
        assert minimal_payments(parts, nets) == [Payment("Bob", "Alice", 1500)]


class TestConservation:
    """US3 (T019): every cent conserved on uneven splits (FR-004/008/009)."""

    def test_uneven_share_allocation(self):
        shares = allocate_shares(1000, 3)
        assert shares == [334, 333, 333]

    def test_shares_sum_exactly_and_differ_by_at_most_one_cent(self):
        shares = allocate_shares(1000, 3)
        assert sum(shares) == 1000
        assert max(shares) - min(shares) <= 1

    def test_first_r_participants_get_extra_cent(self):
        # total 1001, n=4 -> base 250, r=1 -> first participant gets +1.
        assert allocate_shares(1001, 4) == [251, 250, 250, 250]

    def test_payments_sum_to_total_imbalance(self):
        parts = ["Alice", "Bob", "Carol"]
        exps = [E("Alice", 1000)]
        nets = compute_nets(parts, exps)
        pays = settle(parts, exps)
        assert sum(p.amount_cents for p in pays) == sum(n for n in nets if n > 0)

    def test_applying_payments_zeroes_every_balance(self):
        parts = ["Alice", "Bob", "Carol"]
        exps = [E("Alice", 1000)]
        nets = compute_nets(parts, exps)
        applied = dict(zip(parts, nets))
        for pay in settle(parts, exps):
            applied[pay.from_name] += pay.amount_cents
            applied[pay.to_name] -= pay.amount_cents
        assert all(v == 0 for v in applied.values())


class TestScope:
    """Polish (T024): a typical multi-row group settles in one call (SC-006)."""

    def test_multi_row_group_conserves_and_zeroes(self):
        parts = ["Alice", "Bob", "Carol", "Dave", "Erin"]
        exps = [
            E("Alice", 4213),
            E("Bob", 1050),
            E("Carol", 9999),
            E("Dave", 0),
            E("Erin", 777),
            E("Alice", 333),
            E("Carol", 12),
        ]
        nets = compute_nets(parts, exps)
        assert sum(nets) == 0
        pays = settle(parts, exps)
        applied = dict(zip(parts, nets))
        for pay in pays:
            applied[pay.from_name] += pay.amount_cents
            applied[pay.to_name] -= pay.amount_cents
        assert all(v == 0 for v in applied.values())
        nonzero = sum(1 for n in nets if n != 0)
        assert len(pays) <= nonzero - 1

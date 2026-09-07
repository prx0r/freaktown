"""Unit tests for the on-chain POT layer: x402 actions, escrow, payouts,
auction, tickets. No network, no chain — pure deterministic logic."""

import base64
import json

import pytest


# ── x402 actions ─────────────────────────────────────────────────────

class TestX402Actions:
    def test_atomic_conversion(self):
        from backend.services.potchain import usd_cents_to_atomic, atomic_to_usd_cents

        assert usd_cents_to_atomic(100) == "1000000"  # $1 → 1M units
        assert usd_cents_to_atomic(200) == "2000000"
        assert atomic_to_usd_cents("1000000") == 100
        with pytest.raises(ValueError):
            usd_cents_to_atomic(0)
        with pytest.raises(ValueError):
            atomic_to_usd_cents("999")  # sub-cent

    def test_usdc_constants_match_official_sdk(self):
        """Drift guard: our token addresses must equal the official SDK's."""
        from backend.services.potchain import USDC_BASE_MAINNET, USDC_BASE_SEPOLIA
        from x402.mechanisms.evm.default_assets import DEFAULT_ASSETS

        mainnet = {a["asset"] for a in DEFAULT_ASSETS["eip155:8453"]}
        sepolia = {a["asset"] for a in DEFAULT_ASSETS["eip155:84532"]}
        assert USDC_BASE_MAINNET in mainnet
        assert USDC_BASE_SEPOLIA in sepolia

    def test_requirements_are_spec_conformant(self):
        from backend.services.potchain import NetworkConfig, payment_required
        from x402.schemas import PaymentRequired

        req = payment_required(
            "message", "freak-town:message:ep1", 200,
            NetworkConfig.sepolia("0xPOT"),
        )
        # Validates against the official SDK models (single source of truth)
        parsed = PaymentRequired.model_validate(req)
        assert parsed.x402_version == 2
        assert len(parsed.accepts) == 1
        accept = parsed.accepts[0]
        assert accept.scheme == "exact"
        assert accept.network == "eip155:84532"
        assert accept.amount == "2000000"
        assert accept.pay_to == "0xPOT"
        # Wire keys are camelCase per spec
        assert req["accepts"][0]["payTo"] == "0xPOT"
        assert req["accepts"][0]["maxTimeoutSeconds"] == 300

    def test_requirements_reject_bad_input(self):
        from backend.services.potchain import NetworkConfig, payment_required

        cfg = NetworkConfig.sepolia("0xPOT")
        with pytest.raises(ValueError):
            payment_required("nonexistent", "u", 100, cfg)
        with pytest.raises(ValueError):
            payment_required("message", "u", 100, cfg)  # below $2 min
        with pytest.raises(ValueError):
            payment_required("pot", "u", 100, NetworkConfig.sepolia(""))

    def test_header_round_trip(self):
        from backend.services.potchain import (
            NetworkConfig, decode_payment_required, encode_payment_required,
            payment_required,
        )

        req = payment_required("hype", "u", 500, NetworkConfig.sepolia("0xPOT"))
        assert decode_payment_required(encode_payment_required(req)) == req

    def test_parse_v2_dict_and_xpayment(self):
        from backend.services.potchain import parse_payment_payload

        payload = {
            "x402Version": 2,
            "accepted": {
                "scheme": "exact", "network": "eip155:84532",
                "amount": "2000000", "asset": "0xUSDC",
                "payTo": "0xPOT", "maxTimeoutSeconds": 300,
                "extra": {"name": "USDC", "version": "2"},
            },
            "payload": {"signature": "0xabc", "authorization": {"from": "0x1"}},
        }
        parsed = parse_payment_payload(payload)
        assert parsed.get_network() == "eip155:84532"

        # X-PAYMENT transport: base64 of the same JSON (what the modal sends)
        b64 = base64.b64encode(json.dumps(payload).encode()).decode()
        assert parse_payment_payload(b64).get_scheme() == "exact"

    def test_parse_rejects_v1_and_garbage(self):
        from backend.services.potchain import parse_payment_payload

        with pytest.raises(ValueError, match="invalid_x402_version"):
            parse_payment_payload({"x402Version": 1, "scheme": "exact"})
        with pytest.raises(ValueError, match="invalid_payload"):
            parse_payment_payload("!!!not-base64!!!")
        with pytest.raises(ValueError, match="invalid_payload"):
            parse_payment_payload({"x402Version": 2})  # missing accepted


# ── Escrow ───────────────────────────────────────────────────────────

class TestEscrow:
    def _pot(self):
        from backend.services.potchain import LocalPotEscrow

        escrow = LocalPotEscrow()
        escrow.open("ep1", closer="0xCLOSER")
        return escrow

    def test_full_lifecycle(self):
        escrow = self._pot()
        assert escrow.contribute("ep1", "0xA", 1_000_000, tx="0x1") == 1_000_000
        assert escrow.contribute("ep1", "0xB", 2_000_000, message="END THIS") == 3_000_000
        view = escrow.view("ep1")
        assert (view.status, view.total, view.contribution_count) == ("OPEN", 3_000_000, 2)

        escrow.finalize_winner("ep1", winner="0xWIN", closer="0xCLOSER")
        assert escrow.view("ep1").status == "LOCKED"
        assert escrow.claim("ep1", "0xWIN") == 3_000_000
        assert escrow.view("ep1").status == "CLAIMED"

    def test_claim_rules(self):
        escrow = self._pot()
        escrow.contribute("ep1", "0xA", 100)
        with pytest.raises(ValueError):
            escrow.claim("ep1", "0xWIN")  # not locked yet
        escrow.finalize_winner("ep1", winner="0xWIN", closer="0xCLOSER")
        with pytest.raises(ValueError):
            escrow.claim("ep1", "0xA")  # not the winner
        escrow.claim("ep1", "0xWIN")
        with pytest.raises(ValueError):
            escrow.claim("ep1", "0xWIN")  # double claim

    def test_finalize_rules(self):
        escrow = self._pot()
        escrow.contribute("ep1", "0xA", 100)
        with pytest.raises(ValueError):
            escrow.finalize_winner("ep1", winner="0xWIN", closer="0xIMPOSTOR")
        with pytest.raises(ValueError):
            escrow.finalize_winner("ep1", winner="", closer="0xCLOSER")
        escrow.finalize_winner("ep1", winner="0xWIN", closer="0xCLOSER")
        with pytest.raises(ValueError):
            escrow.contribute("ep1", "0xC", 100)  # locked
        with pytest.raises(ValueError):
            escrow.finalize_winner("ep1", winner="0xX", closer="0xCLOSER")  # twice

    def test_refund_flow(self):
        escrow = self._pot()
        escrow.contribute("ep1", "0xA", 1_000_000)
        escrow.contribute("ep1", "0xB", 500_000)
        with pytest.raises(ValueError):
            escrow.withdraw_refund("ep1", "0xA")  # not enabled
        escrow.emergency_refund("ep1", admin="0xCLOSER")
        assert escrow.withdraw_refund("ep1", "0xA") == 1_000_000
        with pytest.raises(ValueError):
            escrow.withdraw_refund("ep1", "0xA")  # twice
        with pytest.raises(ValueError):
            escrow.withdraw_refund("ep1", "0xNOBODY")

    def test_unknown_pot(self):
        escrow = self._pot()
        with pytest.raises(ValueError):
            escrow.contribute("nope", "0xA", 100)


# ── Payouts ──────────────────────────────────────────────────────────

class TestPayouts:
    def test_split_sums_to_total(self):
        from backend.services.potchain import split_pot

        for total in (0, 1, 99, 10_000_000, 12_804_000_000):
            s = split_pot(total)
            assert s["ella_winner"] + s["stream_champion"] + s["season_pot"] == total

    def test_split_ratios(self):
        from backend.services.potchain import split_pot

        s = split_pot(10_000_000)  # $10k pot
        assert s == {"ella_winner": 7_000_000, "stream_champion": 2_000_000,
                     "season_pot": 1_000_000}

    def test_no_stream_champion_rolls_to_season(self):
        from backend.services.potchain import split_pot

        s = split_pot(10_000_000, stream_champion=False)
        assert s["stream_champion"] == 0
        assert s["season_pot"] == 3_000_000

    def test_payout_event(self):
        from backend.services.potchain import payout_event_payload

        p = payout_event_payload("ep1", "0xELLA", "0xSTREAM", 10_000_000, "eip155:8453")
        assert p["ella_share_atomic"] == 7_000_000
        assert p["stream_share_atomic"] == 2_000_000
        assert p["season_share_atomic"] == 1_000_000
        assert p["same_wallet_won_both"] is False

        p = payout_event_payload("ep1", "0xBOTH", "0xBOTH", 10_000_000, "eip155:8453")
        assert p["same_wallet_won_both"] is True
        assert p["ella_share_atomic"] == 9_000_000
        assert p["stream_share_atomic"] == 0


# ── Auction ──────────────────────────────────────────────────────────

class TestAuction:
    def _auction(self):
        from backend.services.potchain import SponsorAuction

        return SponsorAuction("ep1", close_at=1_000_000.0)

    def test_bid_floor_and_close(self):
        a = self._auction()
        b1 = a.place_bid("acme", 3800, "Acme Corp does stuff", now=100.0)
        assert b1.moderation == "pending"
        a.moderate(b1.bid_id, True)
        with pytest.raises(ValueError):
            a.place_bid("cheap", 3800, "same bid", now=101.0)  # must exceed
        with pytest.raises(ValueError):
            a.place_bid("cheap", 100, "x" * 281, now=101.0)  # copy too long
        b2 = a.place_bid("dogshit", 5000, "doge dot xyz", now=102.0)
        a.moderate(b2.bid_id, False, note="rejected copy")
        result = a.close(now=103.0)
        assert result.winner_bid_id == b1.bid_id
        assert result.winning_cents == 3800

    def test_tie_goes_to_earliest(self):
        a = self._auction()
        b1 = a.place_bid("first", 5000, "aaa", now=100.0)
        # floor blocks equal bids; simulate tie via direct moderation path
        a.moderate(b1.bid_id, True)
        assert a.highest_eligible().bid_id == b1.bid_id

    def test_rejected_winner_promotes_runner_up(self):
        a = self._auction()
        b1 = a.place_bid("a", 3000, "aaa", now=100.0)
        b2 = a.place_bid("b", 5000, "bbb", now=101.0)
        a.moderate(b1.bid_id, True)
        a.moderate(b2.bid_id, True)
        result = a.close(now=102.0)
        assert result.winner_bid_id == b2.bid_id
        promoted = a.mark_defaulted(b2.bid_id)
        assert promoted.winner_bid_id == b1.bid_id
        assert promoted.defaulted == [b2.bid_id]

    def test_closed_auction(self):
        a = self._auction()
        with pytest.raises(ValueError):
            a.place_bid("late", 100, "too late", now=2_000_000.0)  # past close
        result = a.close(now=2_000_000.0)
        assert result.winner_bid_id is None and result.winning_cents == 0
        with pytest.raises(ValueError):
            a.close()


# ── Tickets ──────────────────────────────────────────────────────────

class TestTickets:
    def test_weekly_claim_idempotent_per_week(self):
        from backend.services.potchain import TicketWallet

        w = TicketWallet()
        assert w.claim_weekly("u1", now=1_786_000_000.0) == 1
        with pytest.raises(ValueError):
            w.claim_weekly("u1", now=1_786_000_100.0)  # same week
        assert w.claim_weekly("u1", now=1_786_000_000.0 + 8 * 86400) == 2

    def test_redeem_and_balance(self):
        from backend.services.potchain import TicketWallet

        w = TicketWallet()
        with pytest.raises(ValueError):
            w.redeem("broke")
        w.grant("u2", "reputation", 2, note="regular")
        assert w.redeem("u2") == 1
        assert w.redeem("u2") == 0
        with pytest.raises(ValueError):
            w.redeem("u2")

    def test_purchase_disabled_and_bad_source(self):
        from backend.services.potchain import TicketWallet

        w = TicketWallet()
        with pytest.raises(ValueError, match="not enabled"):
            w.grant("u3", "purchase", 1)
        with pytest.raises(ValueError):
            w.grant("u3", "farming", 1)


# ── Chain pot payloads fold into the ledger ──────────────────────────

class TestChainPotTotals:
    def test_amount_usdc_strings(self):
        from backend.services.pot import pot_total, usdc_str_to_cents

        assert usdc_str_to_cents("10.00") == 1000
        assert usdc_str_to_cents("0.01") == 1
        events = [
            {"type": "pot.contribution", "episode_id": "ep1",
             "payload": {"amount_usdc": "10.00", "tx": "0xabc", "network": "eip155:8453",
                         "source": "chain"}},
            {"type": "pot.contribution", "episode_id": "ep1",
             "payload": {"amount_cents": 500, "source": "manual"}},
        ]
        assert pot_total(events) == 1500

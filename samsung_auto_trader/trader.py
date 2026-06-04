from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from account import AccountService, AccountSnapshot
from config import Settings
from market_data import MarketDataService
from orders import OpenOrder, OrderExecutionStatus, OrderService, OrderSubmission

logger = logging.getLogger(__name__)

BUY_ORDER_SLOTS = ("buy", "dip_buy", "dip_buy_2", "breakout_buy", "breakout_buy_2")
SELL_ORDER_SLOT = "sell"


@dataclass
class PendingOrder:
    side: str
    order_number: str
    submitted_at: str
    order_price: int = 0
    reference_price: int = 0
    branch_number: str = ""


@dataclass(frozen=True)
class StrategyPlan:
    buy_offset_krw: int
    sell_offset_krw: int
    buy_allowed: bool
    reason: str


@dataclass(frozen=True)
class BuyOpportunity:
    slot: str
    label: str
    offset_krw: int
    reason: str


class SamsungAutoTrader:
    def __init__(
        self,
        settings: Settings,
        market_data: MarketDataService,
        account_service: AccountService,
        order_service: OrderService,
    ) -> None:
        self.settings = settings
        self.market_data = market_data
        self.account_service = account_service
        self.order_service = order_service
        self.pending_orders: dict[str, PendingOrder] = {}
        self.price_history: list[int] = []

    def run(self) -> None:
        logger.info(
            "Trading window starts at %s and ends at %s.",
            self.settings.trading_start_hhmm,
            self.settings.trading_end_hhmm,
        )
        self._restore_pending_orders()

        while True:
            now = datetime.now(self.settings.timezone)
            if self._after_trading_window(now):
                logger.info("Trading window ended at %s. Stopping.", self.settings.trading_end_hhmm)
                return

            if self._before_trading_window(now):
                sleep_seconds = min(self.settings.poll_interval_seconds, self._seconds_until_start(now))
                logger.info("Before trading window. Sleeping for %s seconds.", sleep_seconds)
                time.sleep(sleep_seconds)
                continue

            self._run_cycle()
            time.sleep(self.settings.poll_interval_seconds)

    def _run_cycle(self) -> None:
        quote = self.market_data.get_current_price(self.settings.symbol)
        self._remember_price(quote.current_price)
        self._sync_pending_orders()
        before = self.account_service.get_snapshot(self.settings.symbol)

        logger.info("Current price for %s: %s KRW", self.settings.symbol, quote.current_price)
        logger.info(
            "Holdings before order: %s share(s), available cash: %s KRW",
            before.holding.quantity,
            before.available_cash,
        )

        strategy = self._build_strategy_plan()
        buy_price = _round_to_tick(
            max(quote.current_price - strategy.buy_offset_krw, 1),
            direction="down",
        )
        sell_price = _round_to_tick(
            quote.current_price + strategy.sell_offset_krw,
            direction="up",
        )
        if (
            strategy.buy_allowed
            and "buy" not in self.pending_orders
            and self._open_buy_order_count() < self.settings.max_open_buy_orders
            and before.available_cash >= buy_price * self.settings.order_quantity
        ):
            requested_at = datetime.now(self.settings.timezone).isoformat(timespec="seconds")
            logger.info(
                "Buy order request at %s: current_price=%s KRW, order_price=%s KRW, quantity=%s, strategy=%s",
                requested_at,
                quote.current_price,
                buy_price,
                self.settings.order_quantity,
                strategy.reason,
            )
            submission = self.order_service.place_limit_buy(
                self.settings.symbol,
                self.settings.order_quantity,
                buy_price,
            )
            self.pending_orders["buy"] = PendingOrder(
                side="buy",
                order_number=submission.order_number,
                submitted_at=requested_at,
                order_price=buy_price,
                reference_price=quote.current_price,
                branch_number=submission.branch_number,
            )
            logger.info(
                "Buy order accepted: order_number=%s, requested_at=%s, current_price=%s KRW, order_price=%s KRW",
                submission.order_number,
                requested_at,
                quote.current_price,
                buy_price,
            )
            self._verify_after_order(submission, before, pending_key="buy")
        else:
            logger.info(
                "Skipping buy order: buy_allowed=%s cash_ok=%s pending=%s open_buy_orders=%s/%s strategy=%s",
                strategy.buy_allowed,
                before.available_cash >= buy_price * self.settings.order_quantity,
                "buy" in self.pending_orders,
                self._open_buy_order_count(),
                self.settings.max_open_buy_orders,
                strategy.reason,
            )

        self._maybe_place_opportunity_buy(quote.current_price, before, strategy)

        if "sell" not in self.pending_orders and before.holding.quantity >= self.settings.order_quantity:
            requested_at = datetime.now(self.settings.timezone).isoformat(timespec="seconds")
            logger.info(
                "Sell order request at %s: current_price=%s KRW, order_price=%s KRW, quantity=%s, strategy=%s",
                requested_at,
                quote.current_price,
                sell_price,
                self.settings.order_quantity,
                strategy.reason,
            )
            submission = self.order_service.place_limit_sell(
                self.settings.symbol,
                self.settings.order_quantity,
                sell_price,
            )
            self.pending_orders["sell"] = PendingOrder(
                side="sell",
                order_number=submission.order_number,
                submitted_at=requested_at,
                order_price=sell_price,
                reference_price=quote.current_price,
                branch_number=submission.branch_number,
            )
            logger.info(
                "Sell order accepted: order_number=%s, requested_at=%s, current_price=%s KRW, order_price=%s KRW",
                submission.order_number,
                requested_at,
                quote.current_price,
                sell_price,
            )
            self._verify_after_order(submission, before, pending_key="sell")
        else:
            logger.info("Skipping sell order because holdings are insufficient or a sell order is still pending.")

    def _maybe_place_opportunity_buy(
        self,
        current_price: int,
        before: AccountSnapshot,
        strategy: StrategyPlan,
    ) -> None:
        if not strategy.buy_allowed:
            logger.info("Skipping opportunity buys because trend filter disabled new buys: %s", strategy.reason)
            return

        if self._open_buy_order_count() >= self.settings.max_open_buy_orders:
            logger.info(
                "Skipping opportunity buys because open buy order limit is reached: %s/%s",
                self._open_buy_order_count(),
                self.settings.max_open_buy_orders,
            )
            return

        for opportunity in self._buy_opportunities(current_price):
            if self._open_buy_order_count() >= self.settings.max_open_buy_orders:
                logger.info(
                    "Stopping opportunity buys because open buy order limit is reached: %s/%s",
                    self._open_buy_order_count(),
                    self.settings.max_open_buy_orders,
                )
                return

            pending_slot = self._available_opportunity_slot(opportunity.slot)
            if pending_slot is None:
                logger.info("Skipping %s because all matching pending slots are still open.", opportunity.label)
                continue

            buy_price = _round_to_tick(
                max(current_price - opportunity.offset_krw, 1),
                direction="down",
            )
            if before.available_cash < buy_price * self.settings.order_quantity:
                logger.info(
                    "Skipping %s because cash is insufficient: order_price=%s KRW quantity=%s",
                    opportunity.label,
                    buy_price,
                    self.settings.order_quantity,
                )
                continue

            requested_at = datetime.now(self.settings.timezone).isoformat(timespec="seconds")
            logger.info(
                "%s request at %s: current_price=%s KRW, order_price=%s KRW, quantity=%s, reason=%s",
                opportunity.label,
                requested_at,
                current_price,
                buy_price,
                self.settings.order_quantity,
                opportunity.reason,
            )
            submission = self.order_service.place_limit_buy(
                self.settings.symbol,
                self.settings.order_quantity,
                buy_price,
            )
            self.pending_orders[pending_slot] = PendingOrder(
                side="buy",
                order_number=submission.order_number,
                submitted_at=requested_at,
                order_price=buy_price,
                reference_price=current_price,
                branch_number=submission.branch_number,
            )
            logger.info(
                "%s accepted: order_number=%s, requested_at=%s, current_price=%s KRW, order_price=%s KRW",
                opportunity.label,
                submission.order_number,
                requested_at,
                current_price,
                buy_price,
            )
            self._verify_after_order(submission, before, pending_key=pending_slot)

    def _verify_after_order(
        self,
        submission: OrderSubmission,
        before: AccountSnapshot,
        pending_key: str,
    ) -> None:
        time.sleep(self.settings.post_order_wait_seconds)

        after = self.account_service.get_snapshot(self.settings.symbol)
        status = self.order_service.get_execution_status(submission.order_number, submission.symbol)

        logger.info(
            "Holdings after order: %s share(s), available cash: %s KRW",
            after.holding.quantity,
            after.available_cash,
        )

        if status is None:
            if self._filled_by_snapshot(submission.side, before, after):
                logger.info("Execution seems to have occurred from holdings change.")
                self.pending_orders.pop(pending_key, None)
                return

            logger.warning(
                "Execution check could not find order %s. Review raw response aliases if needed.",
                submission.order_number or "<empty>",
            )
            return

        self._log_execution_status(submission, status)
        if not status.is_open:
            self.pending_orders.pop(pending_key, None)

    def _log_execution_status(
        self,
        submission: OrderSubmission,
        status: OrderExecutionStatus,
    ) -> None:
        logger.info(
            "Execution check for %s order %s: filled=%s remaining=%s",
            submission.side,
            submission.order_number,
            status.filled_quantity,
            status.remaining_quantity,
        )
        if status.is_filled:
            logger.info("Execution seems complete for order %s.", submission.order_number)
        elif status.is_open:
            logger.info("Order %s is still open.", submission.order_number)
        else:
            logger.info("Order %s is closed without a clear fill signal.", submission.order_number)

    def _restore_pending_orders(self) -> None:
        open_orders = self.order_service.get_open_orders(self.settings.symbol)
        if not open_orders:
            logger.info("No open orders found at startup.")
            return

        used_slots: set[str] = set()
        for open_order in open_orders:
            slot = self._slot_for_open_order(open_order, used_slots)
            if slot is None:
                logger.warning(
                    "Additional open %s order found at startup but no free slot is available: order_number=%s remaining=%s",
                    open_order.side,
                    open_order.order_number,
                    open_order.remaining_quantity,
                )
                continue

            used_slots.add(slot)
            self.pending_orders[slot] = self._pending_from_open_order(open_order)
            logger.info(
                "Restored open %s order at startup: slot=%s order_number=%s order_price=%s KRW remaining=%s filled=%s",
                open_order.side,
                slot,
                open_order.order_number,
                open_order.order_price,
                open_order.remaining_quantity,
                open_order.filled_quantity,
            )

    def _pending_from_open_order(self, open_order: OpenOrder) -> PendingOrder:
        return PendingOrder(
            side=open_order.side,
            order_number=open_order.order_number,
            submitted_at=open_order.ordered_at,
            order_price=open_order.order_price,
            branch_number=open_order.branch_number,
        )

    def _sync_pending_orders(self) -> dict[str, OpenOrder]:
        open_orders = self.order_service.get_open_orders(self.settings.symbol)
        open_by_slot: dict[str, OpenOrder] = {}
        used_slots: set[str] = set()

        for open_order in open_orders:
            slot = self._slot_for_open_order(open_order, used_slots)
            if slot is None:
                logger.warning(
                    "Multiple open %s orders found but no free slot is available; leaving order %s untouched.",
                    open_order.side,
                    open_order.order_number,
                )
                continue
            used_slots.add(slot)
            open_by_slot[slot] = open_order

        for slot in list(self.pending_orders):
            if slot not in open_by_slot:
                logger.info("Pending %s order is no longer open. Removing local pending marker.", slot)
                self.pending_orders.pop(slot, None)

        for slot, open_order in open_by_slot.items():
            self.pending_orders[slot] = self._pending_from_open_order(open_order)

        return open_by_slot

    def _slot_for_open_order(self, open_order: OpenOrder, used_slots: set[str]) -> str | None:
        existing_slot = self._pending_slot_for_order_number(open_order.order_number)
        if existing_slot and existing_slot not in used_slots:
            return existing_slot

        if open_order.side == "sell":
            return SELL_ORDER_SLOT if SELL_ORDER_SLOT not in used_slots else None

        for slot in BUY_ORDER_SLOTS:
            if slot not in used_slots:
                return slot
        return None

    def _pending_slot_for_order_number(self, order_number: str) -> str | None:
        for slot, pending in self.pending_orders.items():
            if pending.order_number == order_number:
                return slot
        return None

    def _open_buy_order_count(self) -> int:
        return sum(1 for pending in self.pending_orders.values() if pending.side == "buy")

    def _available_opportunity_slot(self, base_slot: str) -> str | None:
        for slot in (base_slot, f"{base_slot}_2"):
            if slot in BUY_ORDER_SLOTS and slot not in self.pending_orders:
                return slot
        return None

    def _remember_price(self, current_price: int) -> None:
        self.price_history.append(current_price)
        max_window = max(
            self.settings.volatility_window_size,
            self.settings.trend_window_size,
            self.settings.dip_average_window_size + 1,
            self.settings.breakout_window_size + 1,
            1,
        )
        if len(self.price_history) > max_window:
            self.price_history = self.price_history[-max_window:]

    def _build_strategy_plan(self) -> "StrategyPlan":
        sell_volatility_offset = self._sell_volatility_offset()
        trend = self._trend_state()
        buy_offset = self.settings.buy_offset_krw
        sell_offset = sell_volatility_offset
        buy_allowed = True

        if trend == "rising":
            sell_offset *= self.settings.trend_sell_offset_multiplier
        elif trend == "falling" and self.settings.trend_buy_pause_enabled:
            buy_allowed = False

        reason = (
            f"buy_offset_fixed={buy_offset}, sell_volatility_offset={sell_volatility_offset}, trend={trend}, "
            f"buy_offset={buy_offset}, sell_offset={sell_offset}"
        )
        return StrategyPlan(
            buy_offset_krw=buy_offset,
            sell_offset_krw=sell_offset,
            buy_allowed=buy_allowed,
            reason=reason,
        )

    def _sell_volatility_offset(self) -> int:
        window = self.price_history[-self.settings.volatility_window_size :]
        if len(window) < 2:
            return self.settings.sell_offset_krw

        price_range = max(window) - min(window)
        if price_range >= self.settings.volatility_range_threshold_krw:
            return self.settings.volatility_offset_krw
        return self.settings.sell_offset_krw

    def _buy_opportunities(self, current_price: int) -> list[BuyOpportunity]:
        opportunities: list[BuyOpportunity] = []
        dip = self._dip_buy_opportunity(current_price)
        if dip:
            opportunities.append(dip)

        breakout = self._breakout_buy_opportunity(current_price)
        if breakout:
            opportunities.append(breakout)

        return opportunities

    def _dip_buy_opportunity(self, current_price: int) -> BuyOpportunity | None:
        window = self._previous_prices(self.settings.dip_average_window_size)
        if len(window) < self.settings.dip_average_window_size:
            return None

        average_price = sum(window) / len(window)
        threshold_price = average_price * (1 - self.settings.dip_buy_threshold_bps / 10_000)
        if current_price > threshold_price:
            return None

        return BuyOpportunity(
            slot="dip_buy",
            label="Dip buy",
            offset_krw=self.settings.dip_buy_offset_krw,
            reason=(
                f"current_price={current_price} <= average({len(window)}) "
                f"{average_price:.1f} - {self.settings.dip_buy_threshold_bps}bps"
            ),
        )

    def _breakout_buy_opportunity(self, current_price: int) -> BuyOpportunity | None:
        window = self._previous_prices(self.settings.breakout_window_size)
        if len(window) < self.settings.breakout_window_size:
            return None

        box_high = max(window)
        box_low = min(window)
        box_range = box_high - box_low
        if box_range > self.settings.breakout_range_max_krw or current_price <= box_high:
            return None

        return BuyOpportunity(
            slot="breakout_buy",
            label="Breakout buy",
            offset_krw=self.settings.breakout_buy_offset_krw,
            reason=(
                f"current_price={current_price} > box_high={box_high}, "
                f"box_range={box_range} <= {self.settings.breakout_range_max_krw}"
            ),
        )

    def _previous_prices(self, window_size: int) -> list[int]:
        if len(self.price_history) <= 1:
            return []
        return self.price_history[:-1][-window_size:]

    def _trend_state(self) -> str:
        window = self.price_history[-self.settings.trend_window_size :]
        if len(window) < self.settings.trend_window_size:
            return "neutral"

        if all(left < right for left, right in zip(window, window[1:])):
            return "rising"
        if all(left > right for left, right in zip(window, window[1:])):
            return "falling"
        return "neutral"

    def _filled_by_snapshot(
        self,
        side: str,
        before: AccountSnapshot,
        after: AccountSnapshot,
    ) -> bool:
        if side == "buy":
            return after.holding.quantity > before.holding.quantity
        return after.holding.quantity < before.holding.quantity

    def _before_trading_window(self, now: datetime) -> bool:
        return now.strftime("%H:%M") < self.settings.trading_start_hhmm

    def _after_trading_window(self, now: datetime) -> bool:
        return now.strftime("%H:%M") > self.settings.trading_end_hhmm

    def _seconds_until_start(self, now: datetime) -> int:
        start_time = datetime.strptime(self.settings.trading_start_hhmm, "%H:%M").time()
        start_dt = now.replace(
            hour=start_time.hour,
            minute=start_time.minute,
            second=0,
            microsecond=0,
        )
        return max(1, int((start_dt - now).total_seconds()))


def _round_to_tick(price: int, *, direction: str) -> int:
    tick = _krx_tick_size(price)
    if direction == "up":
        return ((price + tick - 1) // tick) * tick
    return max((price // tick) * tick, tick)


def _krx_tick_size(price: int) -> int:
    if price < 2_000:
        return 1
    if price < 5_000:
        return 5
    if price < 20_000:
        return 10
    if price < 50_000:
        return 50
    if price < 200_000:
        return 100
    if price < 500_000:
        return 500
    return 1_000

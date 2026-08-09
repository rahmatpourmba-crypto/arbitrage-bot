import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import requests

import config

log = logging.getLogger("listing")

ANNOUNCE_URL = getattr(config, "LISTING_ANNOUNCE_URL", "") or ""
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_TITLE_RE = re.compile(r'\\?"title\\?":\\?"([^"\\]{4,140})\\"')
_SKIP_WORDS = ("Futures", "Stock", "Copy Trade", "Earn", "Launchpad", "Dividend",
               "Promotion", "Rewards", "Deposit", "Maintenance", "Delist", "Suspension")
_ALLCAPS_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,15}\b")
_SKIP_TICKERS = {
    "MEXC", "USDT", "USD", "BTC", "ETH", "BUSD", "FDUSD", "TUSD", "DAI",
    "MEME", "NOW", "LIVE", "FIRST", "MARKET", "LIST", "LISTED", "WILL",
    "TRADING", "INNOVATION", "ZONE", "TRADE", "OPEN", "STARTS", "SUPPORT",
}


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _ticker_from_title(title):
    m = re.search(r":\s*([A-Z][A-Z0-9]{1,15})\s+Now Live on MEXC", title)
    if m:
        return m.group(1)
    m = re.search(r"MEXC (?:to|Will) List\s+([A-Z][A-Z0-9]{1,15})", title)
    if m:
        return m.group(1)
    return None


class ListingHunter:
    def __init__(self, exchange):
        self.exchange = exchange
        self.state = self._load_state()
        if self.paper:
            if "paper_usdt" not in self.state:
                self.state["paper_usdt"] = config.PAPER_START_USDT
        if not self.state.get("known"):
            log.info("First run: building baseline of existing %s markets (no buys on this run)",
                     config.LISTING_EXCHANGE.upper())
            self._refresh_markets()
            self._save()

    @property
    def paper(self):
        return config.PAPER_TRADING

    def _load_state(self):
        try:
            with open(config.LISTING_STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"known": [], "announced": {}, "positions": {}, "closed": [], "closed_symbols": []}

    def _save(self):
        try:
            with open(config.LISTING_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _fetch_symbols(self):
        try:
            tickers = self.exchange.fetch_tickers()
            return {s for s in tickers if s.endswith("/USDT")}
        except Exception as exc:
            log.warning("fetch_tickers failed: %s", exc)
            try:
                self.exchange.load_markets()
                return {s for s in self.exchange.symbols if s.endswith("/USDT")}
            except Exception as exc2:
                log.warning("load_markets fallback failed: %s", exc2)
                return set()

    def _refresh_markets(self):
        symbols = self._fetch_symbols()
        if symbols:
            self.state["known"] = list(symbols)

    def check_announcements(self):
        if not ANNOUNCE_URL:
            log.info("announcement URL not configured, skipping (using market-diff only)")
            return
        try:
            r = requests.get(ANNOUNCE_URL, timeout=20, headers=HEADERS)
            titles = _TITLE_RE.findall(r.text)
        except Exception as exc:
            log.warning("announcement fetch failed: %s", exc)
            return
        seen = set(self.state.get("announced_seen", []))
        announced = dict(self.state.get("announced", {}))
        now = time.time()
        changed = False
        for raw in titles:
            title = raw.strip()
            if title in seen:
                continue
            if "Now Live on" not in title and "Will List" not in title and "to List" not in title and "Listing" not in title:
                continue
            if any(w in title for w in _SKIP_WORDS):
                continue
            seen.add(title)
            ticker = _ticker_from_title(title)
            if ticker and ticker not in _SKIP_TICKERS:
                announced[ticker] = now
            log.info("NEW ANNOUNCEMENT: %s (ticker=%s)", title, ticker)
            changed = True
        self.state["announced_seen"] = list(seen)
        self.state["announced"] = announced
        if changed:
            self._save()

    def _price(self, symbol):
        try:
            t = self.exchange.fetch_ticker(symbol)
            price = t.get("last") or t.get("close")
            if price:
                return float(price)
        except Exception:
            pass
        try:
            book = self.exchange.fetch_order_book(symbol, limit=1)
            if book.get("bids"):
                return float(book["bids"][0][0])
        except Exception:
            pass
        return None

    def _maybe_buy(self, symbol):
        if len(self.state["positions"]) >= config.LISTING_MAX_POSITIONS:
            log.info("MAX POSITIONS reached, skip %s", symbol)
            return
        if symbol in self.state["positions"] or symbol in self.state.get("closed_symbols", []):
            return
        price = self._price(symbol)
        if not price or price <= 0:
            log.warning("no tradable price yet for %s, will retry next scan", symbol)
            return
        budget = config.LISTING_BUDGET_USDT
        amount = budget / price
        if self.paper:
            if self.state["paper_usdt"] < budget:
                log.info("paper budget too low for %s (%.2f left)", symbol, self.state["paper_usdt"])
                return
            self.state["paper_usdt"] -= amount * price * (1 + config.taker_fee(config.LISTING_EXCHANGE))
        else:
            try:
                order = self.exchange.create_order(symbol, "market", "buy", amount)
                log.info("LIVE ORDER buy %s -> %s", symbol, order.get("id"))
            except Exception as exc:
                log.error("LIVE BUY FAILED %s: %s", symbol, exc)
                return
        self.state["positions"][symbol] = {
            "amount": amount,
            "buy_price": price,
            "highest": price,
            "buy_time": utc_now(),
        }
        log.info("BOUGHT %s amount=%.6f @ %s | budget=%s USDT", symbol, amount, price, budget)
        self._save()

    def _sell(self, symbol, price):
        pos = self.state["positions"].pop(symbol)
        amount = pos["amount"]
        if self.paper:
            revenue = amount * price * (1 - config.taker_fee(config.LISTING_EXCHANGE))
            self.state["paper_usdt"] += revenue
        else:
            try:
                order = self.exchange.create_order(symbol, "market", "sell", amount)
                log.info("LIVE ORDER sell %s -> %s", symbol, order.get("id"))
            except Exception as exc:
                log.error("LIVE SELL FAILED %s: %s (keeping position)", symbol, exc)
                self.state["positions"][symbol] = pos
                return
        pnl_pct = (price - pos["buy_price"]) / pos["buy_price"] * 100
        self.state.setdefault("closed_symbols", []).append(symbol)
        self.state.setdefault("closed", []).append({
            "symbol": symbol,
            "buy_price": pos["buy_price"],
            "sell_price": price,
            "pnl_percent": round(pnl_pct, 2),
            "highest": pos["highest"],
            "trailing_stop": config.LISTING_TRAILING_STOP_PERCENT,
            "sell_time": utc_now(),
        })
        log.info("SOLD %s @ %s | pnl=%.2f%% (highest=%.8f, trailing=%d%%)",
                 symbol, price, pnl_pct, pos["highest"], config.LISTING_TRAILING_STOP_PERCENT)
        self._save()

    def manage_positions(self):
        for symbol in list(self.state["positions"]):
            pos = self.state["positions"][symbol]
            price = self._price(symbol)
            if not price or price <= 0:
                continue
            if price > pos["highest"]:
                pos["highest"] = price
            drop = (pos["highest"] - price) / pos["highest"] * 100
            if drop >= config.LISTING_TRAILING_STOP_PERCENT:
                log.info("TRAILING STOP hit %s: price=%.8f high=%.8f drop=%.1f%%", symbol, price, pos["highest"], drop)
                self._sell(symbol, price)
            else:
                log.info("WATCH %s price=%.8f high=%.8f drop=%.1f%%", symbol, price, pos["highest"], drop)
        self._save()

    def check_new_markets(self):
        prev = set(self.state.get("known", []))
        cur = self._fetch_symbols()
        if not cur:
            return
        self.state["known"] = list(cur)
        new_symbols = cur - prev
        if not new_symbols:
            return
        has_announcements = bool(self.state.get("announced"))
        for symbol in sorted(new_symbols):
            base = symbol.split("/")[0]
            announced = base in self.state.get("announced", {})
            if not announced and not config.LISTING_BUY_UNANNOUNCED and has_announcements:
                log.info("NEW PAIR (not in announcements, skipped): %s", symbol)
                continue
            log.info("NEW LISTING DETECTED: %s | announced=%s | auto_buy=%s",
                     symbol, announced, config.LISTING_AUTO_BUY)
            if config.LISTING_AUTO_BUY:
                self._maybe_buy(symbol)

    def run_forever(self):
        log.info("Listing hunter started | exchange=%s | budget=%s USDT | trailing_stop=%d%% | max_positions=%d | paper=%s",
                 config.LISTING_EXCHANGE, config.LISTING_BUDGET_USDT,
                 config.LISTING_TRAILING_STOP_PERCENT, config.LISTING_MAX_POSITIONS, self.paper)
        last_announce = 0.0
        last_market = time.time()
        while True:
            try:
                now = time.time()
                if now - last_announce >= config.LISTING_ANNOUNCE_CHECK_SECONDS:
                    self.check_announcements()
                    last_announce = now
                if now - last_market >= config.LISTING_MARKET_CHECK_SECONDS:
                    self.check_new_markets()
                    last_market = now
                if self.state["positions"]:
                    self.manage_positions()
                else:
                    log.info("no open positions, waiting...")
            except Exception as exc:
                log.error("loop error: %s", exc)
            time.sleep(config.LISTING_PRICE_CHECK_SECONDS)


def run_listing():
    import ccxt
    exchange_class = getattr(ccxt, config.LISTING_EXCHANGE)
    creds = config.API_KEYS.get(config.LISTING_EXCHANGE, {})
    exchange = exchange_class({
        "apiKey": creds.get("apiKey", ""),
        "secret": creds.get("secret", ""),
        "enableRateLimit": True,
        "timeout": 15000,
    })
    try:
        exchange.load_markets()
    except Exception as exc:
        log.warning("load_markets failed: %s", exc)
    hunter = ListingHunter(exchange)
    hunter.run_forever()

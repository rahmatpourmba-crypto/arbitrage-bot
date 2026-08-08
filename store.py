import copy
import json
import threading
import time

import config

_lock = threading.RLock()
_state = {
    "status": "starting",
    "started_at": None,
    "last_scan": None,
    "symbols": [],
    "exchanges": [],
    "market": {},
    "spreads": {},
    "opportunities": [],
    "trades": [],
    "balances": {},
    "pnl": {"realized_usdt": 0.0, "trades_count": 0},
}


def _load_persisted():
    try:
        with open(config.STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("balances"):
            _state["balances"] = data["balances"]
        if data.get("trades"):
            _state["trades"] = data["trades"]
        if data.get("pnl"):
            _state["pnl"] = data["pnl"]
    except (OSError, ValueError):
        pass


def init(symbols, exchanges):
    with _lock:
        _load_persisted()
        _state["symbols"] = list(symbols)
        _state["exchanges"] = list(exchanges)
        _state["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _state["status"] = "running"
    save()


def get():
    with _lock:
        return copy.deepcopy(_state)


def save():
    with _lock:
        data = {
            "balances": _state["balances"],
            "trades": _state["trades"],
            "pnl": _state["pnl"],
        }
    try:
        with open(config.STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def set_status(status):
    with _lock:
        _state["status"] = status


def set_last_scan():
    with _lock:
        _state["last_scan"] = time.strftime("%H:%M:%S")


def set_balances(balances):
    with _lock:
        _state["balances"] = balances
    save()


def record_market(symbol, books):
    with _lock:
        market = _state["market"].setdefault(symbol, {})
        bids = {}
        asks = {}
        for name, book in books.items():
            if not book:
                continue
            best_bid = book["bids"][0][0] if book.get("bids") else None
            best_ask = book["asks"][0][0] if book.get("asks") else None
            market[name] = {"bid": best_bid, "ask": best_ask}
            if best_bid is not None:
                bids[name] = best_bid
            if best_ask is not None:
                asks[name] = best_ask
        if bids and asks:
            buy_ex = min(asks, key=asks.get)
            sell_ex = max(bids, key=bids.get)
            spread_pct = (bids[sell_ex] - asks[buy_ex]) / asks[buy_ex] * 100
            _state["spreads"][symbol] = {
                "buy_exchange": buy_ex,
                "sell_exchange": sell_ex,
                "buy_price": asks[buy_ex],
                "sell_price": bids[sell_ex],
                "spread_pct": round(spread_pct, 3),
            }


def record_opportunity(opp):
    with _lock:
        _state["opportunities"].insert(0, opp)
        del _state["opportunities"][50:]


def record_trade(trade):
    with _lock:
        _state["trades"].append(trade)
        if len(_state["trades"]) > 500:
            _state["trades"] = _state["trades"][-500:]
    save()


def add_pnl(profit_usdt):
    with _lock:
        _state["pnl"]["realized_usdt"] = round(_state["pnl"]["realized_usdt"] + profit_usdt, 4)
        _state["pnl"]["trades_count"] += 1
    save()

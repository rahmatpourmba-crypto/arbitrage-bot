import csv
import os
from datetime import datetime, timezone

import config
import store


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class PaperTrader:
    def __init__(self, exchanges: dict):
        saved = store.get()["balances"]
        defaults = self._default_balances(list(exchanges))
        self.balances = saved if saved else defaults
        for name, bal in self.balances.items():
            for key, value in defaults.get(name, {}).items():
                bal.setdefault(key, value)
        self.trades = []
        store.set_balances(self.balances)

    def _default_balances(self, names):
        balances = {}
        for name in names:
            balances[name] = {"USDT": config.PAPER_START_USDT}
            for symbol in config.SYMBOLS:
                base = symbol.split("/")[0]
                balances[name][base] = config.PAPER_START_BASE
        return balances

    def balance(self, exchange_name: str, currency: str) -> float:
        return float(self.balances.get(exchange_name, {}).get(currency, 0.0))

    def transfer(self, from_exchange: str, to_exchange: str, currency: str, amount: float):
        bal_from = self.balances.get(from_exchange, {})
        bal_to = self.balances.get(to_exchange, {})
        if bal_from.get(currency, 0.0) >= amount:
            bal_from[currency] = bal_from.get(currency, 0.0) - amount
            bal_to[currency] = bal_to.get(currency, 0.0) + amount
            store.set_balances(self.balances)

    def buy(self, exchange_name: str, symbol: str, amount: float, price: float, fee_rate: float):
        base, quote = symbol.split("/")
        cost = amount * price * (1 + fee_rate)
        if self.balances[exchange_name][quote] < cost:
            return False
        self.balances[exchange_name][quote] -= cost
        self.balances[exchange_name][base] += amount
        self._record(exchange_name, symbol, "BUY", amount, price, fee_rate)
        return True

    def sell(self, exchange_name: str, symbol: str, amount: float, price: float, fee_rate: float):
        base, quote = symbol.split("/")
        if self.balances[exchange_name][base] < amount:
            return False
        revenue = amount * price * (1 - fee_rate)
        self.balances[exchange_name][base] -= amount
        self.balances[exchange_name][quote] += revenue
        self._record(exchange_name, symbol, "SELL", amount, price, fee_rate)
        return True

    def _record(self, exchange_name, symbol, side, amount, price, fee_rate):
        trade = {
            "time": utc_now(),
            "exchange": exchange_name,
            "symbol": symbol,
            "side": side,
            "amount": round(amount, 8),
            "price": round(price, 8),
            "fee": round(amount * price * fee_rate, 8),
        }
        self.trades.append(trade)
        store.record_trade(trade)
        store.set_balances(self.balances)
        print(f"[PAPER] {trade['time']} {exchange_name} {side} {trade['amount']} {symbol} @ {price}")
        self._write_csv()

    def _write_csv(self):
        file_exists = os.path.isfile(config.TRADES_FILE)
        with open(config.TRADES_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["time", "exchange", "symbol", "side", "amount", "price", "fee"])
            if not file_exists:
                writer.writeheader()
            writer.writerow(self.trades[-1])

    def summary(self, symbol: str):
        base = symbol.split("/")[0]
        print("---- PAPER BALANCES ----")
        for name, bal in self.balances.items():
            print(f"{name}: USDT={bal['USDT']:.2f}  {base}={bal[base]:.6f}")


class LiveTrader:
    def __init__(self, exchanges: dict):
        self.exchanges = exchanges

    def balance(self, exchange_name: str, currency: str) -> float:
        try:
            balance = self.exchanges[exchange_name].fetch_balance()
            return float(balance.get(currency, {}).get("free", 0.0))
        except Exception:
            return 1e18

    def buy(self, exchange_name: str, symbol: str, amount: float, price: float, fee_rate: float):
        exchange = self.exchanges[exchange_name]
        order = exchange.create_order(symbol, "limit", "buy", amount, price)
        print(f"[LIVE] {exchange_name} BUY {amount} {symbol} @ {price} -> {order.get('id')}")
        return order

    def sell(self, exchange_name: str, symbol: str, amount: float, price: float, fee_rate: float):
        exchange = self.exchanges[exchange_name]
        order = exchange.create_order(symbol, "limit", "sell", amount, price)
        print(f"[LIVE] {exchange_name} SELL {amount} {symbol} @ {price} -> {order.get('id')}")
        return order


def make_trader(exchanges: dict):
    if config.PAPER_TRADING:
        return PaperTrader(exchanges)
    return LiveTrader(exchanges)

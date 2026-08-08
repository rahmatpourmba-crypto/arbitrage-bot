import config
import store
from concurrent.futures import ThreadPoolExecutor, as_completed


def weighted_price(levels, target_notional):
    filled_notional = 0.0
    filled_volume = 0.0
    for level in levels:
        price, quantity = level[0], level[1]
        level_notional = price * quantity
        take = min(level_notional, target_notional - filled_notional)
        if take <= 0:
            break
        filled_notional += take
        filled_volume += take / price
    if filled_volume == 0:
        return None, 0.0
    return filled_notional / filled_volume, filled_notional


class Scanner:
    def __init__(self, exchanges: dict):
        self.exchanges = exchanges

    def _fetch_book(self, name: str, symbol: str):
        exchange = self.exchanges[name]
        try:
            return name, exchange.fetch_order_book(symbol, limit=config.ORDER_BOOK_LIMIT)
        except Exception:
            try:
                return name, exchange.fetch_order_book(symbol, limit=20)
            except Exception as exc:
                print(f"[{name}] fetch_order_book {symbol} failed: {exc}")
                return name, None

    def fetch_books(self, symbol: str) -> dict:
        books = {}
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(self._fetch_book, name, symbol) for name in self.exchanges]
            for future in as_completed(futures):
                name, book = future.result()
                if book:
                    books[name] = book
        return books

    def find_opportunity(self, symbol: str, books: dict):
        candidates = []
        for buy_ex, buy_book in books.items():
            for sell_ex, sell_book in books.items():
                if buy_ex == sell_ex:
                    continue
                if not buy_book.get("asks") or not sell_book.get("bids"):
                    continue
                avg_ask, ask_notional = weighted_price(buy_book["asks"], config.TRADE_SIZE_USDT)
                avg_bid, bid_notional = weighted_price(sell_book["bids"], config.TRADE_SIZE_USDT)
                if avg_ask is None or avg_bid is None:
                    continue
                if ask_notional < config.TRADE_SIZE_USDT or bid_notional < config.TRADE_SIZE_USDT:
                    continue
                fee_buy = config.taker_fee(buy_ex)
                fee_sell = config.taker_fee(sell_ex)
                cost = avg_ask * (1 + fee_buy)
                revenue = avg_bid * (1 - fee_sell)
                profit_percent = (revenue - cost) / cost * 100
                if profit_percent >= config.MIN_PROFIT_PERCENT:
                    candidates.append({
                        "symbol": symbol,
                        "buy_exchange": buy_ex,
                        "sell_exchange": sell_ex,
                        "buy_price": avg_ask,
                        "sell_price": avg_bid,
                        "buy_fee": fee_buy,
                        "sell_fee": fee_sell,
                        "profit_percent": profit_percent,
                    })
        if not candidates:
            return None
        return max(candidates, key=lambda c: c["profit_percent"])

    def _scan_symbol(self, symbol: str):
        books = self.fetch_books(symbol)
        store.record_market(symbol, books)
        return self.find_opportunity(symbol, books)

    def scan_all(self) -> list:
        opportunities = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(self._scan_symbol, symbol) for symbol in config.SYMBOLS]
            for future in as_completed(futures):
                opp = future.result()
                if opp:
                    opportunities.append(opp)
        return opportunities

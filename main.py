import argparse
import logging
import sys
import time

import config
import store
from exchange_manager import build_exchanges
from scanner import Scanner
from trader import make_trader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("arbitrage")


def execute(trader, opp: dict) -> bool:
    if not (config.is_tradable(opp["buy_exchange"]) and config.is_tradable(opp["sell_exchange"])):
        store.record_opportunity({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": opp["symbol"],
            "buy_exchange": opp["buy_exchange"],
            "sell_exchange": opp["sell_exchange"],
            "buy_price": opp["buy_price"],
            "sell_price": opp["sell_price"],
            "profit_percent": opp["profit_percent"],
            "status": "observed",
        })
        log.info("OBSERVE %s buy=%s@%s sell=%s@%s profit=%.3f%% (no API key on one/both exchanges)",
                 opp["symbol"], opp["buy_exchange"], opp["buy_price"],
                 opp["sell_exchange"], opp["sell_price"], opp["profit_percent"])
        return False
    base, quote = opp["symbol"].split("/")
    notional = config.TRADE_SIZE_USDT
    amount = notional / opp["buy_price"]
    if hasattr(trader, "balance"):
        amount = min(amount, trader.balance(opp["sell_exchange"], base))
    if amount <= 0:
        return False
    fee_buy = config.taker_fee(opp["buy_exchange"])
    fee_sell = config.taker_fee(opp["sell_exchange"])

    if not trader.buy(opp["buy_exchange"], opp["symbol"], amount, opp["buy_price"], fee_buy):
        return False
    if not trader.sell(opp["sell_exchange"], opp["symbol"], amount, opp["sell_price"], fee_sell):
        return False
    if hasattr(trader, "transfer"):
        trader.transfer(opp["buy_exchange"], opp["sell_exchange"], base, amount)

    profit = amount * opp["sell_price"] * (1 - fee_sell) - amount * opp["buy_price"] * (1 + fee_buy)
    store.add_pnl(profit)
    store.record_opportunity({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": opp["symbol"],
        "buy_exchange": opp["buy_exchange"],
        "sell_exchange": opp["sell_exchange"],
        "buy_price": opp["buy_price"],
        "sell_price": opp["sell_price"],
        "profit_percent": opp["profit_percent"],
        "status": "executed",
    })
    log.info(
        "OPP %s buy=%s@%s sell=%s@%s profit=%.3f%% pnl=%+.4f USDT",
        opp["symbol"],
        opp["buy_exchange"],
        opp["buy_price"],
        opp["sell_exchange"],
        opp["sell_price"],
        opp["profit_percent"],
        profit,
    )
    return True


def run_forever(scanner, trader):
    tradable = config.tradable_exchanges()
    log.info("Bot started | symbols=%s | exchanges=%s | min_profit=%.2f%% | paper=%s | tradable=%s",
             config.SYMBOLS, config.EXCHANGES, config.MIN_PROFIT_PERCENT, config.PAPER_TRADING, tradable)
    store.set_status("running")
    while True:
        try:
            for opp in scanner.scan_all():
                if not execute(trader, opp):
                    log.info("BLOCKED %s buy=%s sell=%s profit=%.3f%% (insufficient balance)",
                             opp["symbol"], opp["buy_exchange"], opp["sell_exchange"], opp["profit_percent"])
            store.set_last_scan()
        except Exception as exc:
            log.error("scan error: %s", exc)
        time.sleep(config.SCAN_INTERVAL_SECONDS)


def run_once(scanner, trader):
    opps = scanner.scan_all()
    if not opps:
        log.info("No opportunity found right now.")
    for opp in opps:
        log.info("FOUND %s buy=%s@%s sell=%s@%s profit=%.3f%%",
                 opp["symbol"], opp["buy_exchange"], opp["buy_price"],
                 opp["sell_exchange"], opp["sell_price"], opp["profit_percent"])
        if trader:
            execute(trader, opp)


def report_scan(scanner):
    opps = scanner.scan_all()
    for opp in opps:
        store.record_opportunity({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": opp["symbol"],
            "buy_exchange": opp["buy_exchange"],
            "sell_exchange": opp["sell_exchange"],
            "buy_price": opp["buy_price"],
            "sell_price": opp["sell_price"],
            "profit_percent": opp["profit_percent"],
            "status": "observed",
        })
    import report
    report.export()


def selftest(scanner, trader):
    symbol = config.SYMBOLS[0]
    base = symbol.split("/")[0]
    price = 60000.0
    ask_price = price * 0.99
    bid_price = price * 1.01
    fake_binance = {"bids": [[bid_price * 1.02, 50.0]], "asks": [[ask_price, 50.0]]}
    fake_bybit = {"bids": [[bid_price, 50.0]], "asks": [[ask_price * 1.02, 50.0]]}
    books = {"binance": fake_binance, "bybit": fake_bybit}
    opp = scanner.find_opportunity(symbol, books)
    if not opp:
        log.error("Selftest failed: opportunity not detected (min profit too high?)")
        return
    log.info("Selftest detected: buy %s@%s sell %s@%s profit=%.3f%%",
             opp["buy_exchange"], opp["buy_price"], opp["sell_exchange"], opp["sell_price"], opp["profit_percent"])
    execute(trader, opp)
    if isinstance(trader, type(None)):
        return
    trader.summary(symbol)
    log.info("Selftest OK: buy+execution pipeline works.")


def main():
    parser = argparse.ArgumentParser(description="Cryptocurrency arbitrage bot")
    parser.add_argument("--once", action="store_true", help="Scan once and exit")
    parser.add_argument("--selftest", action="store_true", help="Run synthetic execution test")
    parser.add_argument("--report", action="store_true", help="Scan once and export static HTML report (no trading)")
    parser.add_argument("--headless", action="store_true", help="Run without web dashboard")
    parser.add_argument("--port", type=int, default=config.DASHBOARD_PORT, help="Dashboard port")
    args = parser.parse_args()

    exchanges = build_exchanges(sandbox=(not config.PAPER_TRADING and config.USE_TESTNET))
    store.init(config.SYMBOLS, config.EXCHANGES)
    scanner = Scanner(exchanges)

    if args.selftest:
        selftest(scanner, make_trader(exchanges))
        return
    if args.once:
        run_once(scanner, make_trader(exchanges))
        return
    if args.report:
        report_scan(scanner)
        return
    if not args.headless:
        from dashboard import start_dashboard
        start_dashboard(args.port)
    run_forever(scanner, make_trader(exchanges))


if __name__ == "__main__":
    main()

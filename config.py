import os


EXCHANGES = [
    "binance",
    "bybit",
    "okx",
    "bitget",
    "mexc",
    "gate",
    "bingx",
    "lbank",
    "coinex",
    "phemex",
    "whitebit",
    "htx",
    "kraken",
    "coinbase",
    "poloniex",
    "cryptocom",
    "bitrue",
    "kucoin",
]

SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "TRX/USDT",
    "LTC/USDT",
    "LINK/USDT",
    "BCH/USDT",
    "NEAR/USDT",
    "PEPE/USDT",
]

TAKER_FEES = {
    "binance": 0.001,
    "bybit": 0.001,
    "okx": 0.001,
    "bitget": 0.001,
    "mexc": 0.0005,
    "gate": 0.001,
    "bingx": 0.0005,
    "lbank": 0.001,
    "coinex": 0.001,
    "phemex": 0.001,
    "whitebit": 0.001,
    "htx": 0.002,
    "kraken": 0.0026,
    "coinbase": 0.006,
    "poloniex": 0.0015,
    "cryptocom": 0.004,
    "bitrue": 0.001,
    "kucoin": 0.001,
}

DEFAULT_TAKER_FEE = 0.001

TRADE_SIZE_USDT = 100.0

MIN_PROFIT_PERCENT = 0.05

SCAN_INTERVAL_SECONDS = 5.0

ORDER_BOOK_LIMIT = 50

PAPER_TRADING = True

PAPER_START_USDT = 10000.0
PAPER_START_BASE = 100.0

API_KEYS = {
    "binance": {"apiKey": os.getenv("BINANCE_API_KEY", ""), "secret": os.getenv("BINANCE_SECRET", "")},
    "bybit": {"apiKey": os.getenv("BYBIT_API_KEY", ""), "secret": os.getenv("BYBIT_SECRET", "")},
    "okx": {"apiKey": os.getenv("OKX_API_KEY", ""), "secret": os.getenv("OKX_SECRET", "")},
    "bitget": {"apiKey": os.getenv("BITGET_API_KEY", ""), "secret": os.getenv("BITGET_SECRET", "")},
    "mexc": {"apiKey": os.getenv("MEXC_API_KEY", ""), "secret": os.getenv("MEXC_SECRET", "")},
    "gate": {"apiKey": os.getenv("GATE_API_KEY", ""), "secret": os.getenv("GATE_SECRET", "")},
    "bingx": {"apiKey": os.getenv("BINGX_API_KEY", ""), "secret": os.getenv("BINGX_SECRET", "")},
    "lbank": {"apiKey": os.getenv("LBANK_API_KEY", ""), "secret": os.getenv("LBANK_SECRET", "")},
    "coinex": {"apiKey": os.getenv("COINEX_API_KEY", ""), "secret": os.getenv("COINEX_SECRET", "")},
    "phemex": {"apiKey": os.getenv("PHEMEX_API_KEY", ""), "secret": os.getenv("PHEMEX_SECRET", "")},
    "whitebit": {"apiKey": os.getenv("WHITEBIT_API_KEY", ""), "secret": os.getenv("WHITEBIT_SECRET", "")},
    "htx": {"apiKey": os.getenv("HTX_API_KEY", ""), "secret": os.getenv("HTX_SECRET", "")},
    "kraken": {"apiKey": os.getenv("KRAKEN_API_KEY", ""), "secret": os.getenv("KRAKEN_SECRET", "")},
    "coinbase": {"apiKey": os.getenv("COINBASE_API_KEY", ""), "secret": os.getenv("COINBASE_SECRET", "")},
    "poloniex": {"apiKey": os.getenv("POLONIEX_API_KEY", ""), "secret": os.getenv("POLONIEX_SECRET", "")},
    "cryptocom": {"apiKey": os.getenv("CRYPTOCOM_API_KEY", ""), "secret": os.getenv("CRYPTOCOM_SECRET", "")},
    "bitrue": {"apiKey": os.getenv("BITRUE_API_KEY", ""), "secret": os.getenv("BITRUE_SECRET", "")},
    "kucoin": {"apiKey": os.getenv("KUCOIN_API_KEY", ""), "secret": os.getenv("KUCOIN_SECRET", "")},
}

USE_TESTNET = True

LOG_FILE = "arbitrage.log"
TRADES_FILE = "trades.csv"
STATE_FILE = "state.json"

DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8080


def taker_fee(exchange_name: str) -> float:
    return TAKER_FEES.get(exchange_name, DEFAULT_TAKER_FEE)

import ccxt
from concurrent.futures import ThreadPoolExecutor, as_completed

import config


def _build_one(name: str, sandbox: bool):
    exchange_class = getattr(ccxt, name)
    creds = config.API_KEYS.get(name, {})
    exchange = exchange_class({
        "apiKey": creds.get("apiKey", ""),
        "secret": creds.get("secret", ""),
        "enableRateLimit": True,
        "timeout": 10000,
    })
    if sandbox:
        try:
            exchange.set_sandbox_mode(True)
        except Exception:
            pass
    try:
        exchange.load_markets()
    except Exception as exc:
        print(f"[{name}] load_markets failed: {exc}")
    return name, exchange


def build_exchanges(sandbox: bool = False) -> dict:
    exchanges = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_build_one, name, sandbox) for name in config.EXCHANGES]
        for future in as_completed(futures):
            name, exchange = future.result()
            exchanges[name] = exchange
    return exchanges

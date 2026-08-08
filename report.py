import html
import os

import config
import store


def _render(state) -> str:
    rows = []

    opp_rows = ""
    for o in state.get("opportunities", [])[:50]:
        status = "معامله شد" if o.get("status") == "executed" else "فقط مشاهده"
        opp_rows += (
            "<tr><td>{time}</td><td>{symbol}</td><td>{buy} @ {bp}</td>"
            "<td>{sell} @ {sp}</td><td class=\"pos\">{pp}</td><td>{status}</td></tr>"
        ).format(
            time=html.escape(str(o.get("time", ""))),
            symbol=html.escape(str(o.get("symbol", ""))),
            buy=html.escape(str(o.get("buy_exchange", ""))),
            bp=html.escape(str(o.get("buy_price", ""))),
            sell=html.escape(str(o.get("sell_exchange", ""))),
            sp=html.escape(str(o.get("sell_price", ""))),
            pp=html.escape(str(o.get("profit_percent", ""))),
            status=html.escape(status),
        )
    rows.append('<div class="section"><h3>فرصت‌های اخیر</h3><table>'
                '<thead><tr><th>زمان</th><th>جفت‌ارز</th><th>خرید از</th>'
                '<th>فروش به</th><th>سود ٪</th><th>وضعیت</th></tr></thead><tbody>')
    rows.append(opp_rows or '<tr><td colspan="6" class="muted">فرصتی ثبت نشده</td></tr>')
    rows.append('</tbody></table></div>')

    spread_rows = ""
    for sym, sp in state.get("spreads", {}).items():
        cls = "pos" if sp.get("spread_pct", 0) >= 0 else "neg"
        spread_rows += (
            "<tr><td>{sym}</td><td>{buy} @ {bp}</td><td>{sell} @ {sp}</td>"
            "<td class=\"{cls}\">{pct}</td></tr>"
        ).format(
            sym=html.escape(sym),
            buy=html.escape(str(sp.get("buy_exchange", ""))),
            bp=html.escape(str(sp.get("buy_price", ""))),
            sell=html.escape(str(sp.get("sell_exchange", ""))),
            sp=html.escape(str(sp.get("sell_price", ""))),
            cls=cls,
            pct=html.escape(str(sp.get("spread_pct", ""))),
        )
    rows.append('<div class="section"><h3>اسپرد زنده بازار</h3><table>'
                '<thead><tr><th>جفت‌ارز</th><th>ارزان‌ترین فروشنده (ask)</th>'
                '<th>گران‌ترین خریدار (bid)</th><th>اسپرد ٪</th></tr></thead><tbody>')
    rows.append(spread_rows or '<tr><td colspan="4" class="muted">در حال اسکن...</td></tr>')
    rows.append('</tbody></table></div>')

    trade_rows = ""
    for t in reversed(state.get("trades", [])[-20:]):
        trade_rows += (
            "<tr><td>{time}</td><td>{ex}</td><td>{symbol}</td><td>{side}</td>"
            "<td>{amount}</td><td>{price}</td></tr>"
        ).format(
            time=html.escape(str(t.get("time", ""))),
            ex=html.escape(str(t.get("exchange", ""))),
            symbol=html.escape(str(t.get("symbol", ""))),
            side=html.escape(str(t.get("side", ""))),
            amount=html.escape(str(t.get("amount", ""))),
            price=html.escape(str(t.get("price", ""))),
        )
    rows.append('<div class="section"><h3>معاملات اخیر</h3><table>'
                '<thead><tr><th>زمان</th><th>صرافی</th><th>جفت‌ارز</th><th>طرف</th>'
                '<th>حجم</th><th>قیمت</th></tr></thead><tbody>')
    rows.append(trade_rows or '<tr><td colspan="6" class="muted">معامله‌ای ثبت نشده</td></tr>')
    rows.append('</tbody></table></div>')

    bal_rows = ""
    for ex, bal in state.get("balances", {}).items():
        bal_rows += "<tr><td>{ex}</td><td>{usdt}</td></tr>".format(
            ex=html.escape(ex),
            usdt=html.escape(f"{float(bal.get('USDT') or 0):.2f}"),
        )
    rows.append('<div class="section"><h3>بیلنس تستی (Paper)</h3><table>'
                '<thead><tr><th>صرافی</th><th>USDT</th></tr></thead><tbody>')
    rows.append(bal_rows or '<tr><td colspan="2" class="muted">—</td></tr>')
    rows.append('</tbody></table></div>')

    pnl = state.get("pnl", {})
    pnl_cls = "pos" if pnl.get("realized_usdt", 0) >= 0 else "neg"

    return """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>داشبورد آربیتراژ</title>
<style>
  body {{ font-family: Vazirmatn, Tahoma, sans-serif; background:#0f1420; color:#e6edf3; margin:0; padding:16px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }}
  .card {{ background:#161d2b; border:1px solid #2a3550; border-radius:10px; padding:12px 18px; min-width:150px; }}
  .card .label {{ font-size:12px; color:#8b98b3; }}
  .card .value {{ font-size:22px; font-weight:bold; margin-top:4px; }}
  .ok {{ color:#3fb68b; }} .bad {{ color:#e5534b; }}
  table {{ width:100%; border-collapse:collapse; background:#161d2b; border-radius:10px; overflow:hidden; margin-top:8px; }}
  th, td {{ padding:8px 10px; border-bottom:1px solid #232c40; text-align:right; font-size:13px; }}
  th {{ background:#1b2436; color:#8b98b3; font-weight:normal; }}
  .section {{ margin-top:24px; }}
  .pos {{ color:#3fb68b; }} .neg {{ color:#e5534b; }}
  .muted {{ color:#8b98b3; font-size:12px; }}
</style>
</head>
<body>
  <h1>داشبورد آربیتراژ بین صرافی‌ها</h1>
  <div class="muted">به‌روزرسانی خودکار توسط GitHub Actions | آخرین اسکن: {last_scan}</div>

  <div class="cards">
    <div class="card"><div class="label">وضعیت</div><div class="value ok">{status}</div></div>
    <div class="card"><div class="label">آخرین اسکن</div><div class="value">{last_scan}</div></div>
    <div class="card"><div class="label">سود تحقق‌یافته (USDT)</div><div class="value {pnl_cls}">{pnl_usdt}</div></div>
    <div class="card"><div class="label">تعداد معاملات</div><div class="value">{trades_count}</div></div>
  </div>

  <div class="muted">صرافی‌ها: {exchanges} | ارزها: {symbols}</div>
{body}
</body>
</html>""".format(
        last_scan=html.escape(str(state.get("last_scan") or "—")),
        status=html.escape(str(state.get("status") or "—")),
        pnl_cls=pnl_cls,
        pnl_usdt=f"{pnl.get('realized_usdt', 0.0):.2f}",
        trades_count=pnl.get("trades_count", 0),
        exchanges=", ".join(state.get("exchanges", [])),
        symbols=", ".join(state.get("symbols", [])),
        body="\n".join(rows),
    )


def export(out_dir: str = "report"):
    state = store.get()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_render(state))
    print(f"Static report written to {path}")
    return path


if __name__ == "__main__":
    store.init(config.SYMBOLS, config.EXCHANGES)
    export()

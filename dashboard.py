import threading

from flask import Flask, jsonify

import config
import store

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>داشبورد آربیتراژ</title>
<style>
  body { font-family: Vazirmatn, Tahoma, sans-serif; background:#0f1420; color:#e6edf3; margin:0; padding:16px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .cards { display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }
  .card { background:#161d2b; border:1px solid #2a3550; border-radius:10px; padding:12px 18px; min-width:150px; }
  .card .label { font-size:12px; color:#8b98b3; }
  .card .value { font-size:22px; font-weight:bold; margin-top:4px; }
  .ok { color:#3fb68b; } .bad { color:#e5534b; }
  table { width:100%; border-collapse:collapse; background:#161d2b; border-radius:10px; overflow:hidden; margin-top:8px; }
  th, td { padding:8px 10px; border-bottom:1px solid #232c40; text-align:right; font-size:13px; }
  th { background:#1b2436; color:#8b98b3; font-weight:normal; }
  .section { margin-top:24px; }
  .pos { color:#3fb68b; } .neg { color:#e5534b; }
  details { background:#161d2b; border:1px solid #2a3550; border-radius:10px; padding:10px 14px; margin-top:8px; }
  summary { cursor:pointer; color:#c9d4e6; font-weight:bold; }
  .muted { color:#8b98b3; font-size:12px; }
</style>
</head>
<body>
  <h1>داشبورد آربیتراژ بین صرافی‌ها</h1>
  <div class="muted" id="meta">در حال بارگذاری...</div>

  <div class="cards">
    <div class="card"><div class="label">وضعیت</div><div class="value ok" id="status">...</div></div>
    <div class="card"><div class="label">آخرین اسکن</div><div class="value" id="last_scan">...</div></div>
    <div class="card"><div class="label">سود تحقق‌یافته (USDT)</div><div class="value" id="pnl">...</div></div>
    <div class="card"><div class="label">تعداد معاملات</div><div class="value" id="trades_count">...</div></div>
  </div>

  <div class="section"><h3>فرصت‌های اخیر</h3>
    <table><thead><tr><th>زمان</th><th>جفت‌ارز</th><th>خرید از</th><th>فروش به</th><th>سود ٪</th><th>وضعیت</th></tr></thead>
    <tbody id="opp_body"><tr><td colspan="6" class="muted">فرصتی ثبت نشده</td></tr></tbody></table>
  </div>

  <div class="section"><h3>اسپرد زنده بازار</h3>
    <table><thead><tr><th>جفت‌ارز</th><th>ارزان‌ترین فروشنده (ask)</th><th>گران‌ترین خریدار (bid)</th><th>اسپرد ٪</th></tr></thead>
    <tbody id="spread_body"><tr><td colspan="4" class="muted">در حال اسکن...</td></tr></tbody></table>
  </div>

  <div class="section"><h3>معاملات اخیر</h3>
    <table><thead><tr><th>زمان</th><th>صرافی</th><th>جفت‌ارز</th><th>طرف</th><th>حجم</th><th>قیمت</th></tr></thead>
    <tbody id="trade_body"><tr><td colspan="6" class="muted">معامله‌ای ثبت نشده</td></tr></tbody></table>
  </div>

  <div class="section"><h3>بیلنس تستی (Paper)</h3>
    <table><thead><tr><th>صرافی</th><th>USDT</th></tr></thead>
    <tbody id="bal_body"></tbody></table>
  </div>

<script>
async function refresh() {
  const s = await fetch('/api/state').then(r => r.json());
  document.getElementById('status').textContent = s.status;
  document.getElementById('last_scan').textContent = s.last_scan || '—';
  const pnl = document.getElementById('pnl');
  pnl.textContent = s.pnl.realized_usdt.toFixed(2);
  pnl.className = 'value ' + (s.pnl.realized_usdt >= 0 ? 'pos' : 'neg');
  document.getElementById('trades_count').textContent = s.pnl.trades_count;
  document.getElementById('meta').textContent =
    'صرافی‌ها: ' + s.exchanges.join(', ') + ' | ارزها: ' + s.symbols.join(', ');

  const ob = document.getElementById('opp_body');
  if (s.opportunities.length) {
    ob.innerHTML = s.opportunities.map(o =>
      `<tr><td>${o.time||''}</td><td>${o.symbol}</td><td>${o.buy_exchange} @ ${o.buy_price}</td>` +
      `<td>${o.sell_exchange} @ ${o.sell_price}</td><td class="pos">${o.profit_percent.toFixed(3)}</td>` +
      `<td>${o.status==='executed' ? 'معامله شد' : 'فقط مشاهده'}</td></tr>`
    ).join('');
  }

  const sb = document.getElementById('spread_body');
  const spreadRows = Object.entries(s.spreads).map(([sym, sp]) =>
    `<tr><td>${sym}</td><td>${sp.buy_exchange} @ ${sp.buy_price}</td>` +
    `<td>${sp.sell_exchange} @ ${sp.sell_price}</td>` +
    `<td class="${sp.spread_pct>=0?'pos':'neg'}">${sp.spread_pct.toFixed(3)}</td></tr>`
  );
  sb.innerHTML = spreadRows.join('') || '<tr><td colspan="4" class="muted">در حال اسکن...</td></tr>';

  const tb = document.getElementById('trade_body');
  if (s.trades.length) {
    tb.innerHTML = s.trades.slice(-20).reverse().map(t =>
      `<tr><td>${t.time}</td><td>${t.exchange}</td><td>${t.symbol}</td>` +
      `<td>${t.side}</td><td>${t.amount}</td><td>${t.price}</td></tr>`
    ).join('');
  }

  const bb = document.getElementById('bal_body');
  const balRows = Object.entries(s.balances).map(([ex, bal]) =>
    `<tr><td>${ex}</td><td>${Number(bal.USDT || 0).toFixed(2)}</td></tr>`
  );
  bb.innerHTML = balRows.join('') || '<tr><td colspan="2" class="muted">—</td></tr>';
}
setInterval(refresh, 3000);
refresh();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


@app.route("/api/state")
def api_state():
    return jsonify(store.get())


def start_dashboard(port=None):
    port = port or config.DASHBOARD_PORT
    thread = threading.Thread(
        target=lambda: app.run(host=config.DASHBOARD_HOST, port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    thread.start()
    print(f"Dashboard running at http://127.0.0.1:{port}")

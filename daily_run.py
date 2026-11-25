"""每日自動選股 + 模擬交易 + 通知（本機版，不需要 Google Sheet）

流程：
1. 強制更新今天的股價（快取只保留到今天）
2. 用指定策略（預設 default）跑 watchlist.csv
3. 結果存到 data/signals/<交易日>.json 與 data/signals/latest.json
4. 推進模擬帳戶（data/paper/account.json）
5. 有設定 Discord Webhook 就推播

執行: uv run python daily_run.py [--force] [--strategy default]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from stock_strategies import config as _config

# 每日排程要拿「今天」的收盤資料：日 K 快取只在資料日期 = 今天時才算新鮮
_config.CACHE_FRESH_DAYS["daily"] = 0

from api.services.runs import screen  # noqa: E402
from stock_strategies import loader, paper  # noqa: E402
from stock_strategies.datasources import get_index_history  # noqa: E402

ROOT = Path(__file__).resolve().parent
SIGNAL_DIR = ROOT / "data" / "signals"


def _configured(name: str) -> bool:
    value = os.environ.get(name, "")
    return bool(value) and "your_" not in value


def send_discord(text: str) -> bool:
    """用 Discord Webhook 送訊息（單則上限 2000 字，超過自動分段）"""
    import requests
    url = os.environ["DISCORD_WEBHOOK_URL"].strip()
    chunks, buf = [], ""
    for line in text.splitlines():
        if len(buf) + len(line) + 1 > 1900:
            chunks.append(buf)
            buf = ""
        buf += line + "\n"
    if buf:
        chunks.append(buf)
    ok = True
    for chunk in chunks:
        try:
            r = requests.post(url, json={"content": chunk, "username": "台股選股機器人"}, timeout=15)
            if r.status_code >= 300:
                print(f"Discord 送出失敗: {r.status_code} {r.text[:200]}", file=sys.stderr)
                ok = False
        except Exception as exc:
            print(f"Discord 送出失敗: {exc}", file=sys.stderr)
            ok = False
    return ok


def _fmt_money(v: float) -> str:
    return f"{v:,.0f}"


def build_message(trade_date: str, result: dict, events: list[dict], account_summary: dict) -> str:
    s = result["summary"]
    lines = [f"📊 每日選股 {trade_date}（{result['strategy']['name']}）",
             f"掃描 {s['total']} 檔｜BUY {s['buy']}｜WATCH {s['watch']}｜SKIP {s['skip']}｜錯誤 {s['error']}",
             result["market"].get("note", ""), ""]
    buys = [r for r in result["results"] if r.get("action") == "BUY"]
    watches = [r for r in result["results"] if r.get("action") == "WATCH"][:8]
    if buys:
        lines.append("🟢 BUY")
        for r in buys:
            lines.append(f"• {r['stock_id']} {r.get('name','')} {r.get('signal_score')}分｜"
                         f"收 {r.get('entry_price')} 損 {r.get('stop_loss_price')} 標 {r.get('target_price')}")
        lines.append("")
    if watches:
        lines.append("🟡 WATCH（前 8 名）")
        for r in watches:
            lines.append(f"• {r['stock_id']} {r.get('name','')} {r.get('signal_score')}分")
        lines.append("")
    if events:
        lines.append("🤖 模擬交易")
        for e in events:
            if e["type"] == "BUY":
                lines.append(f"• 買進 {e['stock_id']} {e['name']} {e['shares']} 股 @ {e['price']}")
            elif e["type"] == "SELL":
                lines.append(f"• 賣出 {e['stock_id']} {e['name']} @ {e['exit_price']}（{e['reason']}）"
                             f" 損益 {_fmt_money(e['pnl'])}（{e['return_pct']:+.2f}%）")
            elif e["type"] == "ORDER":
                lines.append(f"• 掛單 {e['stock_id']} {e['name']}：{e['note']}")
            elif e["type"] == "SKIP_BUY":
                lines.append(f"• 未買 {e['stock_id']} {e['name']}：{e['reason']}")
        lines.append("")
    a = account_summary
    lines.append(f"💼 模擬帳戶 {_fmt_money(a['equity'])}（{a['return_pct']:+.2f}%）｜"
                 f"現金 {_fmt_money(a['cash'])}｜已平倉 {a['trade_count']} 筆")
    lines.append("※ 模擬交易，非投資建議")
    return "\n".join(lines)


class _Tee:
    """同時輸出到畫面與 data/logs/daily.log（UTF-8、即時寫入）"""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, text):
        try:
            self.stream.write(text)
            self.stream.flush()
        except Exception:
            pass
        self.log.write(text)
        self.log.flush()
        return len(text)

    def flush(self):
        try:
            self.stream.flush()
        except Exception:
            pass
        self.log.flush()


def _setup_log() -> None:
    log_dir = ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "daily.log", "a", encoding="utf-8")
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        setattr(sys, name, _Tee(stream, log))


def main() -> int:
    _setup_log()
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="同一交易日已跑過也重跑")
    parser.add_argument("--strategy", default=os.environ.get("DAILY_STRATEGY", "default"))
    args = parser.parse_args()

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 每日選股開始")
    if not _configured("FINMIND_TOKEN"):
        print("❌ .env 沒有 FINMIND_TOKEN", file=sys.stderr)
        return 1

    taiex = get_index_history("TAIEX")
    if taiex.empty:
        print("❌ 取不到加權指數資料，稍後再試", file=sys.stderr)
        return 1
    trade_date = str(taiex["date"].iloc[-1])[:10]
    today = datetime.now().strftime("%Y-%m-%d")
    if trade_date != today:
        print(f"⚠️ 最新交易日是 {trade_date}，不是今天（{today}）：可能休市或資料尚未更新")

    out = SIGNAL_DIR / f"{trade_date}.json"
    if out.exists() and not args.force:
        print(f"✅ {trade_date} 已經跑過，略過（要重跑請加 --force）")
        return 0

    strategy = loader.get_strategy(args.strategy)
    if not strategy:
        print(f"❌ 找不到策略 {args.strategy}", file=sys.stderr)
        return 1

    shown = set()

    def progress(completed=0, total=0, current=None):
        if current and current not in shown:
            shown.add(current)
            print(f"  [{len(shown)}/{total}] {current}")

    result = screen(strategy, progress=progress, delay=0.3)
    payload = {"trade_date": trade_date, "run_at": datetime.now().isoformat(timespec="seconds"), **result}

    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    out.write_text(text, encoding="utf-8")
    (SIGNAL_DIR / "latest.json").write_text(text, encoding="utf-8")
    s = result["summary"]
    print(f"✅ 選股完成：BUY {s['buy']} / WATCH {s['watch']} / SKIP {s['skip']} / 錯誤 {s['error']}")

    account = paper.load_account()
    events = paper.process_day(account, trade_date, result["results"], strategy["params"])
    paper.save_account(account)
    acct = paper.summary(account)
    for e in events:
        print(f"  🤖 {e}")
    print(f"💼 模擬帳戶 {acct['equity']:,.0f}（{acct['return_pct']:+.2f}%）")

    if _configured("DISCORD_WEBHOOK_URL"):
        ok = send_discord(build_message(trade_date, result, events, acct))
        print("📨 Discord 已送出" if ok else "⚠️ Discord 送出失敗")
    else:
        print("（未設定 Discord，略過通知）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

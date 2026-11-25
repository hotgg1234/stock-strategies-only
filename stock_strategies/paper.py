"""模擬交易（紙上交易）帳戶。

規則：
- 收盤後的 BUY 訊號先變成「待成交」，下一個交易日用開盤價買進（與回測一致，不偷看未來）。
- 部位大小 = 初始資金 × 策略建議部位 %，可零股，現金不夠就買到現金為止。
- 每天用日 K 檢查：跌破停損 → 停損價出場（跳空低開則用開盤價）；
  觸及停利 → 停利價出場（跳空高開用開盤價）；同一天兩者都碰到時保守當作停損；
  持有滿 hold_days 個交易日 → 收盤價出場。
- 扣手續費 0.1425%（最低 20 元）、賣出證交稅（股票 0.3%、ETF 0.1%）。
- 狀態存在 data/paper/account.json，重複執行同一天不會重複下單。
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from .data import get_price_history

ROOT = Path(__file__).resolve().parent.parent
ACCOUNT_PATH = Path(os.environ.get("PAPER_ACCOUNT_PATH", ROOT / "data" / "paper" / "account.json"))

INITIAL_CASH = float(os.environ.get("PAPER_INITIAL_CASH", 1_000_000))
FEE_RATE = 0.001425
FEE_DISCOUNT = float(os.environ.get("PAPER_FEE_DISCOUNT", 1.0))
MIN_FEE = 20.0
TAX_STOCK = 0.003
TAX_ETF = 0.001


def _is_etf(stock_id: str) -> bool:
    return str(stock_id).startswith("00")


def buy_fee(amount: float) -> float:
    return round(max(MIN_FEE, amount * FEE_RATE * FEE_DISCOUNT), 0)


def sell_cost(stock_id: str, amount: float) -> float:
    tax = amount * (TAX_ETF if _is_etf(stock_id) else TAX_STOCK)
    return round(max(MIN_FEE, amount * FEE_RATE * FEE_DISCOUNT) + tax, 0)


def new_account(initial_cash: float = INITIAL_CASH) -> dict:
    return {
        "initial_cash": initial_cash,
        "cash": initial_cash,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "positions": [],
        "pending": [],
        "trades": [],
        "equity_history": [],
        "events": [],
    }


def load_account(path: Path = ACCOUNT_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return new_account()


def save_account(account: dict, path: Path = ACCOUNT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(account, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _bars(stock_id: str, price_loader) -> pd.DataFrame:
    df = price_loader(stock_id)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df[["date", "open", "high", "low", "close"]].dropna().sort_values("date").reset_index(drop=True)


def _close_position(account: dict, pos: dict, date: str, price: float, reason: str, events: list) -> None:
    amount = price * pos["shares"]
    cost = sell_cost(pos["stock_id"], amount)
    proceeds = amount - cost
    account["cash"] = round(account["cash"] + proceeds, 0)
    pnl = proceeds - pos["cost_basis"]
    trade = {
        "stock_id": pos["stock_id"], "name": pos.get("name", ""),
        "shares": pos["shares"],
        "entry_date": pos["entry_date"], "entry_price": pos["entry_price"],
        "exit_date": date, "exit_price": round(price, 2),
        "reason": reason, "days_held": pos["days_held"],
        "pnl": round(pnl, 0),
        "return_pct": round(pnl / pos["cost_basis"] * 100, 2) if pos["cost_basis"] else 0.0,
    }
    account["trades"].append(trade)
    events.append({"type": "SELL", **trade})


def process_day(account: dict, as_of: str, results: list[dict], params: dict,
                price_loader=None) -> list[dict]:
    """推進模擬帳戶到 as_of（含），並把今天的 BUY 訊號加入待成交。回傳今天發生的事件。"""
    price_loader = price_loader or (lambda sid: get_price_history(sid, 1))
    events: list[dict] = []
    cache: dict[str, pd.DataFrame] = {}

    def bars(sid):
        if sid not in cache:
            cache[sid] = _bars(sid, price_loader)
        return cache[sid]

    # 1) 待成交 → 用訊號日之後第一根 K 棒的開盤價買進
    still_pending = []
    for order in account["pending"]:
        df = bars(order["stock_id"])
        nxt = df[(df["date"] > order["signal_date"]) & (df["date"] <= as_of)]
        if nxt.empty:
            still_pending.append(order)
            continue
        bar = nxt.iloc[0]
        price = float(bar["open"])
        budget = min(order["budget"], account["cash"])
        shares = int(math.floor(budget / (price * (1 + FEE_RATE * FEE_DISCOUNT))))
        if shares <= 0:
            events.append({"type": "SKIP_BUY", "stock_id": order["stock_id"], "name": order.get("name", ""),
                           "date": bar["date"], "reason": "現金不足"})
            continue
        amount = price * shares
        fee = buy_fee(amount)
        if amount + fee > account["cash"]:
            shares -= int(math.ceil(fee / price))
            amount = price * shares
            fee = buy_fee(amount)
        if shares <= 0:
            continue
        account["cash"] = round(account["cash"] - amount - fee, 0)
        pos = {
            "stock_id": order["stock_id"], "name": order.get("name", ""),
            "shares": shares, "entry_date": bar["date"], "entry_price": round(price, 2),
            "cost_basis": round(amount + fee, 0),
            "stop_price": round(price * (1 - order["stop_loss"]), 2),
            "target_price": round(price * (1 + order["target_return"]), 2),
            "hold_days": int(order["hold_days"]), "days_held": 0,
            "last_checked": None, "last_close": round(price, 2),
            "signal_date": order["signal_date"], "signal_score": order.get("signal_score"),
        }
        account["positions"].append(pos)
        events.append({"type": "BUY", "stock_id": pos["stock_id"], "name": pos["name"], "date": bar["date"],
                       "shares": shares, "price": pos["entry_price"], "stop_price": pos["stop_price"],
                       "target_price": pos["target_price"]})
    account["pending"] = still_pending

    # 2) 持倉逐日檢查停損 / 停利 / 到期
    remaining = []
    for pos in account["positions"]:
        df = bars(pos["stock_id"])
        start = pos["last_checked"] or ""
        todo = df[(df["date"] >= pos["entry_date"]) & (df["date"] > start) & (df["date"] <= as_of)]
        closed = False
        for _, bar in todo.iterrows():
            o, h, l, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
            first_day = bar["date"] == pos["entry_date"]
            pos["days_held"] += 1
            pos["last_checked"] = bar["date"]
            pos["last_close"] = round(c, 2)
            stop, target = pos["stop_price"], pos["target_price"]
            if l <= stop:
                price = o if (not first_day and o < stop) else stop
                _close_position(account, pos, bar["date"], price, "停損", events)
                closed = True
                break
            if h >= target:
                price = o if (not first_day and o > target) else target
                _close_position(account, pos, bar["date"], price, "停利", events)
                closed = True
                break
            if pos["days_held"] >= pos["hold_days"]:
                _close_position(account, pos, bar["date"], c, "持有到期", events)
                closed = True
                break
        if not closed:
            remaining.append(pos)
    account["positions"] = remaining

    # 3) 今天的 BUY → 待成交（同一檔已持有或已排隊就跳過）
    held = {p["stock_id"] for p in account["positions"]} | {o["stock_id"] for o in account["pending"]}
    for r in results:
        if r.get("action") != "BUY" or str(r["stock_id"]) in held:
            continue
        pct = float(r.get("position_size_pct") or 10) / 100
        account["pending"].append({
            "stock_id": str(r["stock_id"]), "name": r.get("name", ""),
            "signal_date": as_of, "signal_score": r.get("signal_score"),
            "budget": round(account["initial_cash"] * pct, 0),
            "stop_loss": float(params.get("stop_loss", 0.08)),
            "target_return": float(params.get("target_return", 0.10)),
            "hold_days": int(params.get("hold_days", 20)),
        })
        held.add(str(r["stock_id"]))
        events.append({"type": "ORDER", "stock_id": str(r["stock_id"]), "name": r.get("name", ""),
                       "date": as_of, "note": "明日開盤買進"})

    # 4) 權益紀錄
    market_value = sum(p["shares"] * p["last_close"] for p in account["positions"])
    equity = round(account["cash"] + market_value, 0)
    hist = [h for h in account["equity_history"] if h["date"] != as_of]
    hist.append({"date": as_of, "equity": equity, "cash": account["cash"],
                 "positions": len(account["positions"])})
    account["equity_history"] = sorted(hist, key=lambda h: h["date"])
    account["events"] = (account.get("events", []) + [{**e, "run_date": as_of} for e in events])[-200:]
    return events


def summary(account: dict) -> dict:
    market_value = sum(p["shares"] * p["last_close"] for p in account["positions"])
    equity = account["cash"] + market_value
    trades = account["trades"]
    wins = [t for t in trades if t["pnl"] > 0]
    return {
        "initial_cash": account["initial_cash"],
        "cash": round(account["cash"], 0),
        "market_value": round(market_value, 0),
        "equity": round(equity, 0),
        "return_pct": round((equity / account["initial_cash"] - 1) * 100, 2),
        "realized_pnl": round(sum(t["pnl"] for t in trades), 0),
        "trade_count": len(trades),
        "winrate": round(len(wins) / len(trades) * 100, 1) if trades else None,
    }

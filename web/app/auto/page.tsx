"use client";
import { useEffect, useState } from "react";
import { api, DailyLatest, errorMessage, PaperAccount } from "@/lib/api";
import { EmptyState, ErrorCard, Skeleton } from "@/components/Feedback";
import SignalResults from "@/components/SignalResults";

const money = (v?: number | null) => typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("zh-TW", { maximumFractionDigits: 0 }) : "—";
const pctText = (v?: number | null) => typeof v === "number" && Number.isFinite(v) ? `${v > 0 ? "+" : ""}${v.toFixed(2)}%` : "—";
const tone = (v?: number | null) => v == null || v === 0 ? "text-muted" : v > 0 ? "text-rise" : "text-fall";

function Stat({ label, value, sub, className = "" }: { label: string; value: string; sub?: string; className?: string }) {
  return <div className="card">
    <div className="text-xs text-muted">{label}</div>
    <div className={`mt-2 font-mono text-2xl font-semibold ${className}`}>{value}</div>
    {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
  </div>;
}

function EquityLine({ points }: { points: { date: string; equity: number }[] }) {
  if (points.length < 2) return <p className="text-sm text-muted">累積兩個交易日以上就會畫出權益曲線。</p>;
  const w = 600, h = 140, pad = 6;
  const values = points.map(p => p.equity);
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const d = points.map((p, i) => `${i ? "L" : "M"}${(pad + (i / (points.length - 1)) * (w - pad * 2)).toFixed(1)},${(h - pad - ((p.equity - min) / span) * (h - pad * 2)).toFixed(1)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  return <div>
    <svg viewBox={`0 0 ${w} ${h}`} className="h-36 w-full" role="img" aria-label="模擬帳戶權益曲線">
      <path d={d} fill="none" strokeWidth={2} className={up ? "stroke-rise" : "stroke-fall"} vectorEffect="non-scaling-stroke" />
    </svg>
    <div className="flex justify-between font-mono text-xs text-muted"><span>{points[0].date}</span><span>{points[points.length - 1].date}</span></div>
  </div>;
}

export default function AutoPage() {
  const [daily, setDaily] = useState<DailyLatest | null>(null);
  const [paper, setPaper] = useState<PaperAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null);
    Promise.all([api.getDailyLatest(controller.signal), api.getPaper(controller.signal)])
      .then(([d, p]) => { setDaily(d); setPaper(p); })
      .catch(err => { if (!controller.signal.aborted) setError(errorMessage(err)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload]);

  return <div className="space-y-8">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="eyebrow">AUTOPILOT</p>
        <h1 className="mt-2 text-3xl font-semibold">自動交易</h1>
        <p className="mt-2 text-sm text-muted">每個交易日 15:30 自動選股，照 BUY 訊號用虛擬資金模擬買賣。不會動到真實帳戶。</p>
      </div>
      <button className="btn-ghost" onClick={() => setReload(v => v + 1)}>重新整理</button>
    </div>

    {error && <ErrorCard message={error} retry={() => setReload(v => v + 1)} />}
    {loading ? <Skeleton /> : <>
      <section className="space-y-4" aria-labelledby="paper-title">
        <h2 id="paper-title" className="text-lg font-semibold">模擬帳戶</h2>
        {!paper || !paper.available ? <EmptyState title="模擬帳戶尚未開始">第一次每日自動選股跑完後，會用 1,000,000 元虛擬資金建立帳戶。</EmptyState> : <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="帳戶總值" value={money(paper.summary.equity)} sub={`初始 ${money(paper.summary.initial_cash)}`} />
            <Stat label="總報酬" value={pctText(paper.summary.return_pct)} className={tone(paper.summary.return_pct)} sub={`已實現 ${money(paper.summary.realized_pnl)}`} />
            <Stat label="現金 / 持股市值" value={money(paper.summary.cash)} sub={`持股 ${money(paper.summary.market_value)}`} />
            <Stat label="已平倉交易" value={`${paper.summary.trade_count} 筆`} sub={paper.summary.winrate == null ? "尚無勝率" : `勝率 ${paper.summary.winrate}%`} />
          </div>
          <div className="card"><div className="mb-3 text-sm font-medium">權益曲線</div><EquityLine points={paper.equity_history} /></div>

          <div className="card overflow-x-auto">
            <div className="mb-3 text-sm font-medium">目前持股（{paper.positions.length}）</div>
            {paper.positions.length ? <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="py-2">股票</th><th>股數</th><th>買進日 / 價</th><th>現價</th><th>未實現</th><th>停損 / 停利</th><th>持有</th></tr></thead>
              <tbody className="font-mono">{paper.positions.map(p => { const pnl = p.shares * p.last_close - p.cost_basis; const pct = pnl / p.cost_basis * 100; return <tr key={p.stock_id} className="border-t border-line">
                <td className="py-2 font-sans">{p.stock_id} {p.name}</td><td>{money(p.shares)}</td><td>{p.entry_date} / {p.entry_price}</td><td>{p.last_close}</td>
                <td className={tone(pnl)}>{money(pnl)}（{pctText(pct)}）</td><td>{p.stop_price} / {p.target_price}</td><td>{p.days_held}/{p.hold_days} 天</td></tr>; })}</tbody>
            </table> : <p className="text-sm text-muted">目前沒有持股。</p>}
          </div>

          {paper.pending.length > 0 && <div className="card">
            <div className="mb-3 text-sm font-medium">待成交（下一個交易日開盤買進）</div>
            <ul className="space-y-1 text-sm">{paper.pending.map(o => <li key={o.stock_id}><span className="font-mono">{o.stock_id}</span> {o.name} · 訊號日 {o.signal_date} · 預算 {money(o.budget)}</li>)}</ul>
          </div>}

          <div className="card overflow-x-auto">
            <div className="mb-3 text-sm font-medium">交易紀錄</div>
            {paper.trades.length ? <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="py-2">股票</th><th>買進</th><th>賣出</th><th>原因</th><th>損益</th></tr></thead>
              <tbody className="font-mono">{paper.trades.map((t, i) => <tr key={`${t.stock_id}-${t.exit_date}-${i}`} className="border-t border-line">
                <td className="py-2 font-sans">{t.stock_id} {t.name}</td><td>{t.entry_date} @ {t.entry_price}</td><td>{t.exit_date} @ {t.exit_price}</td><td className="font-sans">{t.reason}</td>
                <td className={tone(t.pnl)}>{money(t.pnl)}（{pctText(t.return_pct)}）</td></tr>)}</tbody>
            </table> : <p className="text-sm text-muted">還沒有平倉的交易。</p>}
          </div>
        </>}
      </section>

      <section className="space-y-4" aria-labelledby="daily-title">
        <h2 id="daily-title" className="text-lg font-semibold">最新自動選股{daily && daily.available ? `（${daily.trade_date}）` : ""}</h2>
        {!daily || !daily.available ? <EmptyState title="還沒有自動選股紀錄">排程會在每個交易日 15:30 執行；也可以雙擊 run-daily.bat 立即跑一次。</EmptyState> : <>
          <p className="text-xs text-muted">執行時間 {daily.run_at.replace("T", " ")} · 策略 {daily.strategy.name}</p>
          <SignalResults run={daily} />
        </>}
      </section>
    </>}
  </div>;
}

"use client";

import { useEffect, useRef, useState } from "react";

import { formatPrice } from "@/lib/format";

type Day = { date: string; revenue_cents: number };

// Mark specs (dataviz skill): columns ≤ 24px, 4px rounded data-end, square at the baseline,
// a 2px gap between neighbours, hairline recessive grid. One series → no legend box.
const HEIGHT = 220;
const MARGIN = { top: 24, right: 8, bottom: 28, left: 52 };
const MAX_BAR = 24;
const GAP = 2;
const RADIUS = 4;
const SERIES_COLOR = "#b4532a"; // brand accent; validated against the card surface (contrast ≥ 3:1)

function niceMax(value: number): number {
  if (value <= 0) return 100_00;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= value) ?? 10;
  return step * magnitude;
}

function compactDollars(cents: number): string {
  const dollars = cents / 100;
  return dollars >= 1000 ? `$${(dollars / 1000).toFixed(dollars % 1000 === 0 ? 0 : 1)}K` : `$${Math.round(dollars)}`;
}

function shortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** A column with a rounded top and a square bottom, as an SVG path. */
function columnPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(RADIUS, width / 2, height);
  const bottom = y + height;
  return `M${x},${bottom} V${y + r} Q${x},${y} ${x + r},${y} H${x + width - r} Q${x + width},${y} ${x + width},${y + r} V${bottom} Z`;
}

export function RevenueChart({ days }: { days: Day[] }) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [active, setActive] = useState<number | null>(null);

  // Draw at the real width (keeps text crisp instead of scaling the whole SVG).
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const max = niceMax(Math.max(...days.map((d) => d.revenue_cents)));
  const plotWidth = width - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const band = plotWidth / days.length;
  const barWidth = Math.max(2, Math.min(MAX_BAR, band - GAP));
  const y = (cents: number) => MARGIN.top + plotHeight - (cents / max) * plotHeight;
  const ticks = [0, max / 2, max];
  const peak = days.reduce((best, d, i) => (d.revenue_cents > days[best].revenue_cents ? i : best), 0);
  const shown = active ?? null;

  function onKeyDown(event: React.KeyboardEvent) {
    const last = days.length - 1;
    const moves: Record<string, number> = {
      ArrowLeft: Math.max((shown ?? last + 1) - 1, 0),
      ArrowRight: Math.min((shown ?? -1) + 1, last),
      Home: 0,
      End: last,
    };
    if (event.key in moves) {
      event.preventDefault();
      setActive(moves[event.key]);
    }
  }

  return (
    <div>
      <div
        ref={container}
        className="relative focus-visible:outline-2"
        tabIndex={0}
        role="group"
        aria-label="Daily revenue, last 30 days. Use the left and right arrow keys to read each day."
        onKeyDown={onKeyDown}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
      >
        <svg width={width} height={HEIGHT} role="img" aria-hidden="true" className="block">
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} stroke="#e6dfd3" strokeWidth={1} />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px] tabular-nums">
                {compactDollars(tick)}
              </text>
            </g>
          ))}

          {days.map((day, i) => {
            const x = MARGIN.left + i * band + (band - barWidth) / 2;
            const top = y(day.revenue_cents);
            const height = MARGIN.top + plotHeight - top;
            return (
              <g key={day.date}>
                {height > 0 && (
                  <path
                    d={columnPath(x, top, barWidth, height)}
                    fill={SERIES_COLOR}
                    opacity={shown === null || shown === i ? 1 : 0.55}
                  />
                )}
                {/* The hit target is the whole band, much bigger than the bar itself. */}
                <rect
                  x={MARGIN.left + i * band}
                  y={MARGIN.top}
                  width={band}
                  height={plotHeight}
                  fill="transparent"
                  onPointerMove={() => setActive(i)}
                />
                {/* Weekly ticks plus the last day, skipping a weekly tick that would collide with it. */}
                {((i % 7 === 0 && i <= days.length - 4) || i === days.length - 1) && (
                  <text x={x + barWidth / 2} y={HEIGHT - 8} textAnchor="middle" className="fill-muted text-[11px]">
                    {shortDate(day.date)}
                  </text>
                )}
              </g>
            );
          })}

          {/* One direct label: the peak day, on its cap. Everything else lives in the tooltip and table. */}
          {days[peak].revenue_cents > 0 && shown === null && (
            <text
              x={MARGIN.left + peak * band + band / 2}
              y={y(days[peak].revenue_cents) - 6}
              textAnchor="middle"
              className="fill-ink text-[11px] font-medium"
            >
              {formatPrice(days[peak].revenue_cents)}
            </text>
          )}
          <line x1={MARGIN.left} x2={width - MARGIN.right} y1={MARGIN.top + plotHeight} y2={MARGIN.top + plotHeight} stroke="#cfc6b8" />
        </svg>

        {shown !== null && (
          <div
            role="status"
            className="pointer-events-none absolute z-10 -translate-x-1/2 whitespace-nowrap rounded-sm bg-ink px-3 py-2 text-xs text-paper shadow-lg"
            style={{
              left: Math.min(Math.max(MARGIN.left + shown * band + band / 2, 60), width - 60),
              top: Math.max(y(days[shown].revenue_cents) - 52, 0),
            }}
          >
            <p className="text-sm font-semibold">{formatPrice(days[shown].revenue_cents)}</p>
            <p className="text-paper/70">{shortDate(days[shown].date)}</p>
          </div>
        )}
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted hover:text-ink">Show as table</summary>
        <table className="mt-2 w-full max-w-sm text-left">
          <thead className="text-xs uppercase tracking-widest text-muted">
            <tr>
              <th scope="col" className="py-1 font-medium">Day</th>
              <th scope="col" className="py-1 text-right font-medium">Revenue</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {days.map((day) => (
              <tr key={day.date} className="border-t border-line">
                <td className="py-1">{shortDate(day.date)}</td>
                <td className="py-1 text-right">{formatPrice(day.revenue_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

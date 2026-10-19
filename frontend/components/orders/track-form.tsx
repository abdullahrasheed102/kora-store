"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { OrderProgress, OrderTimeline } from "@/components/orders/order-progress";
import { StatusBadge } from "@/components/account/status-badge";
import { api, ApiError } from "@/lib/api";
import { COUNTRY_NAMES, formatDate } from "@/lib/format";
import type { TrackingResult } from "@/lib/types";

const inputClass =
  "mt-1.5 h-12 w-full rounded-sm border border-line bg-card px-4 text-base focus:border-ink/50 focus:outline-none focus-visible:outline-2";

export function TrackForm() {
  const prefill = useSearchParams().get("order") ?? "";
  const [result, setResult] = useState<TrackingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setLoading(true);
    try {
      setResult(await api.trackOrder(String(form.get("order_number")), String(form.get("email"))));
    } catch (caught) {
      setResult(null);
      setError(
        caught instanceof ApiError && caught.status === 429
          ? "Too many lookups. Please wait a few minutes and try again."
          : caught instanceof ApiError
            ? caught.message
            : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-10">
      <form onSubmit={submit} className="grid gap-4 rounded-sm bg-card p-6 ring-1 ring-line sm:grid-cols-[1fr_1.4fr_auto] sm:items-end">
        <div>
          <label htmlFor="order_number" className="text-sm font-medium">
            Order number
          </label>
          <input id="order_number" name="order_number" required defaultValue={prefill} placeholder="KO-1005" className={inputClass} />
        </div>
        <div>
          <label htmlFor="email" className="text-sm font-medium">
            Email used for the order
          </label>
          <input id="email" name="email" type="email" autoComplete="email" required className={inputClass} />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="h-12 rounded-full bg-ink px-7 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40"
        >
          {loading ? "Looking up…" : "Track order"}
        </button>
      </form>

      {error && (
        <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
          {error}
        </p>
      )}

      {result && <TrackingDetails result={result} />}
    </div>
  );
}

function TrackingDetails({ result }: { result: TrackingResult }) {
  return (
    <section aria-labelledby="tracking-heading" className="space-y-10" aria-live="polite">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="tracking-heading" className="font-serif text-3xl">
            {result.order_number}
          </h2>
          <StatusBadge status={result.status} />
        </div>
        <p className="mt-1 text-sm text-muted">
          Placed {formatDate(result.created_at)} · shipping to {result.shipping_city},{" "}
          {COUNTRY_NAMES[result.shipping_country] ?? result.shipping_country}
        </p>
        {result.status_note && <p className="mt-4 rounded-sm bg-sage px-4 py-3 text-sm">{result.status_note}</p>}
      </div>

      <OrderProgress status={result.status} />

      <div className="grid gap-10 sm:grid-cols-2">
        <div className="space-y-6">
          <dl className="space-y-3 text-sm">
            {result.estimated_delivery && result.status !== "delivered" && (
              <div>
                <dt className="text-muted">Estimated delivery</dt>
                <dd className="mt-0.5 font-serif text-2xl">{formatDate(result.estimated_delivery)}</dd>
              </div>
            )}
            {result.delivered_at && (
              <div>
                <dt className="text-muted">Delivered</dt>
                <dd className="mt-0.5 font-serif text-2xl">{formatDate(result.delivered_at)}</dd>
              </div>
            )}
            {result.tracking_number && (
              <div>
                <dt className="text-muted">{result.carrier} tracking number</dt>
                <dd className="mt-0.5 font-mono">{result.tracking_number}</dd>
              </div>
            )}
          </dl>
          <div>
            <h3 className="text-xs font-medium uppercase tracking-widest text-muted">Items</h3>
            <ul className="mt-2 space-y-1 text-sm">
              {result.items.map((item) => (
                <li key={`${item.product_name}-${item.size}-${item.color}`}>
                  {item.quantity} × {item.product_name} <span className="text-muted">({item.color} · {item.size})</span>
                </li>
              ))}
            </ul>
          </div>
          {result.status === "delivered" && (
            <Link
              href={`/returns?order=${result.order_number}`}
              className="inline-block rounded-full border border-ink/20 px-5 py-2.5 text-sm font-medium hover:border-ink"
            >
              Start a return
            </Link>
          )}
        </div>
        <div>
          <h3 className="mb-4 text-xs font-medium uppercase tracking-widest text-muted">Timeline</h3>
          <OrderTimeline events={result.events} />
        </div>
      </div>
    </section>
  );
}

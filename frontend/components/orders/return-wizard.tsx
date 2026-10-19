"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { formatDate, formatPrice, RETURN_REASONS, returnStatusLabel } from "@/lib/format";
import type { ReturnEligibility, ReturnReason, ReturnRequestView, User } from "@/lib/types";

const inputClass =
  "mt-1.5 h-12 w-full rounded-sm border border-line bg-card px-4 text-base focus:border-ink/50 focus:outline-none focus-visible:outline-2";

type Lookup = { order_number: string; email?: string };

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Too many lookups. Please wait a few minutes and try again.";
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

/**
 * Three steps: find the order → choose items → done. Every rule is enforced by the backend;
 * this page only shows what the eligibility check returned, and why.
 */
export function ReturnWizard({ user, initialOrder }: { user: User | null; initialOrder: string | null }) {
  const [lookup, setLookup] = useState<Lookup | null>(null);
  const [eligibility, setEligibility] = useState<ReturnEligibility | null>(null);
  const [created, setCreated] = useState<ReturnRequestView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function find(next: Lookup) {
    setError(null);
    setLoading(true);
    try {
      setEligibility(await api.returnEligibility(next.order_number, next.email));
      setLookup(next);
    } catch (caught) {
      setError(messageFor(caught));
    } finally {
      setLoading(false);
    }
  }

  // Logged in and coming from an account order page: no need to type anything.
  useEffect(() => {
    if (!user || !initialOrder) return;
    let cancelled = false;
    api
      .returnEligibility(initialOrder)
      .then((result) => {
        if (cancelled) return;
        setEligibility(result);
        setLookup({ order_number: initialOrder });
      })
      .catch(() => undefined); // not their order: fall back to the lookup form
    return () => {
      cancelled = true;
    };
  }, [user, initialOrder]);

  if (created) return <ReturnCreated request={created} email={lookup?.email ?? user?.email} />;

  if (eligibility && lookup) {
    return (
      <ChooseItems
        eligibility={eligibility}
        lookup={lookup}
        onCreated={setCreated}
        onBack={() => {
          setEligibility(null);
          setLookup(null);
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          void find({ order_number: String(form.get("order_number")), email: String(form.get("email")) });
        }}
        className="grid gap-4 rounded-sm bg-card p-6 ring-1 ring-line sm:grid-cols-[1fr_1.4fr_auto] sm:items-end"
      >
        <div>
          <label htmlFor="order_number" className="text-sm font-medium">
            Order number
          </label>
          <input id="order_number" name="order_number" required defaultValue={initialOrder ?? ""} placeholder="KO-1005" className={inputClass} />
        </div>
        <div>
          <label htmlFor="email" className="text-sm font-medium">
            Email used for the order
          </label>
          <input id="email" name="email" type="email" autoComplete="email" required defaultValue={user?.email} className={inputClass} />
        </div>
        <button type="submit" disabled={loading} className="h-12 rounded-full bg-ink px-7 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40">
          {loading ? "Finding…" : "Find order"}
        </button>
      </form>
      {error && (
        <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
          {error}
        </p>
      )}
    </div>
  );
}

function ChooseItems({
  eligibility,
  lookup,
  onCreated,
  onBack,
}: {
  eligibility: ReturnEligibility;
  lookup: Lookup;
  onCreated: (request: ReturnRequestView) => void;
  onBack: () => void;
}) {
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [type, setType] = useState<"refund" | "exchange">("refund");
  const [exchangeVariant, setExchangeVariant] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const selected = eligibility.items.filter((item) => (quantities[item.order_item_id] ?? 0) > 0);
  const canExchange = selected.length === 1 && selected[0].exchange_options.length > 0;
  const refund = selected.reduce((sum, item) => sum + item.unit_price_cents * quantities[item.order_item_id], 0);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setSubmitting(true);
    try {
      const isExchange = type === "exchange" && canExchange;
      onCreated(
        await api.createReturn({
          ...lookup,
          items: selected.map((item) => ({ order_item_id: item.order_item_id, quantity: quantities[item.order_item_id] })),
          type: isExchange ? "exchange" : "refund",
          exchange_variant_id: isExchange ? (exchangeVariant ?? undefined) : undefined,
          reason: String(form.get("reason")) as ReturnReason,
          comments: String(form.get("comments") ?? "") || undefined,
          condition_confirmed: form.get("condition") === "on",
        }),
      );
    } catch (caught) {
      setSubmitting(false);
      setError(messageFor(caught));
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <button type="button" onClick={onBack} className="text-sm text-muted hover:text-ink">
          ← Look up a different order
        </button>
        <h2 className="mt-3 font-serif text-3xl">{eligibility.order_number}</h2>
        {eligibility.eligible ? (
          <p className="mt-2 text-sm text-muted">
            Delivered {eligibility.delivered_at && formatDate(eligibility.delivered_at)}. You have{" "}
            <span className="font-medium text-ink">
              {eligibility.days_left} {eligibility.days_left === 1 ? "day" : "days"}
            </span>{" "}
            left to start a return (until {eligibility.return_deadline && formatDate(eligibility.return_deadline)}).
          </p>
        ) : (
          <p className="mt-4 rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark" role="status">
            {eligibility.reason?.message}{" "}
            <Link href="/policies/returns" className="underline underline-offset-2">
              Read the returns policy
            </Link>
          </p>
        )}
      </div>

      {eligibility.returns.length > 0 && <ExistingReturns returns={eligibility.returns} />}

      {eligibility.eligible && (
        <form onSubmit={submit} className="space-y-8">
          <fieldset>
            <legend className="font-serif text-xl">Which items?</legend>
            <ul className="mt-4 divide-y divide-line rounded-sm bg-card ring-1 ring-line">
              {eligibility.items.map((item) => {
                const returnable = item.returnable_quantity > 0;
                const quantity = quantities[item.order_item_id] ?? 0;
                return (
                  <li key={item.order_item_id} className={`flex flex-wrap items-center gap-4 p-4 ${returnable ? "" : "opacity-70"}`}>
                    <label className={`flex flex-1 items-start gap-3 ${returnable ? "cursor-pointer" : ""}`}>
                      <input
                        type="checkbox"
                        disabled={!returnable}
                        checked={quantity > 0}
                        onChange={(event) =>
                          setQuantities({ ...quantities, [item.order_item_id]: event.target.checked ? 1 : 0 })
                        }
                        className="mt-1 size-4 accent-ink"
                      />
                      <span className="text-sm">
                        <span className="font-medium">{item.product_name}</span>
                        <span className="block text-muted">
                          {item.color} · {item.size} · {formatPrice(item.unit_price_cents)}
                        </span>
                        {item.reason && <span className="mt-1 block text-accent-dark">{item.reason.message}</span>}
                      </span>
                    </label>
                    {returnable && item.returnable_quantity > 1 && quantity > 0 && (
                      <label className="text-sm">
                        <span className="sr-only">Quantity of {item.product_name}</span>
                        <select
                          value={quantity}
                          onChange={(event) => setQuantities({ ...quantities, [item.order_item_id]: Number(event.target.value) })}
                          className="h-10 rounded-full border border-line bg-paper px-3"
                        >
                          {Array.from({ length: item.returnable_quantity }, (_, i) => i + 1).map((n) => (
                            <option key={n} value={n}>
                              {n}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                  </li>
                );
              })}
            </ul>
          </fieldset>

          {selected.length > 0 && (
            <>
              <fieldset>
                <legend className="font-serif text-xl">Refund or exchange?</legend>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <label className="flex cursor-pointer gap-3 rounded-sm border border-line bg-card p-4 has-[:checked]:border-ink">
                    <input type="radio" name="type" checked={type === "refund"} onChange={() => setType("refund")} className="mt-1 size-4 accent-ink" />
                    <span className="text-sm">
                      <span className="font-medium">Refund {formatPrice(refund)}</span>
                      <span className="block text-muted">To your original payment method, 5–7 business days after we receive it.</span>
                    </span>
                  </label>
                  <label
                    className={`flex gap-3 rounded-sm border border-line bg-card p-4 has-[:checked]:border-ink ${canExchange ? "cursor-pointer" : "opacity-60"}`}
                  >
                    <input
                      type="radio"
                      name="type"
                      disabled={!canExchange}
                      checked={type === "exchange" && canExchange}
                      onChange={() => setType("exchange")}
                      className="mt-1 size-4 accent-ink"
                    />
                    <span className="text-sm">
                      <span className="font-medium">Exchange (free)</span>
                      <span className="block text-muted">
                        {canExchange ? "A different size or colour, subject to stock." : "Choose one item to exchange it."}
                      </span>
                    </span>
                  </label>
                </div>
                {type === "exchange" && canExchange && (
                  <div className="mt-4">
                    <label htmlFor="exchange" className="text-sm font-medium">
                      Exchange {selected[0].product_name} for
                    </label>
                    <select
                      id="exchange"
                      required
                      value={exchangeVariant ?? ""}
                      onChange={(event) => setExchangeVariant(Number(event.target.value) || null)}
                      className={inputClass}
                    >
                      <option value="">Choose a size and colour</option>
                      {selected[0].exchange_options.map((option) => (
                        <option key={option.variant_id} value={option.variant_id}>
                          {option.size} / {option.color}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </fieldset>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="reason" className="text-sm font-medium">
                    Reason
                  </label>
                  <select id="reason" name="reason" required defaultValue="" className={inputClass}>
                    <option value="" disabled>
                      Choose a reason
                    </option>
                    {RETURN_REASONS.map((reason) => (
                      <option key={reason.value} value={reason.value}>
                        {reason.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="comments" className="text-sm font-medium">
                    Anything else? (optional)
                  </label>
                  <textarea id="comments" name="comments" rows={3} maxLength={1000} className={`${inputClass} h-auto py-3`} />
                </div>
              </div>

              <label className="flex items-start gap-3 text-sm">
                <input type="checkbox" name="condition" required className="mt-0.5 size-4 accent-ink" />
                <span>The items are unworn, with the tags still attached.</span>
              </label>

              <p className="text-sm text-muted">
                {eligibility.return_shipping === "prepaid_label"
                  ? "Returns within the US are free: we'll email you a prepaid label."
                  : "International returns: you pay the return shipping (we'll email the address)."}
              </p>

              {error && (
                <p role="alert" className="rounded-sm bg-accent/10 px-4 py-3 text-sm text-accent-dark">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting || (type === "exchange" && canExchange && !exchangeVariant)}
                className="h-12 rounded-full bg-ink px-8 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40"
              >
                {submitting ? "Sending…" : type === "exchange" && canExchange ? "Request exchange" : "Request return"}
              </button>
            </>
          )}
        </form>
      )}
    </div>
  );
}

function ExistingReturns({ returns }: { returns: ReturnRequestView[] }) {
  return (
    <section aria-labelledby="existing-returns" className="rounded-sm bg-sage/60 p-4 text-sm">
      <h3 id="existing-returns" className="font-medium">
        Returns already started for this order
      </h3>
      <ul className="mt-2 space-y-1">
        {returns.map((request) => (
          <li key={request.id}>
            {formatDate(request.created_at)} · {request.items.map((i) => `${i.quantity} × ${i.product_name}`).join(", ")} ·{" "}
            <span className="font-medium">{returnStatusLabel(request.status)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ReturnCreated({ request, email }: { request: ReturnRequestView; email?: string }) {
  return (
    <div className="rounded-sm bg-card p-6 ring-1 ring-line sm:p-8" role="status">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">
        {request.type === "exchange" ? "Exchange requested" : "Return requested"}
      </p>
      <h2 className="mt-3 font-serif text-3xl">We&apos;ve got your request for {request.order_number}</h2>
      <ul className="mt-6 space-y-1 text-sm">
        {request.items.map((item) => (
          <li key={item.order_item_id}>
            {item.quantity} × {item.product_name} <span className="text-muted">({item.color} · {item.size})</span>
          </li>
        ))}
      </ul>
      {request.exchange_details && <p className="mt-3 text-sm">{request.exchange_details}.</p>}
      <h3 className="mt-8 font-medium">What happens next</h3>
      <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-ink/80">
        <li>
          {request.return_shipping === "prepaid_label"
            ? `We'll email a free prepaid return label${email ? ` to ${email}` : ""} within one business day.`
            : `We'll email our returns address${email ? ` to ${email}` : ""}. International return shipping is paid by you.`}
        </li>
        <li>Pack the items unworn, with tags attached, and drop the parcel off.</li>
        <li>
          {request.type === "exchange"
            ? "We'll send your new size as soon as the return is scanned."
            : `Once it arrives, we refund ${formatPrice(request.refund_estimate_cents)} to your original payment method within 5–7 business days.`}
        </li>
      </ol>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/shop" className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Continue shopping
        </Link>
        <Link href={`/track?order=${request.order_number}`} className="rounded-full border border-ink/20 px-6 py-3 text-sm font-medium hover:border-ink">
          Track this order
        </Link>
      </div>
    </div>
  );
}

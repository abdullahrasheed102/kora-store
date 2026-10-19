"use client";

import Link from "next/link";

import { useCart } from "@/components/cart/cart-provider";
import { formatPrice } from "@/lib/format";

export function FreeShippingProgress() {
  const { quote } = useCart();
  if (!quote || quote.amount_to_free_shipping_cents === null || quote.subtotal_cents === 0) return null;
  const gap = quote.amount_to_free_shipping_cents;
  const progress = Math.min(quote.subtotal_cents / (quote.free_shipping_threshold_cents + 1), 1);
  return (
    <div>
      <p className="text-sm">
        {gap > 0 ? (
          <>
            Add <span className="font-medium">{formatPrice(gap)}</span> more for free standard shipping.
          </>
        ) : (
          <>You&apos;ve unlocked free standard shipping.</>
        )}
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${progress * 100}%` }} />
      </div>
    </div>
  );
}

/** Totals from the server's quote. Dimmed while a newer quote is on its way. */
export function CartTotals() {
  const { quote, isUpdating } = useCart();
  if (!quote) return null;
  return (
    <dl className={`space-y-2 text-sm transition-opacity ${isUpdating ? "opacity-50" : ""}`} aria-busy={isUpdating}>
      <div className="flex justify-between">
        <dt className="text-muted">Subtotal</dt>
        <dd>{formatPrice(quote.subtotal_cents)}</dd>
      </div>
      <div className="flex justify-between">
        <dt className="text-muted">Shipping</dt>
        <dd>{quote.subtotal_cents === 0 ? "—" : quote.shipping_cents === 0 ? "Free" : formatPrice(quote.shipping_cents)}</dd>
      </div>
      <div className="flex justify-between border-t border-line pt-3 text-base font-medium">
        <dt>Total</dt>
        <dd>{formatPrice(quote.total_cents)}</dd>
      </div>
    </dl>
  );
}

export function CheckoutButton({ onNavigate }: { onNavigate?: () => void }) {
  const { quote, isUpdating } = useCart();
  const ready = Boolean(quote && quote.subtotal_cents > 0 && !quote.has_issues && !isUpdating);
  const className = "flex h-13 w-full items-center justify-center rounded-full py-4 text-sm font-medium transition";
  return ready ? (
    <Link href="/checkout" onClick={onNavigate} className={`${className} bg-ink text-paper hover:bg-accent`}>
      Checkout
    </Link>
  ) : (
    <span aria-disabled="true" className={`${className} cursor-not-allowed bg-ink/30 text-paper`}>
      Checkout
    </span>
  );
}

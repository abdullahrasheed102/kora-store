"use client";

import Link from "next/link";

import { CartLines } from "@/components/cart/cart-lines";
import { useCart } from "@/components/cart/cart-provider";
import { CartTotals, CheckoutButton, FreeShippingProgress } from "@/components/cart/cart-totals";
import { SHIPPING_LABELS } from "@/lib/format";
import type { ShippingMethod } from "@/lib/types";

export function CartPage() {
  const { count, quote, quoteError, shippingMethod, setShippingMethod } = useCart();

  if (count === 0) {
    return (
      <div className="rounded-sm border border-dashed border-line px-6 py-20 text-center">
        <p className="font-serif text-2xl">Your bag is empty</p>
        <p className="mt-2 text-sm text-muted">Items you add will be saved on this device.</p>
        <Link href="/shop" className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Start shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-12 lg:grid-cols-[1fr_380px]">
      <section aria-label="Items in your bag">
        {quote ? <CartLines /> : <p className="py-8 text-sm text-muted">Loading your bag…</p>}
        {quoteError && (
          <p className="mt-4 text-sm text-accent" role="alert">
            We couldn&apos;t update prices. Check your connection and try again.
          </p>
        )}
      </section>

      <aside aria-label="Order summary" className="h-fit space-y-6 rounded-sm bg-card p-6 ring-1 ring-line lg:sticky lg:top-32">
        <h2 className="font-serif text-2xl">Summary</h2>
        <FreeShippingProgress />
        <fieldset>
          <legend className="text-xs font-medium uppercase tracking-widest text-muted">Shipping</legend>
          <div className="mt-3 space-y-2">
            {(Object.keys(SHIPPING_LABELS) as ShippingMethod[]).map((method) => (
              <label
                key={method}
                className="flex cursor-pointer items-start gap-3 rounded-sm border border-line p-3 has-[:checked]:border-ink"
              >
                <input
                  type="radio"
                  name="shipping"
                  value={method}
                  checked={shippingMethod === method}
                  onChange={() => setShippingMethod(method)}
                  className="mt-1 size-4 accent-ink"
                />
                <span className="text-sm">
                  <span className="font-medium">{SHIPPING_LABELS[method].label}</span>
                  <span className="block text-muted">{SHIPPING_LABELS[method].detail}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <CartTotals />
        <CheckoutButton />
      </aside>
    </div>
  );
}

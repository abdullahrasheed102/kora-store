"use client";

import Link from "next/link";

import { useCart } from "@/components/cart/cart-provider";
import { ProductArt } from "@/components/product-art";
import { formatPrice } from "@/lib/format";
import { MAX_QUANTITY } from "@/lib/cart-store";
import type { CartQuoteItem } from "@/lib/types";

const ISSUE_TEXT: Record<string, (item: CartQuoteItem) => string> = {
  unavailable: () => "This item is no longer available.",
  out_of_stock: () => "Sold out. It won't be charged.",
  insufficient_stock: (item) => `Only ${item.quantity} left. Your bag shows the ${item.quantity} we have.`,
};

/** The items in the bag, as priced by the server. Shared by the drawer and the /cart page. */
export function CartLines({ onNavigate, compact = false }: { onNavigate?: () => void; compact?: boolean }) {
  const { quote, lines, setQuantity, removeItem } = useCart();
  if (!quote) return null;

  // Keep the shopper's order (the quote can arrive a moment after a change).
  const byId = new Map(quote.items.map((item) => [item.variant_id, item]));
  const items = lines.map((line) => byId.get(line.variantId)).filter((item): item is CartQuoteItem => Boolean(item));

  return (
    <ul className="divide-y divide-line">
      {items.map((item) => {
        const requested = lines.find((line) => line.variantId === item.variant_id)?.quantity ?? item.requested_quantity;
        const max = Math.min(item.available_quantity ?? MAX_QUANTITY, MAX_QUANTITY);
        return (
          <li key={item.variant_id} className="flex gap-4 py-5">
            {item.product_slug ? (
              <Link href={`/products/${item.product_slug}`} onClick={onNavigate} className="shrink-0">
                <ProductArt
                  name={item.product_name ?? "Product"}
                  slug={item.product_slug}
                  categorySlug={item.category_slug ?? ""}
                  color={item.color}
                  imageUrl={item.image_url}
                  className={`${compact ? "w-20" : "w-24 sm:w-28"} aspect-[4/5] rounded-sm`}
                />
              </Link>
            ) : (
              <div className={`${compact ? "w-20" : "w-24 sm:w-28"} aspect-[4/5] shrink-0 rounded-sm bg-line/60`} />
            )}

            <div className="flex min-w-0 flex-1 flex-col">
              <div className="flex justify-between gap-3">
                <div className="min-w-0">
                  {item.product_slug ? (
                    <Link href={`/products/${item.product_slug}`} onClick={onNavigate} className="font-medium hover:underline">
                      {item.product_name}
                    </Link>
                  ) : (
                    <p className="font-medium">Unavailable item</p>
                  )}
                  {item.size && (
                    <p className="mt-0.5 text-sm text-muted">
                      {item.color} · {item.size}
                    </p>
                  )}
                  {item.is_final_sale && <p className="mt-0.5 text-xs font-medium text-accent">Final sale</p>}
                </div>
                <p className="shrink-0 text-sm font-medium">{formatPrice(item.line_total_cents)}</p>
              </div>

              {item.issue && (
                <p className="mt-2 text-sm text-accent" role="status">
                  {ISSUE_TEXT[item.issue](item)}
                </p>
              )}

              <div className="mt-auto flex items-center justify-between pt-3">
                {item.issue === "unavailable" || item.issue === "out_of_stock" ? (
                  <span />
                ) : (
                  <div className="inline-flex items-center rounded-full border border-line" role="group" aria-label={`Quantity of ${item.product_name}`}>
                    <button
                      type="button"
                      onClick={() => setQuantity(item.variant_id, requested - 1)}
                      className="size-9 rounded-full text-lg hover:bg-line/60"
                      aria-label="Decrease quantity"
                    >
                      −
                    </button>
                    <span className="w-7 text-center text-sm tabular-nums" aria-live="polite">
                      {requested}
                    </span>
                    <button
                      type="button"
                      onClick={() => setQuantity(item.variant_id, requested + 1)}
                      disabled={requested >= max}
                      className="size-9 rounded-full text-lg hover:bg-line/60 disabled:text-muted/50 disabled:hover:bg-transparent"
                      aria-label="Increase quantity"
                    >
                      +
                    </button>
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => removeItem(item.variant_id)}
                  className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
                >
                  Remove
                </button>
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

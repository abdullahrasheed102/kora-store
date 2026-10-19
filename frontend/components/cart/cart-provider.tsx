"use client";

import { createContext, use, useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { api } from "@/lib/api";
import { cartStore, MAX_QUANTITY, type CartLine } from "@/lib/cart-store";
import type { CartQuote, ShippingMethod } from "@/lib/types";

type CartContextValue = {
  lines: CartLine[];
  /** Server-priced view of the cart. Null until the first quote arrives. */
  quote: CartQuote | null;
  /** True while the quote on screen is for an older version of the cart. */
  isUpdating: boolean;
  quoteError: boolean;
  count: number;
  shippingMethod: ShippingMethod;
  setShippingMethod: (method: ShippingMethod) => void;
  addItem: (variantId: number, quantity?: number) => void;
  setQuantity: (variantId: number, quantity: number) => void;
  removeItem: (variantId: number) => void;
  clear: () => void;
  isDrawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);

const QUOTE_DELAY_MS = 150; // wait for quick +/- clicks to finish before asking the server

export function CartProvider({ children }: { children: React.ReactNode }) {
  const lines = useSyncExternalStore(cartStore.subscribe, cartStore.getSnapshot, cartStore.getServerSnapshot);
  const [shippingMethod, setShippingMethod] = useState<ShippingMethod>("standard");
  const [result, setResult] = useState<{ key: string; quote: CartQuote | null; error: boolean } | null>(null);
  const [isDrawerOpen, setDrawerOpen] = useState(false);

  // A key that identifies this exact cart + shipping method. The quote is "current" only if it
  // was made for the same key, which tells us when we're waiting for a fresh one.
  const key = JSON.stringify([lines, shippingMethod]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .quoteCart(
          lines.map((line) => ({ variant_id: line.variantId, quantity: line.quantity })),
          shippingMethod,
          controller.signal,
        )
        .then((quote) => setResult({ key, quote, error: false }))
        .catch((error: unknown) => {
          if (!controller.signal.aborted) setResult((previous) => ({ key, quote: previous?.quote ?? null, error: true }));
          void error;
        });
    }, QUOTE_DELAY_MS);
    // A newer cart cancels the older request, so a slow old answer can't overwrite a new one.
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, lines, shippingMethod]);

  const update = useCallback((change: (lines: CartLine[]) => CartLine[]) => {
    cartStore.setLines(change(cartStore.getSnapshot()));
  }, []);

  const value = useMemo<CartContextValue>(() => {
    const setQuantity = (variantId: number, quantity: number) =>
      update((current) =>
        quantity <= 0
          ? current.filter((line) => line.variantId !== variantId)
          : current.map((line) =>
              line.variantId === variantId ? { ...line, quantity: Math.min(quantity, MAX_QUANTITY) } : line,
            ),
      );
    return {
      lines,
      quote: result?.quote ?? null,
      isUpdating: result?.key !== key,
      quoteError: result?.key === key && result.error,
      count: lines.reduce((total, line) => total + line.quantity, 0),
      shippingMethod,
      setShippingMethod,
      addItem: (variantId, quantity = 1) =>
        update((current) => {
          const existing = current.find((line) => line.variantId === variantId);
          return existing
            ? current.map((line) =>
                line.variantId === variantId ? { ...line, quantity: Math.min(line.quantity + quantity, MAX_QUANTITY) } : line,
              )
            : [...current, { variantId, quantity: Math.min(quantity, MAX_QUANTITY) }];
        }),
      setQuantity,
      removeItem: (variantId) => setQuantity(variantId, 0),
      clear: () => update(() => []),
      isDrawerOpen,
      openDrawer: () => setDrawerOpen(true),
      closeDrawer: () => setDrawerOpen(false),
    };
  }, [lines, result, key, shippingMethod, isDrawerOpen, update]);

  return <CartContext value={value}>{children}</CartContext>;
}

export function useCart(): CartContextValue {
  const context = use(CartContext);
  if (!context) throw new Error("useCart must be used inside <CartProvider>");
  return context;
}

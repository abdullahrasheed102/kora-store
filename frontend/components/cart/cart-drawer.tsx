"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { CartLines } from "@/components/cart/cart-lines";
import { useCart } from "@/components/cart/cart-provider";
import { CartTotals, CheckoutButton, FreeShippingProgress } from "@/components/cart/cart-totals";
import { CloseIcon } from "@/components/icons";

export function CartDrawer() {
  const { isDrawerOpen, closeDrawer, count, quote, quoteError } = useCart();
  const dialog = useRef<HTMLDialogElement>(null);

  // Keep the native <dialog> in sync with our state (it also closes itself on Escape).
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (isDrawerOpen && !element.open) element.showModal();
    if (!isDrawerOpen && element.open) element.close();
  }, [isDrawerOpen]);

  return (
    <dialog
      ref={dialog}
      aria-label="Shopping bag"
      onClose={closeDrawer}
      onClick={(event) => {
        if (event.target === dialog.current) closeDrawer(); // backdrop click
      }}
      className="ml-auto mr-0 h-dvh max-h-none w-full max-w-md bg-paper p-0 text-ink backdrop:bg-ink/40 sm:w-[28rem]"
    >
      <div className="flex h-full flex-col">
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
          <h2 className="font-serif text-xl">
            Your bag {count > 0 && <span className="text-muted">({count})</span>}
          </h2>
          <button
            type="button"
            onClick={closeDrawer}
            className="inline-flex size-10 items-center justify-center rounded-full hover:bg-line/60"
            aria-label="Close bag"
          >
            <CloseIcon />
          </button>
        </div>

        {count === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
            <p className="font-serif text-2xl">Your bag is empty</p>
            <p className="mt-2 text-sm text-muted">Good things are waiting in the shop.</p>
            <Link
              href="/shop"
              onClick={closeDrawer}
              className="mt-6 rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent"
            >
              Start shopping
            </Link>
          </div>
        ) : (
          <>
            <div className="border-b border-line px-5 py-4">
              <FreeShippingProgress />
            </div>
            <div className="flex-1 overflow-y-auto px-5">
              {quote ? <CartLines onNavigate={closeDrawer} compact /> : <p className="py-8 text-sm text-muted">Loading your bag…</p>}
              {quoteError && (
                <p className="py-3 text-sm text-accent" role="alert">
                  We couldn&apos;t update prices. Check your connection and try again.
                </p>
              )}
            </div>
            <div className="space-y-4 border-t border-line px-5 py-5">
              <CartTotals />
              <CheckoutButton />
              <Link href="/cart" onClick={closeDrawer} className="block text-center text-sm font-medium underline underline-offset-4 hover:text-accent">
                View bag and shipping options
              </Link>
            </div>
          </>
        )}
      </div>
    </dialog>
  );
}

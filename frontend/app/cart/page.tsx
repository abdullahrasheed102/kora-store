import type { Metadata } from "next";

import { CartPage } from "@/components/cart/cart-page";

export const metadata: Metadata = { title: "Your bag", robots: { index: false } };

export default function Page() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 lg:px-8">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Your bag</h1>
      <p className="mt-2 text-sm text-muted">Prices and stock are checked live every time your bag changes.</p>
      <div className="mt-10">
        {/* The cart lives in this browser's storage, so it renders on the client. */}
        <CartPage />
      </div>
    </div>
  );
}

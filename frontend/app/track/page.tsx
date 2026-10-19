import type { Metadata } from "next";
import { Suspense } from "react";

import { TrackForm } from "@/components/orders/track-form";

export const metadata: Metadata = {
  title: "Track your order",
  description: "Check the status of your Kora Outfitters order with your order number and email.",
};

export default function TrackPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 pt-12 sm:px-6">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Track your order</h1>
      <p className="mt-3 text-muted">
        Enter the order number from your confirmation email (it starts with KO-) and the email you ordered with.
      </p>
      <div className="mt-10">
        {/* useSearchParams (?order= prefill) is request data, so the form streams in. */}
        <Suspense fallback={<div className="h-32 rounded-sm bg-card ring-1 ring-line" aria-busy="true" />}>
          <TrackForm />
        </Suspense>
      </div>
    </div>
  );
}

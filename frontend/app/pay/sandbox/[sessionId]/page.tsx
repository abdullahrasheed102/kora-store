import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { SandboxPayForm } from "@/components/sandbox/sandbox-pay-form";
import { TextSkeleton } from "@/components/skeletons";
import { api, isNotFound } from "@/lib/api";
import { formatPrice } from "@/lib/format";

export const metadata: Metadata = { title: "Sandbox payment", robots: { index: false, follow: false } };

/**
 * The sandbox provider's "hosted payment page". In the Stripe flow this page lives on Stripe's
 * domain; here it's ours, clearly labelled so nobody mistakes it for a real payment.
 */
export default function SandboxPayPage({ params }: PageProps<"/pay/sandbox/[sessionId]">) {
  return (
    <div className="mx-auto max-w-4xl px-4 pt-10 sm:px-6">
      <div
        role="note"
        className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-md border-2 border-dashed border-accent bg-accent/5 px-4 py-3 text-center text-sm"
      >
        <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-white">Sandbox</span>
        <span className="font-medium">Sandbox payment, no real money.</span>
        <span className="text-muted">Nothing is charged, and only the test cards below work. Never enter a real card.</span>
      </div>
      <div className="mt-8">
        <Suspense fallback={<TextSkeleton lines={10} />}>
          <PaymentPage params={params} />
        </Suspense>
      </div>
    </div>
  );
}

async function PaymentPage({ params }: Pick<PageProps<"/pay/sandbox/[sessionId]">, "params">) {
  const { sessionId } = await params;
  const session = await api.sandboxSession(sessionId).catch((error) => {
    if (isNotFound(error)) notFound();
    throw error;
  });

  if (session.status !== "open") {
    const paid = session.status === "complete";
    return (
      <div className="mx-auto max-w-md rounded-lg bg-card p-8 text-center ring-1 ring-line">
        <h1 className="font-serif text-3xl">{paid ? "Already paid" : "This payment page has expired"}</h1>
        <p className="mt-3 text-sm text-muted">
          {paid
            ? `Order ${session.order_number} has been paid.`
            : "Payment links last 30 minutes. Your bag is still saved, so you can check out again."}
        </p>
        <Link
          href={paid ? new URL(session.success_url).pathname + new URL(session.success_url).search : "/checkout"}
          className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent"
        >
          {paid ? "View your order" : "Back to checkout"}
        </Link>
      </div>
    );
  }

  const subtotal = session.line_items.reduce((sum, item) => sum + item.amount_cents, 0);

  return (
    <div className="grid overflow-hidden rounded-lg bg-card ring-1 ring-line md:grid-cols-2">
      <section aria-labelledby="pay-summary" className="bg-paper/60 p-6 sm:p-8">
        <p className="text-sm text-muted">Kora Outfitters · order {session.order_number}</p>
        <h1 id="pay-summary" className="mt-2 font-serif text-4xl">
          {formatPrice(session.amount_total_cents)}
        </h1>
        <ul className="mt-6 space-y-3 text-sm">
          {session.line_items.map((item) => (
            <li key={item.name} className="flex justify-between gap-4">
              <span>
                {item.name} <span className="text-muted">× {item.quantity}</span>
              </span>
              <span>{formatPrice(item.amount_cents)}</span>
            </li>
          ))}
        </ul>
        <dl className="mt-6 space-y-1.5 border-t border-line pt-4 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Subtotal</dt>
            <dd>{formatPrice(subtotal)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">{session.shipping.name}</dt>
            <dd>{session.shipping.amount_cents === 0 ? "Free" : formatPrice(session.shipping.amount_cents)}</dd>
          </div>
          <div className="flex justify-between font-medium">
            <dt>Total due</dt>
            <dd>{formatPrice(session.amount_total_cents)}</dd>
          </div>
        </dl>
        <p className="mt-6 text-xs text-muted">Receipt to {session.email}</p>
      </section>

      <section aria-label="Card details" className="p-6 sm:p-8">
        <h2 className="text-lg font-semibold">Pay with card</h2>
        <div className="mt-4">
          <SandboxPayForm sessionId={session.session_id} total={session.amount_total_cents} defaultName="" />
        </div>
        <Link href="/checkout?cancelled=1" className="mt-4 block text-center text-sm text-muted underline-offset-4 hover:text-ink hover:underline">
          Cancel and return to the store
        </Link>
      </section>
    </div>
  );
}

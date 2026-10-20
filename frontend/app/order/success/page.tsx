import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ClearCart, WaitForPayment } from "@/components/checkout/payment-status";
import { TextSkeleton } from "@/components/skeletons";
import { api, isNotFound } from "@/lib/api";
import { COUNTRY_NAMES, formatDate, formatPrice, paymentSummary, SHIPPING_LABELS } from "@/lib/format";

export const metadata: Metadata = { title: "Thank you", robots: { index: false } };

export default function SuccessPage({ searchParams }: PageProps<"/order/success">) {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-14 sm:px-6">
      <Suspense fallback={<TextSkeleton lines={10} />}>
        <Confirmation searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Confirmation({ searchParams }: Pick<PageProps<"/order/success">, "searchParams">) {
  const { order: orderNumber, session_id: sessionId } = await searchParams;
  if (typeof orderNumber !== "string" || typeof sessionId !== "string") notFound();
  const order = await api.confirmation(orderNumber, sessionId).catch((error) => {
    if (isNotFound(error)) notFound();
    throw error;
  });

  if (order.status === "cancelled") {
    return (
      <div className="text-center">
        <h1 className="font-serif text-4xl tracking-tight">We couldn&apos;t complete order {order.order_number}</h1>
        <p className="mx-auto mt-4 max-w-lg text-muted">{order.status_note ?? "This order was cancelled."}</p>
        <Link href="/cart" className="mt-8 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Back to your bag
        </Link>
      </div>
    );
  }

  // Card orders are confirmed once the payment webhook arrives; cash-on-delivery orders at once.
  const confirmed = order.status !== "pending_payment";
  const isCod = order.payment_method === "cod";
  const address = order.shipping_address;

  return (
    <div>
      {confirmed && <ClearCart />}
      <div className="text-center">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">{confirmed ? "Order confirmed" : "Almost there"}</p>
        <h1 className="mt-4 font-serif text-4xl tracking-tight sm:text-5xl">
          {confirmed ? `Thank you, ${order.customer_name.split(" ")[0]}.` : "Payment received"}
        </h1>
        <p className="mt-4 text-muted">
          Order <span className="font-medium text-ink">{order.order_number}</span> · placed {formatDate(order.created_at)}
        </p>
        <div className="mt-4">
          {confirmed ? (
            <p className="text-sm text-muted">
              {isCod
                ? `Please have ${formatPrice(order.total_cents)} in cash ready when it arrives. We'll ship within 1–2 business days.`
                : "We'll ship within 1–2 business days."}
            </p>
          ) : (
            <WaitForPayment />
          )}
          <p className="mt-3 text-xs text-muted">
            This is a portfolio demonstration store: no payment was taken and nothing will be shipped.
          </p>
        </div>
      </div>

      <section aria-labelledby="summary-heading" className="mt-12 rounded-sm bg-card p-6 ring-1 ring-line sm:p-8">
        <h2 id="summary-heading" className="font-serif text-2xl">
          Order summary
        </h2>
        <ul className="mt-4 divide-y divide-line">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-4 py-3 text-sm">
              <span>
                <span className="font-medium">{item.product_name}</span>
                <span className="block text-muted">
                  {item.color} · {item.size} · Qty {item.quantity}
                </span>
              </span>
              <span>{formatPrice(item.line_total_cents)}</span>
            </li>
          ))}
        </ul>
        <dl className="mt-4 space-y-1.5 border-t border-line pt-4 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Subtotal</dt>
            <dd>{formatPrice(order.subtotal_cents)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Shipping ({SHIPPING_LABELS[order.shipping_method]?.label})</dt>
            <dd>{order.shipping_cents === 0 ? "Free" : formatPrice(order.shipping_cents)}</dd>
          </div>
          <div className="flex justify-between text-base font-medium">
            <dt>{isCod && order.payment_status === "unpaid" ? "Total due on delivery" : "Total paid"}</dt>
            <dd>{formatPrice(order.total_cents)}</dd>
          </div>
          <div className="flex justify-between pt-1.5">
            <dt className="text-muted">Payment</dt>
            <dd>{paymentSummary({ ...order, total_cents: null })}</dd>
          </div>
        </dl>
        <div className="mt-6 border-t border-line pt-4 text-sm">
          <h3 className="font-medium">Shipping to</h3>
          <address className="mt-1 not-italic leading-relaxed text-muted">
            {order.customer_name}, {address.line1}
            {address.line2 && `, ${address.line2}`}, {address.city}
            {address.state && `, ${address.state}`} {address.postal_code}, {COUNTRY_NAMES[address.country] ?? address.country}
          </address>
        </div>
      </section>

      <div className="mt-10 flex flex-wrap justify-center gap-3">
        <Link href="/shop" className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Continue shopping
        </Link>
        <Link href="/account/orders" className="rounded-full border border-ink/20 px-6 py-3 text-sm font-medium hover:border-ink">
          View your orders
        </Link>
      </div>
    </div>
  );
}

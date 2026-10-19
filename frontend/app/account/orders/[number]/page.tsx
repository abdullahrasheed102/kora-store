import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { StatusBadge } from "@/components/account/status-badge";
import { TextSkeleton } from "@/components/skeletons";
import { isNotFound } from "@/lib/api";
import { accountApi, requireCustomer } from "@/lib/api-server";
import { OrderTimeline } from "@/components/orders/order-progress";
import { COUNTRY_NAMES, formatDate, formatPrice, returnStatusLabel, SHIPPING_LABELS } from "@/lib/format";

export const metadata: Metadata = { title: "Order details", robots: { index: false } };

export default function OrderPage({ params }: PageProps<"/account/orders/[number]">) {
  return (
    <Suspense fallback={<TextSkeleton lines={10} />}>
      <Order params={params} />
    </Suspense>
  );
}

async function Order({ params }: Pick<PageProps<"/account/orders/[number]">, "params">) {
  const { number } = await params;
  await requireCustomer(`/account/orders/${number}`);
  const order = await accountApi.order(number).catch((error) => {
    if (isNotFound(error)) notFound();
    throw error;
  });
  const address = order.shipping_address;

  return (
    <div className="space-y-10">
      <div>
        <Link href="/account/orders" className="text-sm text-muted hover:text-ink">
          ← All orders
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h2 className="font-serif text-3xl">{order.order_number}</h2>
          <StatusBadge status={order.status} />
        </div>
        <p className="mt-1 text-sm text-muted">Placed {formatDate(order.created_at)}</p>
        {order.status_note && <p className="mt-3 rounded-sm bg-sage px-4 py-3 text-sm">{order.status_note}</p>}
        {order.status === "delivered" && (
          <Link
            href={`/returns?order=${order.order_number}`}
            className="mt-4 inline-block rounded-full border border-ink/20 px-5 py-2.5 text-sm font-medium hover:border-ink"
          >
            Start a return
          </Link>
        )}
      </div>

      {order.returns.length > 0 && (
        <section aria-labelledby="returns-heading">
          <h3 id="returns-heading" className="border-b border-line pb-3 font-serif text-xl">
            Returns
          </h3>
          <ul className="divide-y divide-line">
            {order.returns.map((request) => (
              <li key={request.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm">
                <span>
                  {request.type === "exchange" ? "Exchange" : "Refund"} ·{" "}
                  {request.items.map((item) => `${item.quantity} × ${item.product_name}`).join(", ")}
                  {request.exchange_details && <span className="block text-muted">{request.exchange_details}</span>}
                </span>
                <span className="font-medium">{returnStatusLabel(request.status)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="items-heading">
        <h3 id="items-heading" className="border-b border-line pb-3 font-serif text-xl">
          Items
        </h3>
        <ul className="divide-y divide-line">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-4 py-4 text-sm">
              <div>
                <p className="font-medium">{item.product_name}</p>
                <p className="text-muted">
                  {item.color} · {item.size} · Qty {item.quantity}
                  {item.is_final_sale && <span className="text-accent"> · Final sale</span>}
                </p>
              </div>
              <p>{formatPrice(item.line_total_cents)}</p>
            </li>
          ))}
        </ul>
        <dl className="ml-auto max-w-xs space-y-1.5 border-t border-line pt-4 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Subtotal</dt>
            <dd>{formatPrice(order.subtotal_cents)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Shipping ({SHIPPING_LABELS[order.shipping_method]?.label})</dt>
            <dd>{order.shipping_cents === 0 ? "Free" : formatPrice(order.shipping_cents)}</dd>
          </div>
          <div className="flex justify-between font-medium">
            <dt>Total</dt>
            <dd>{formatPrice(order.total_cents)}</dd>
          </div>
        </dl>
      </section>

      <div className="grid gap-10 sm:grid-cols-2">
        <section aria-labelledby="shipping-heading">
          <h3 id="shipping-heading" className="border-b border-line pb-3 font-serif text-xl">
            Shipping to
          </h3>
          <address className="mt-4 text-sm not-italic leading-relaxed">
            {order.customer_name}
            <br />
            {address.line1}
            {address.line2 && <>, {address.line2}</>}
            <br />
            {address.city}
            {address.state && `, ${address.state}`} {address.postal_code}
            <br />
            {COUNTRY_NAMES[address.country] ?? address.country}
          </address>
          {order.tracking_number && (
            <p className="mt-4 text-sm">
              {order.carrier} tracking: <span className="font-mono">{order.tracking_number}</span>
            </p>
          )}
          {order.estimated_delivery && (
            <p className="mt-1 text-sm text-muted">Estimated delivery {formatDate(order.estimated_delivery)}</p>
          )}
        </section>

        <section aria-labelledby="timeline-heading">
          <h3 id="timeline-heading" className="border-b border-line pb-3 font-serif text-xl">
            Timeline
          </h3>
          <div className="mt-4">
            <OrderTimeline events={order.events} />
          </div>
        </section>
      </div>
    </div>
  );
}

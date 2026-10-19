import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { StatusBadge } from "@/components/account/status-badge";
import { TextSkeleton } from "@/components/skeletons";
import { isNotFound } from "@/lib/api";
import { accountApi, requireUser } from "@/lib/api-server";
import { COUNTRY_NAMES, formatDate, formatDateTime, formatPrice, SHIPPING_LABELS, statusLabel } from "@/lib/format";

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
  await requireUser(`/account/orders/${number}`);
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
      </div>

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
          <ol className="mt-4 space-y-4 border-l border-line pl-5">
            {[...order.events].reverse().map((event, index) => (
              <li key={`${event.status}-${event.created_at}`} className="relative text-sm">
                <span
                  aria-hidden="true"
                  className={`absolute -left-[25px] top-1.5 size-2.5 rounded-full ${index === 0 ? "bg-accent" : "bg-line"}`}
                />
                <p className="font-medium">{statusLabel(event.status)}</p>
                <p className="text-muted">{formatDateTime(event.created_at)}</p>
                {event.note && <p className="mt-1">{event.note}</p>}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

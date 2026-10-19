import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StatusBadge } from "@/components/account/status-badge";
import { OrderStatusForm } from "@/components/admin/order-status-form";
import { Card } from "@/components/admin/ui";
import { isNotFound } from "@/lib/api";
import { adminApi } from "@/lib/api-server";
import { COUNTRY_NAMES, formatDate, formatDateTime, formatPrice, returnStatusLabel, SHIPPING_LABELS, statusLabel } from "@/lib/format";

export const metadata: Metadata = { title: "Order" };

export default async function AdminOrderPage({ params }: PageProps<"/admin/orders/[number]">) {
  const { number } = await params;
  const order = await adminApi.order(number).catch((error) => {
    if (isNotFound(error)) notFound();
    throw error;
  });
  const address = order.shipping_address;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/admin/orders" className="text-sm text-muted hover:text-ink">← Orders</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-serif text-3xl">{order.order_number}</h1>
          <StatusBadge status={order.status} />
        </div>
        <p className="mt-1 text-sm text-muted">
          Placed {formatDateTime(order.created_at)} · {order.user_id ? "account customer" : "guest"}
        </p>
        {order.status_note && <p className="mt-3 rounded-sm bg-sage px-4 py-2 text-sm">{order.status_note}</p>}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card title="Items">
            <ul className="divide-y divide-line text-sm">
              {order.items.map((item) => (
                <li key={item.id} className="flex justify-between gap-4 py-2">
                  <span>
                    {item.quantity} × {item.product_name} <span className="text-muted">({item.color} · {item.size})</span>
                    {item.is_final_sale && <span className="text-accent-dark"> · final sale</span>}
                  </span>
                  <span className="tabular-nums">{formatPrice(item.line_total_cents)}</span>
                </li>
              ))}
            </ul>
            <dl className="mt-3 space-y-1 border-t border-line pt-3 text-sm">
              <div className="flex justify-between"><dt className="text-muted">Subtotal</dt><dd>{formatPrice(order.subtotal_cents)}</dd></div>
              <div className="flex justify-between">
                <dt className="text-muted">Shipping ({SHIPPING_LABELS[order.shipping_method]?.label})</dt>
                <dd>{order.shipping_cents === 0 ? "Free" : formatPrice(order.shipping_cents)}</dd>
              </div>
              <div className="flex justify-between font-medium"><dt>Total</dt><dd>{formatPrice(order.total_cents)}</dd></div>
            </dl>
          </Card>

          <Card title="Timeline (audit trail)">
            <ol className="space-y-4 border-l border-line pl-5">
              {[...order.events].reverse().map((event, index) => (
                <li key={`${event.created_at}-${index}`} className="relative text-sm">
                  <span aria-hidden="true" className={`absolute -left-[25px] top-1.5 size-2.5 rounded-full ${index === 0 ? "bg-accent" : "bg-line"}`} />
                  <p className="font-medium">
                    {statusLabel(event.status)} <span className="text-xs font-normal text-muted">by {event.created_by}</span>
                  </p>
                  <p className="text-muted">{formatDateTime(event.created_at)}</p>
                  {event.note && <p className="mt-0.5">{event.note}</p>}
                </li>
              ))}
            </ol>
          </Card>

          {order.returns.length > 0 && (
            <Card title="Returns">
              <ul className="divide-y divide-line text-sm">
                {order.returns.map((request) => (
                  <li key={request.id} className="flex justify-between gap-4 py-2">
                    <span>
                      #{request.id} {request.type} · {request.items.map((i) => `${i.quantity} × ${i.product_name}`).join(", ")}
                    </span>
                    <Link href="/admin/returns" className="font-medium hover:text-accent">{returnStatusLabel(request.status)}</Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card title="Update status">
            <OrderStatusForm order={order} />
          </Card>
          <Card title="Customer">
            <p className="text-sm">{order.customer_name}</p>
            <p className="text-sm text-muted">{order.email}</p>
            <address className="mt-3 text-sm not-italic leading-relaxed">
              {address.line1}{address.line2 && `, ${address.line2}`}
              <br />
              {address.city}{address.state && `, ${address.state}`} {address.postal_code}
              <br />
              {COUNTRY_NAMES[address.country] ?? address.country}
            </address>
          </Card>
          <Card title="Shipping and payment">
            <dl className="space-y-2 text-sm">
              <div><dt className="text-muted">Carrier / tracking</dt><dd>{order.carrier ? `${order.carrier} · ${order.tracking_number}` : "Not shipped yet"}</dd></div>
              {order.estimated_delivery && <div><dt className="text-muted">Estimated delivery</dt><dd>{formatDate(order.estimated_delivery)}</dd></div>}
              {order.delivered_at && <div><dt className="text-muted">Delivered</dt><dd>{formatDateTime(order.delivered_at)}</dd></div>}
              <div><dt className="text-muted">Payment</dt><dd className="break-all font-mono text-xs">
                  {order.payment_id ?? (order.status === "pending_payment" ? "Not paid yet" : "No payment reference (demo order)")}
                </dd></div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}

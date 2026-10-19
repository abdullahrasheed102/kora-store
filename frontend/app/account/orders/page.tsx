import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { StatusBadge } from "@/components/account/status-badge";
import { TextSkeleton } from "@/components/skeletons";
import { accountApi, requireUser } from "@/lib/api-server";
import { formatDate, formatPrice } from "@/lib/format";

export const metadata: Metadata = { title: "Your orders", robots: { index: false } };

export default function OrdersPage() {
  return (
    <Suspense fallback={<TextSkeleton lines={6} />}>
      <Orders />
    </Suspense>
  );
}

async function Orders() {
  await requireUser("/account/orders");
  const orders = await accountApi.orders();

  if (orders.length === 0) {
    return (
      <div className="rounded-sm border border-dashed border-line px-6 py-16 text-center">
        <h2 className="font-serif text-2xl">No orders yet</h2>
        <p className="mt-2 text-sm text-muted">Orders you place while logged in will appear here.</p>
      </div>
    );
  }

  return (
    <table className="w-full text-left text-sm">
      <caption className="sr-only">Your orders</caption>
      <thead className="border-b border-line text-xs uppercase tracking-widest text-muted">
        <tr>
          <th scope="col" className="py-3 font-medium">Order</th>
          <th scope="col" className="hidden py-3 font-medium sm:table-cell">Date</th>
          <th scope="col" className="py-3 font-medium">Status</th>
          <th scope="col" className="hidden py-3 font-medium sm:table-cell">Items</th>
          <th scope="col" className="py-3 text-right font-medium">Total</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {orders.map((order) => (
          <tr key={order.order_number}>
            <td className="py-4">
              <Link href={`/account/orders/${order.order_number}`} className="font-medium underline-offset-4 hover:text-accent hover:underline">
                {order.order_number}
              </Link>
            </td>
            <td className="hidden py-4 text-muted sm:table-cell">{formatDate(order.created_at)}</td>
            <td className="py-4">
              <StatusBadge status={order.status} />
            </td>
            <td className="hidden py-4 text-muted sm:table-cell">{order.item_count}</td>
            <td className="py-4 text-right">{formatPrice(order.total_cents)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

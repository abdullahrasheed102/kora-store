import type { Metadata } from "next";
import Form from "next/form";
import Link from "next/link";

import { StatusBadge } from "@/components/account/status-badge";
import { AdminPageHeader, Empty, inputClass, Pager, secondaryButtonClass, tableClass, tdClass, theadClass, thClass } from "@/components/admin/ui";
import { adminApi } from "@/lib/api-server";
import { formatDate, formatPrice, statusLabel } from "@/lib/format";

export const metadata: Metadata = { title: "Orders" };

const STATUSES = ["pending_payment", "processing", "partially_shipped", "shipped", "delayed", "out_for_delivery", "delivered", "returned", "cancelled"];

export default async function AdminOrdersPage({ searchParams }: PageProps<"/admin/orders">) {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q : undefined;
  const status = typeof params.status === "string" && STATUSES.includes(params.status) ? params.status : undefined;
  const page = Number(params.page) > 1 ? Number(params.page) : 1;
  const result = await adminApi.orders({ q, status, page });

  return (
    <div>
      <AdminPageHeader title="Orders" description={`${result.total} ${result.total === 1 ? "order" : "orders"}`} />
      {/* A GET form: filters live in the URL, so a filtered list can be bookmarked or shared. */}
      <Form action="/admin/orders" className="mb-6 flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1">
          <label htmlFor="q" className="text-sm font-medium">Search</label>
          <input id="q" name="q" defaultValue={q} placeholder="Order number, email or name" className={inputClass} />
        </div>
        <div>
          <label htmlFor="status" className="text-sm font-medium">Status</label>
          <select id="status" name="status" defaultValue={status ?? ""} className={inputClass}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
          </select>
        </div>
        <button type="submit" className={secondaryButtonClass}>Filter</button>
      </Form>

      {result.items.length === 0 ? (
        <Empty>No orders match.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className={tableClass}>
            <caption className="sr-only">Orders</caption>
            <thead className={theadClass}>
              <tr>
                <th scope="col" className={thClass}>Order</th>
                <th scope="col" className={thClass}>Customer</th>
                <th scope="col" className={thClass}>Status</th>
                <th scope="col" className={`${thClass} hidden md:table-cell`}>Placed</th>
                <th scope="col" className={`${thClass} text-right`}>Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {result.items.map((order) => (
                <tr key={order.order_number}>
                  <td className={tdClass}>
                    <Link href={`/admin/orders/${order.order_number}`} className="font-medium underline-offset-4 hover:text-accent hover:underline">
                      {order.order_number}
                    </Link>
                  </td>
                  <td className={tdClass}>
                    {order.customer_name}
                    <span className="block text-xs text-muted">{order.email}</span>
                  </td>
                  <td className={tdClass}><StatusBadge status={order.status} /></td>
                  <td className={`${tdClass} hidden text-muted md:table-cell`}>{formatDate(order.created_at)}</td>
                  <td className={`${tdClass} text-right tabular-nums`}>{formatPrice(order.total_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager basePath="/admin/orders" params={{ q, status }} page={result.page} totalPages={result.total_pages} />
    </div>
  );
}

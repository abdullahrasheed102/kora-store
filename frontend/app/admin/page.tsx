import type { Metadata } from "next";
import Link from "next/link";

import { RevenueChart } from "@/components/admin/revenue-chart";
import { AdminPageHeader, Card, StatTile } from "@/components/admin/ui";
import { StatusBadge } from "@/components/account/status-badge";
import { adminApi } from "@/lib/api-server";
import { formatPrice } from "@/lib/format";
import type { OrderStatus } from "@/lib/types";

export const metadata: Metadata = { title: "Dashboard" };

const STATUS_ORDER: OrderStatus[] = [
  "pending_payment", "processing", "partially_shipped", "shipped", "delayed", "out_for_delivery", "delivered",
  "returned", "cancelled",
];

// Rendered inside the admin layout's gate (already inside <Suspense>), so it can read data directly.
export default async function AdminDashboard() {
  const stats = await adminApi.stats();
  const statusTotal = Object.values(stats.orders_by_status).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <AdminPageHeader title="Dashboard" description="Paid orders only (pending and cancelled orders don't count as revenue)." />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-sm bg-card p-5 ring-1 ring-line sm:col-span-2">
          <p className="text-sm text-muted">Revenue, last 30 days</p>
          {/* The one hero figure on the page: large, sans-serif, default proportional digits. */}
          <p className="mt-1 text-5xl font-semibold tracking-tight">{formatPrice(stats.revenue_30d_cents)}</p>
          <p className="mt-2 text-sm text-muted">
            {stats.orders_30d} orders · average {formatPrice(stats.average_order_30d_cents)} · last 7 days{" "}
            {formatPrice(stats.revenue_7d_cents)}
          </p>
        </div>
        <StatTile label="Orders to ship" value={String(stats.orders_to_ship)} hint="Processing or partly shipped" href="/admin/orders?status=processing" />
        <div className="grid gap-4">
          <StatTile label="Open returns" value={String(stats.open_returns)} href="/admin/returns" />
          <StatTile label="Open tickets" value={String(stats.open_tickets)} href="/admin/tickets" />
        </div>
      </div>

      <Card title="Daily revenue, last 30 days">
        <RevenueChart days={stats.daily_revenue} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Orders by status">
          <ul className="divide-y divide-line text-sm">
            {STATUS_ORDER.map((status) => (
              <li key={status}>
                <Link href={`/admin/orders?status=${status}`} className="flex items-center justify-between py-2 hover:text-accent">
                  <StatusBadge status={status} />
                  <span className="tabular-nums">{stats.orders_by_status[status]}</span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">{statusTotal} orders in total</p>
        </Card>

        <Card title={`Low stock (${stats.low_stock_threshold} or fewer left)`}>
          {stats.low_stock.length === 0 ? (
            <p className="text-sm text-muted">Everything is well stocked.</p>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {stats.low_stock.map((item) => (
                <li key={item.variant_id}>
                  <Link href={`/admin/products/${item.product_id}`} className="flex items-center justify-between gap-4 py-2 hover:text-accent">
                    <span>
                      {item.product_name} <span className="text-muted">({item.color} · {item.size})</span>
                    </span>
                    <span className={`tabular-nums ${item.stock === 0 ? "font-semibold text-accent-dark" : ""}`}>
                      {item.stock === 0 ? "Sold out" : `${item.stock} left`}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

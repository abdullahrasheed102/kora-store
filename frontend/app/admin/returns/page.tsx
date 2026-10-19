import type { Metadata } from "next";
import Link from "next/link";

import { ReturnActions } from "@/components/admin/return-actions";
import { AdminPageHeader, Empty, Pager } from "@/components/admin/ui";
import { adminApi } from "@/lib/api-server";
import { formatDate, formatPrice, returnStatusLabel } from "@/lib/format";

export const metadata: Metadata = { title: "Returns" };

const FILTERS = ["requested", "approved", "label_sent", "received", "refunded", "rejected"];

export default async function AdminReturnsPage({ searchParams }: PageProps<"/admin/returns">) {
  const params = await searchParams;
  const status = typeof params.status === "string" && FILTERS.includes(params.status) ? params.status : undefined;
  const page = Number(params.page) > 1 ? Number(params.page) : 1;
  const result = await adminApi.returns({ status, page });

  return (
    <div>
      <AdminPageHeader title="Returns" description="Approve → label sent → received (puts stock back) → refund. Exchanges finish at received." />
      <nav aria-label="Filter returns" className="mb-6 flex flex-wrap gap-2 text-sm">
        {[undefined, ...FILTERS].map((filter) => (
          <Link key={filter ?? "all"} href={filter ? `/admin/returns?status=${filter}` : "/admin/returns"}
            aria-current={filter === status ? "page" : undefined}
            className={`rounded-full px-3 py-1.5 ring-1 ring-line ${filter === status ? "bg-ink text-paper" : "hover:ring-ink/40"}`}>
            {filter ? returnStatusLabel(filter) : "All"}
          </Link>
        ))}
      </nav>
      {result.items.length === 0 ? (
        <Empty>No returns here.</Empty>
      ) : (
        <ul className="space-y-4">
          {result.items.map((request) => (
            <li key={request.id} className="rounded-sm bg-card p-5 ring-1 ring-line">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-medium">
                    #{request.id} · {request.type === "exchange" ? "Exchange" : `Refund ${formatPrice(request.refund_estimate_cents)}`} ·{" "}
                    <Link href={`/admin/orders/${request.order_number}`} className="underline underline-offset-4 hover:text-accent">
                      {request.order_number}
                    </Link>
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {request.customer_name} ({request.email}) · {formatDate(request.created_at)} · started by {request.created_by}
                  </p>
                  <p className="mt-2 text-sm">{request.items.map((i) => `${i.quantity} × ${i.product_name} (${i.color} · ${i.size})`).join(", ")}</p>
                  {request.exchange_details && <p className="text-sm">{request.exchange_details}</p>}
                  <p className="mt-1 text-sm text-muted">Reason: {request.reason}</p>
                  <p className="text-xs text-muted">
                    {request.return_shipping === "prepaid_label" ? "Free prepaid label (US)" : "Customer pays return shipping"}
                  </p>
                </div>
                <span className="rounded-full bg-line px-2.5 py-1 text-xs font-medium">{returnStatusLabel(request.status)}</span>
              </div>
              <div className="mt-4 border-t border-line pt-4">
                <ReturnActions request={request} />
              </div>
            </li>
          ))}
        </ul>
      )}
      <Pager basePath="/admin/returns" params={{ status }} page={result.page} totalPages={result.total_pages} />
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { TicketControls } from "@/components/admin/ticket-controls";
import { AdminPageHeader, Empty, Pager } from "@/components/admin/ui";
import { adminApi } from "@/lib/api-server";
import { formatDateTime } from "@/lib/format";

export const metadata: Metadata = { title: "Tickets" };

const FILTERS = [
  { value: undefined, label: "All" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "closed", label: "Closed" },
];

export default async function AdminTicketsPage({ searchParams }: PageProps<"/admin/tickets">) {
  const params = await searchParams;
  const status = typeof params.status === "string" && ["open", "in_progress", "closed"].includes(params.status) ? params.status : undefined;
  const page = Number(params.page) > 1 ? Number(params.page) : 1;
  const result = await adminApi.tickets({ status, page });

  return (
    <div>
      <AdminPageHeader title="Support tickets" description="Open work first, most urgent first. From the contact form now; from the AI assistant in phase 8." />
      <nav aria-label="Filter tickets" className="mb-6 flex flex-wrap gap-2 text-sm">
        {FILTERS.map((filter) => (
          <Link key={filter.label} href={filter.value ? `/admin/tickets?status=${filter.value}` : "/admin/tickets"}
            aria-current={filter.value === status ? "page" : undefined}
            className={`rounded-full px-3 py-1.5 ring-1 ring-line ${filter.value === status ? "bg-ink text-paper" : "hover:ring-ink/40"}`}>
            {filter.label}
          </Link>
        ))}
      </nav>
      {result.items.length === 0 ? (
        <Empty>No tickets. Messages sent from the <Link href="/contact" className="underline">contact page</Link> appear here.</Empty>
      ) : (
        <ul className="space-y-4">
          {result.items.map((ticket) => (
            <li key={ticket.id} className={`rounded-sm bg-card p-5 ring-1 ring-line ${ticket.status === "closed" ? "opacity-70" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-medium">#{ticket.id} · {ticket.subject}</p>
                  <p className="mt-1 text-sm text-muted">
                    {ticket.name} ({ticket.email}) · {formatDateTime(ticket.created_at)} · via {ticket.source.replace("_", " ")}
                    {ticket.order_number && (
                      <>
                        {" "}·{" "}
                        <Link href={`/admin/orders/${ticket.order_number}`} className="underline underline-offset-4">{ticket.order_number}</Link>
                      </>
                    )}
                  </p>
                </div>
                <TicketControls ticket={ticket} />
              </div>
              <p className="mt-3 whitespace-pre-line text-sm leading-relaxed">{ticket.summary}</p>
            </li>
          ))}
        </ul>
      )}
      <Pager basePath="/admin/tickets" params={{ status }} page={result.page} totalPages={result.total_pages} />
    </div>
  );
}

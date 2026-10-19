"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { api } from "@/lib/api";
import type { Ticket } from "@/lib/types";

const selectClass = "h-9 rounded-full border border-line bg-paper px-3 text-xs";

export function TicketControls({ ticket }: { ticket: Ticket }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const update = async (body: { status?: string; priority?: string }) => {
    await api.admin.updateTicket(ticket.id, body);
    startTransition(() => router.refresh());
  };
  return (
    <div className={`flex flex-wrap gap-2 ${isPending ? "opacity-60" : ""}`}>
      <label className="sr-only" htmlFor={`status-${ticket.id}`}>Status</label>
      <select id={`status-${ticket.id}`} value={ticket.status} onChange={(e) => update({ status: e.target.value })} className={selectClass}>
        <option value="open">Open</option>
        <option value="in_progress">In progress</option>
        <option value="closed">Closed</option>
      </select>
      <label className="sr-only" htmlFor={`priority-${ticket.id}`}>Priority</label>
      <select id={`priority-${ticket.id}`} value={ticket.priority} onChange={(e) => update({ priority: e.target.value })} className={selectClass}>
        <option value="urgent">Urgent</option>
        <option value="high">High</option>
        <option value="normal">Normal</option>
        <option value="low">Low</option>
      </select>
    </div>
  );
}

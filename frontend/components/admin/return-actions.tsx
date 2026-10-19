"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { secondaryButtonClass } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import type { AdminReturn } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  approved: "Approve",
  label_sent: "Mark label sent",
  received: "Mark received (restocks)",
  refunded: "Refund",
  rejected: "Reject",
};

/** One button per move the backend allows next for this return. */
export function ReturnActions({ request }: { request: AdminReturn }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function act(status: string) {
    let note: string | undefined;
    if (status === "rejected") {
      note = window.prompt("Why is this return rejected? The customer will see this.")?.trim();
      if (!note) return;
    }
    if (status === "refunded" && !window.confirm(`Refund ${formatPrice(request.refund_estimate_cents)} to the customer?`)) return;
    setError(null);
    try {
      await api.admin.updateReturnStatus(request.id, { status, note });
      startTransition(() => router.refresh());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    }
  }

  if (request.allowed_next_statuses.length === 0) return <span className="text-xs text-muted">Done</span>;
  return (
    <div className={`flex flex-wrap gap-2 ${isPending ? "opacity-60" : ""}`}>
      {request.allowed_next_statuses.map((status) => (
        <button key={status} type="button" onClick={() => act(status)} disabled={isPending}
          className={`${secondaryButtonClass} ${status === "rejected" ? "text-accent-dark" : ""}`}>
          {status === "refunded" ? `Refund ${formatPrice(request.refund_estimate_cents)}` : ACTION_LABELS[status]}
        </button>
      ))}
      {error && <p role="alert" className="w-full text-sm text-accent-dark">{error}</p>}
    </div>
  );
}

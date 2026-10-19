"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { buttonClass, inputClass } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/api";
import { statusLabel } from "@/lib/format";
import type { AdminOrder, OrderStatus } from "@/lib/types";

const NEEDS_TRACKING: OrderStatus[] = ["shipped", "partially_shipped"];

/** Only offers the moves the backend's state machine allows (allowed_next_statuses). */
export function OrderStatusForm({ order }: { order: AdminOrder }) {
  const router = useRouter();
  const [target, setTarget] = useState<OrderStatus | "">("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  if (order.allowed_next_statuses.length === 0) {
    return <p className="text-sm text-muted">No further status changes: this order is {statusLabel(order.status).toLowerCase()}.</p>;
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim() || undefined;
    setError(null);
    if (target === "cancelled" && !window.confirm(order.status === "processing"
      ? "Cancel this order? Its stock goes back on sale and the customer is refunded in full."
      : "Cancel this unpaid order?")) return;
    try {
      await api.admin.updateOrderStatus(order.order_number, {
        status: target,
        note: text("note"),
        carrier: text("carrier"),
        tracking_number: text("tracking_number"),
        estimated_delivery: text("estimated_delivery"),
      });
      setTarget("");
      (event.target as HTMLFormElement).reset();
      startTransition(() => router.refresh());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    }
  }

  return (
    <form onSubmit={submit} className={`space-y-4 ${isPending ? "opacity-60" : ""}`}>
      <div>
        <label htmlFor="status" className="text-sm font-medium">New status</label>
        <select id="status" required value={target} onChange={(e) => setTarget(e.target.value as OrderStatus)} className={inputClass}>
          <option value="">Choose…</option>
          {order.allowed_next_statuses.map((status) => (
            <option key={status} value={status}>{statusLabel(status)}</option>
          ))}
        </select>
      </div>
      {NEEDS_TRACKING.includes(target as OrderStatus) && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="carrier" className="text-sm font-medium">Carrier</label>
            <input id="carrier" name="carrier" defaultValue={order.carrier ?? ""} required className={inputClass} placeholder="USPS" />
          </div>
          <div>
            <label htmlFor="tracking_number" className="text-sm font-medium">Tracking number</label>
            <input id="tracking_number" name="tracking_number" defaultValue={order.tracking_number ?? ""} required className={inputClass} />
          </div>
        </div>
      )}
      {target && target !== "cancelled" && target !== "delivered" && (
        <div>
          <label htmlFor="estimated_delivery" className="text-sm font-medium">Estimated delivery (optional)</label>
          <input id="estimated_delivery" name="estimated_delivery" type="date" defaultValue={order.estimated_delivery ?? ""} className={inputClass} />
        </div>
      )}
      <div>
        <label htmlFor="note" className="text-sm font-medium">
          Note for the customer {target === "delayed" ? "(required)" : "(optional)"}
        </label>
        <input id="note" name="note" required={target === "delayed"} maxLength={500} className={inputClass}
          placeholder={target === "delayed" ? "e.g. Carrier weather delay." : ""} />
        <p className="mt-1 text-xs text-muted">Shown on the tracking page and recorded in the timeline.</p>
      </div>
      {error && <p role="alert" className="rounded-sm bg-accent/10 px-3 py-2 text-sm text-accent-dark">{error}</p>}
      <button type="submit" disabled={!target || isPending} className={buttonClass}>Update status</button>
    </form>
  );
}

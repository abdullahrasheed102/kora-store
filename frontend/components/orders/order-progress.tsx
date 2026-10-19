import { formatDateTime, statusLabel } from "@/lib/format";
import type { OrderStatus } from "@/lib/types";

const STEPS = ["Ordered", "Processing", "Shipped", "Out for delivery", "Delivered"];

// Where each status sits on the progress bar.
const STEP_FOR: Record<OrderStatus, number> = {
  pending_payment: 0,
  processing: 1,
  partially_shipped: 2,
  shipped: 2,
  delayed: 2,
  out_for_delivery: 3,
  delivered: 4,
  returned: 4,
  cancelled: 0,
};

/** A five-step progress bar. Cancelled orders don't get a bar; delays are shown in accent colour. */
export function OrderProgress({ status }: { status: OrderStatus }) {
  if (status === "cancelled") return null;
  const current = STEP_FOR[status];
  const warning = status === "delayed" || status === "partially_shipped";
  return (
    <ol className="grid grid-cols-5 gap-2" aria-label={`Order progress: ${statusLabel(status)}`}>
      {STEPS.map((step, index) => {
        const done = index <= current;
        return (
          <li key={step} aria-current={index === current ? "step" : undefined}>
            <div
              className={`h-1.5 rounded-full ${done ? (warning && index === current ? "bg-accent" : "bg-ink") : "bg-line"}`}
            />
            <p className={`mt-2 text-xs sm:text-sm ${done ? "font-medium text-ink" : "text-muted"}`}>
              {index === current && status !== STATUS_OF_STEP[index] ? statusLabel(status) : step}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

const STATUS_OF_STEP: OrderStatus[] = ["pending_payment", "processing", "shipped", "out_for_delivery", "delivered"];

/** Newest first, with a dot for each event; the latest one is highlighted. */
export function OrderTimeline({ events }: { events: { status: OrderStatus; note: string | null; created_at: string }[] }) {
  return (
    <ol className="space-y-5 border-l border-line pl-5">
      {[...events].reverse().map((event, index) => (
        <li key={`${event.status}-${event.created_at}-${index}`} className="relative text-sm">
          <span aria-hidden="true" className={`absolute -left-[25px] top-1.5 size-2.5 rounded-full ${index === 0 ? "bg-accent" : "bg-line"}`} />
          <p className="font-medium">{statusLabel(event.status)}</p>
          <p className="text-muted">{formatDateTime(event.created_at)}</p>
          {event.note && <p className="mt-1">{event.note}</p>}
        </li>
      ))}
    </ol>
  );
}

import { statusLabel } from "@/lib/format";
import type { OrderStatus } from "@/lib/types";

const TONES: Partial<Record<OrderStatus, string>> = {
  delivered: "bg-sage text-ink",
  cancelled: "bg-line text-muted",
  returned: "bg-line text-muted",
  delayed: "bg-accent/15 text-accent-dark",
  pending_payment: "bg-accent/15 text-accent-dark",
};

export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${TONES[status] ?? "bg-ink/5 text-ink"}`}>
      {statusLabel(status)}
    </span>
  );
}

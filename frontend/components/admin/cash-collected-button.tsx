"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { buttonClass } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import type { AdminOrder } from "@/lib/types";

/** Cash on delivery: record that the courier handed over the cash (writes an order event). */
export function CashCollectedButton({ order }: { order: AdminOrder }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function collect() {
    if (!window.confirm(`Record ${formatPrice(order.total_cents)} in cash as collected for ${order.order_number}?`)) return;
    setError(null);
    try {
      await api.admin.markCashCollected(order.order_number);
      startTransition(() => router.refresh());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong.");
    }
  }

  return (
    <div className="mt-3">
      <button type="button" onClick={collect} disabled={isPending} className={buttonClass}>
        Mark cash collected
      </button>
      {error && <p role="alert" className="mt-2 text-sm text-accent-dark">{error}</p>}
    </div>
  );
}

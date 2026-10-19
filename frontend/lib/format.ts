const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usdWhole = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

/** Money is integer cents everywhere; we only turn it into dollars for display. */
export function formatPrice(cents: number): string {
  return cents % 100 === 0 ? usdWhole.format(cents / 100) : usd.format(cents / 100);
}

export function formatPriceRange(minCents: number, maxCents: number): string {
  return minCents === maxCents ? formatPrice(minCents) : `${formatPrice(minCents)} – ${formatPrice(maxCents)}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

const STATUS_LABELS: Record<string, string> = {
  pending_payment: "Awaiting payment",
  processing: "Processing",
  shipped: "Shipped",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  delayed: "Delayed",
  partially_shipped: "Partially shipped",
  cancelled: "Cancelled",
  returned: "Returned",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export const SHIPPING_LABELS: Record<string, { label: string; detail: string }> = {
  standard: { label: "Standard", detail: "3–6 business days · free over $75" },
  express: { label: "Express", detail: "2 business days" },
  international: { label: "International", detail: "UK, Canada, Australia · 7–14 business days" },
};

export const COUNTRY_NAMES: Record<string, string> = {
  US: "United States",
  GB: "United Kingdom",
  CA: "Canada",
  AU: "Australia",
};

"use client";

import { useRouter } from "next/navigation";

import { shopHref, SORT_OPTIONS, type ShopFilters } from "@/lib/shop-url";

export function SortSelect({ category, filters }: { category?: string; filters: ShopFilters }) {
  const router = useRouter();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="sort" className="text-sm text-muted">
        Sort
      </label>
      <select
        id="sort"
        value={filters.sort ?? "best_selling"}
        onChange={(event) =>
          router.push(shopHref(category, { ...filters, sort: event.target.value as ShopFilters["sort"], page: undefined }), {
            scroll: false,
          })
        }
        className="h-10 rounded-full border border-line bg-card px-4 pr-8 text-sm"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// Shop filters live in the URL (/shop/tops?size=M&sort=price_asc), so filtered pages can be
// shared and bookmarked, and the back button works. These helpers read and write that URL.
import { toSearchParams } from "@/lib/api";
import { TAG_LABELS } from "@/lib/site";
import type { ProductQuery, SortOption } from "@/lib/types";

export type ShopFilters = Omit<ProductQuery, "category" | "per_page">;

export const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "best_selling", label: "Best selling" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "name_asc", label: "Name: A–Z" },
];

export const PRICE_RANGES: { label: string; min?: number; max?: number }[] = [
  { label: "Under $50", max: 4999 },
  { label: "$50 – $100", min: 5000, max: 9999 },
  { label: "$100 – $150", min: 10000, max: 14999 },
  { label: "$150 and up", min: 15000 },
];

type RawParams = Record<string, string | string[] | undefined>;

const asList = (value: string | string[] | undefined) =>
  value === undefined ? [] : (Array.isArray(value) ? value : [value]).filter(Boolean);
const asFirst = (value: string | string[] | undefined) => asList(value)[0];
const TAG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const asNumber = (value: string | string[] | undefined) => {
  const number = Number(asFirst(value));
  return Number.isInteger(number) && number >= 0 ? number : undefined;
};

export function parseShopFilters(params: RawParams): ShopFilters {
  const sort = asFirst(params.sort);
  return {
    q: asFirst(params.q)?.trim() || undefined,
    // Only well-formed tags reach the API (it would refuse anything else with a 400).
    tag: TAG_PATTERN.test(asFirst(params.tag) ?? "") ? asFirst(params.tag) : undefined,
    size: asList(params.size),
    color: asList(params.color),
    min_price: asNumber(params.min_price),
    max_price: asNumber(params.max_price),
    sort: SORT_OPTIONS.some((option) => option.value === sort) ? (sort as SortOption) : undefined,
    page: asNumber(params.page),
  };
}

export function shopHref(category: string | undefined, filters: ShopFilters): string {
  const path = category ? `/shop/${category}` : "/shop";
  // Default values are left out to keep URLs short.
  const query = toSearchParams({
    ...filters,
    sort: filters.sort === "best_selling" ? undefined : filters.sort,
    page: filters.page && filters.page > 1 ? filters.page : undefined,
  }).toString();
  return query ? `${path}?${query}` : path;
}

export function hasActiveFilters(filters: ShopFilters): boolean {
  return Boolean(
    filters.size?.length || filters.color?.length || filters.min_price !== undefined || filters.max_price !== undefined,
  );
}

/** "autumn-edit" → "The Autumn Edit" for known tags; any other tag → "Tag: spring-sale". */
export function tagLabel(tag: string): string {
  return TAG_LABELS[tag] ?? `Tag: ${tag}`;
}

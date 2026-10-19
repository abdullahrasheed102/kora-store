import Link from "next/link";
import { notFound } from "next/navigation";

import { ChevronIcon } from "@/components/icons";
import { ProductGrid } from "@/components/product-card";
import { FilterPanel, MobileFilters } from "@/components/shop/filter-panel";
import { Pagination } from "@/components/shop/pagination";
import { SortSelect } from "@/components/shop/sort-select";
import { api, isNotFound } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { hasActiveFilters, shopHref, type ShopFilters } from "@/lib/shop-url";

const PER_PAGE = 12;

/** Fetches and renders one page of the shop. Used by /shop and /shop/[category]. */
export async function ShopResults({ category, filters }: { category?: string; filters: ShopFilters }) {
  // Both requests start at the same time instead of one after the other.
  const [result, categories] = await Promise.all([
    api.products({ ...filters, category, per_page: PER_PAGE }).catch((error) => {
      if (isNotFound(error)) notFound(); // unknown category slug
      throw error;
    }),
    api.categories(),
  ]);

  const current = categories.find((item) => item.slug === category);
  const title = filters.q ? `Results for “${filters.q}”` : (current?.name ?? "Shop all");
  const chips = activeChips(category, filters);

  return (
    <>
      <nav aria-label="Breadcrumb" className="text-sm text-muted">
        <ol className="flex items-center gap-1.5">
          <li>
            <Link href="/" className="hover:text-ink">
              Home
            </Link>
          </li>
          <ChevronIcon className="size-3.5" />
          <li>
            {current ? (
              <Link href="/shop" className="hover:text-ink">
                Shop
              </Link>
            ) : (
              <span aria-current="page">Shop</span>
            )}
          </li>
          {current && (
            <>
              <ChevronIcon className="size-3.5" />
              <li aria-current="page">{current.name}</li>
            </>
          )}
        </ol>
      </nav>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
        <div>
          <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">{title}</h1>
          <p className="mt-2 text-sm text-muted" aria-live="polite">
            {result.total} {result.total === 1 ? "product" : "products"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <MobileFilters category={category} categories={categories} facets={result.facets} filters={filters} />
          <SortSelect category={category} filters={filters} />
        </div>
      </div>

      <div className="mt-8 grid gap-10 lg:grid-cols-[220px_1fr]">
        <aside aria-label="Filters" className="hidden lg:block">
          <FilterPanel category={category} categories={categories} facets={result.facets} filters={filters} />
        </aside>

        <div>
          {chips.length > 0 && (
            <ul className="mb-6 flex flex-wrap gap-2" aria-label="Active filters">
              {chips.map((chip) => (
                <li key={chip.label}>
                  <Link
                    href={chip.href}
                    className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-3 py-1.5 text-xs hover:border-ink"
                  >
                    {chip.label}
                    <span aria-hidden="true">×</span>
                    <span className="sr-only">(remove filter)</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {result.items.length > 0 ? (
            <>
              <ProductGrid products={result.items} priorityCount={4} />
              <Pagination category={category} filters={filters} page={result.page} totalPages={result.total_pages} />
            </>
          ) : (
            <EmptyState category={category} filters={filters} />
          )}
        </div>
      </div>
    </>
  );
}

function activeChips(category: string | undefined, filters: ShopFilters): { label: string; href: string }[] {
  const without = (changes: Partial<ShopFilters>) => shopHref(category, { ...filters, ...changes, page: undefined });
  const chips = [
    ...(filters.size ?? []).map((size) => ({
      label: `Size: ${size}`,
      href: without({ size: filters.size?.filter((item) => item !== size) }),
    })),
    ...(filters.color ?? []).map((color) => ({
      label: color,
      href: without({ color: filters.color?.filter((item) => item !== color) }),
    })),
  ];
  if (filters.min_price !== undefined || filters.max_price !== undefined) {
    const label =
      filters.max_price === undefined
        ? `${formatPrice(filters.min_price ?? 0)} and up`
        : `${formatPrice(filters.min_price ?? 0)} – ${formatPrice(filters.max_price + 1)}`;
    chips.push({ label, href: without({ min_price: undefined, max_price: undefined }) });
  }
  if (filters.q) chips.push({ label: `“${filters.q}”`, href: without({ q: undefined }) });
  return chips;
}

function EmptyState({ category, filters }: { category?: string; filters: ShopFilters }) {
  const filtered = hasActiveFilters(filters) || Boolean(filters.q);
  return (
    <div className="rounded-sm border border-dashed border-line px-6 py-20 text-center">
      <h2 className="font-serif text-2xl">Nothing here yet</h2>
      <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
        {filtered
          ? "No products match these filters. Try removing one, or search for something else."
          : "There are no products on this page."}
      </p>
      <Link
        href={shopHref(category, filtered ? { sort: filters.sort } : {})}
        className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent"
      >
        {filtered ? "Clear filters" : "Back to page 1"}
      </Link>
    </div>
  );
}

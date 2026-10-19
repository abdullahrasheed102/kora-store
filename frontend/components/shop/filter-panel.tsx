"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";

import { CloseIcon, FilterIcon } from "@/components/icons";
import { isLightColor, swatchColor } from "@/lib/colors";
import { hasActiveFilters, PRICE_RANGES, shopHref, type ShopFilters } from "@/lib/shop-url";
import type { Category, Facets } from "@/lib/types";

type Props = { category?: string; categories: Category[]; facets: Facets; filters: ShopFilters };

const COLORS_COLLAPSED = 8;

/**
 * Filter controls. They don't hold any state of their own: every change builds a new URL and
 * navigates to it. The server then renders the matching products. The URL is the state.
 */
export function FilterPanel({ category, categories, facets, filters }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [showAllColors, setShowAllColors] = useState(false);
  // Long colour lists are collapsed, but a selected colour is always visible.
  const visibleColors = showAllColors
    ? facets.colors
    : facets.colors.filter((color, index) => index < COLORS_COLLAPSED || filters.color?.includes(color));

  const apply = (changes: Partial<ShopFilters>) => {
    startTransition(() => {
      router.push(shopHref(category, { ...filters, ...changes, page: undefined }), { scroll: false });
    });
  };
  const toggle = (list: string[] = [], value: string) =>
    list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

  return (
    <div className={`space-y-9 text-sm transition-opacity ${isPending ? "opacity-60" : ""}`} aria-busy={isPending}>
      <section>
        <h2 className="text-xs font-medium uppercase tracking-widest text-muted">Category</h2>
        <ul className="mt-3 space-y-2">
          <li>
            <Link
              href={shopHref(undefined, { q: filters.q, sort: filters.sort })}
              aria-current={!category ? "page" : undefined}
              className={!category ? "font-semibold text-ink" : "text-ink/75 hover:text-ink"}
            >
              All products
            </Link>
          </li>
          {categories.map((item) => (
            <li key={item.slug} className="flex justify-between">
              <Link
                href={shopHref(item.slug, { q: filters.q, sort: filters.sort })}
                aria-current={item.slug === category ? "page" : undefined}
                className={item.slug === category ? "font-semibold text-ink" : "text-ink/75 hover:text-ink"}
              >
                {item.name}
              </Link>
              <span className="text-muted">{item.product_count}</span>
            </li>
          ))}
        </ul>
      </section>

      {facets.sizes.length > 0 && (
        <fieldset>
          <legend className="text-xs font-medium uppercase tracking-widest text-muted">Size</legend>
          <div className="mt-3 flex flex-wrap gap-2">
            {facets.sizes.map((size) => {
              const checked = filters.size?.includes(size) ?? false;
              return (
                <label key={size} className="cursor-pointer">
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={checked}
                    onChange={() => apply({ size: toggle(filters.size, size) })}
                  />
                  <span className="inline-flex h-9 min-w-11 items-center justify-center rounded-full border border-line bg-card px-3 text-xs transition peer-checked:border-ink peer-checked:bg-ink peer-checked:text-paper peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent hover:border-ink/50">
                    {size}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      )}

      {facets.colors.length > 0 && (
        <fieldset>
          <legend className="text-xs font-medium uppercase tracking-widest text-muted">Colour</legend>
          <div className="mt-3 grid grid-cols-1 gap-2">
            {visibleColors.map((color) => {
              const checked = filters.color?.includes(color) ?? false;
              const hex = swatchColor(color);
              return (
                <label key={color} className="flex cursor-pointer items-center gap-2.5">
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={checked}
                    onChange={() => apply({ color: toggle(filters.color, color) })}
                  />
                  <span
                    className="flex size-5 items-center justify-center rounded-full ring-1 ring-ink/20 ring-offset-2 ring-offset-paper peer-checked:ring-2 peer-checked:ring-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-accent"
                    style={{ backgroundColor: hex }}
                  >
                    {checked && (
                      <svg viewBox="0 0 12 12" className="size-3" aria-hidden="true">
                        <path d="m2.5 6 2.5 2.5 4.5-5" fill="none" stroke={isLightColor(hex) ? "#1f1b16" : "#fff"} strokeWidth="1.8" />
                      </svg>
                    )}
                  </span>
                  <span className={checked ? "font-medium" : "text-ink/80"}>{color}</span>
                </label>
              );
            })}
          </div>
          {facets.colors.length > visibleColors.length && (
            <button
              type="button"
              onClick={() => setShowAllColors(true)}
              className="mt-3 text-sm font-medium underline underline-offset-4 hover:text-accent"
            >
              Show all {facets.colors.length} colours
            </button>
          )}
        </fieldset>
      )}

      <fieldset>
        <legend className="text-xs font-medium uppercase tracking-widest text-muted">Price</legend>
        <div className="mt-3 space-y-2">
          {[{ label: "Any price" }, ...PRICE_RANGES].map((range) => {
            const checked = filters.min_price === range.min && filters.max_price === range.max;
            return (
              <label key={range.label} className="flex cursor-pointer items-center gap-2.5">
                <input
                  type="radio"
                  name="price"
                  checked={checked}
                  onChange={() => apply({ min_price: range.min, max_price: range.max })}
                  className="size-4 accent-ink"
                />
                <span className={checked ? "font-medium" : "text-ink/80"}>{range.label}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {hasActiveFilters(filters) && (
        <button
          type="button"
          onClick={() => apply({ size: [], color: [], min_price: undefined, max_price: undefined })}
          className="text-sm font-medium underline underline-offset-4 hover:text-accent"
        >
          Clear all filters
        </button>
      )}
    </div>
  );
}

/** On small screens the same panel opens in a slide-in dialog. */
export function MobileFilters(props: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const count = (props.filters.size?.length ?? 0) + (props.filters.color?.length ?? 0) + (props.filters.min_price !== undefined || props.filters.max_price !== undefined ? 1 : 0);

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => dialog.current?.showModal()}
        className="inline-flex h-10 items-center gap-2 rounded-full border border-line bg-card px-4 text-sm"
      >
        <FilterIcon />
        Filters{count > 0 && ` (${count})`}
      </button>
      <dialog
        ref={dialog}
        aria-label="Filters"
        className="ml-auto mr-0 h-dvh max-h-none w-[min(22rem,90vw)] max-w-none bg-paper p-0 text-ink backdrop:bg-ink/40"
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current.close();
        }}
      >
        <div className="flex h-16 items-center justify-between border-b border-line px-5">
          <h2 className="font-serif text-xl">Filters</h2>
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            className="inline-flex size-10 items-center justify-center rounded-full hover:bg-line/60"
            aria-label="Close filters"
          >
            <CloseIcon />
          </button>
        </div>
        <div className="p-5">
          <FilterPanel {...props} />
        </div>
      </dialog>
    </div>
  );
}

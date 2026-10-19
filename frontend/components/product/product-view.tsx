"use client";

import Link from "next/link";
import { useState } from "react";

import { useCart } from "@/components/cart/cart-provider";
import { Badge } from "@/components/product-card";
import { ProductArt } from "@/components/product-art";
import { isLightColor, swatchColor } from "@/lib/colors";
import { formatPrice, formatPriceRange } from "@/lib/format";
import type { ProductDetail, Variant } from "@/lib/types";

const LOW_STOCK = 5;

type Props = { product: Omit<ProductDetail, "related"> };

/**
 * The interactive part of the product page: colour and size pickers, live stock and price.
 * The data (including stock) was fetched on the server for this request; this component only
 * decides what to show for the shopper's current choice.
 */
export function ProductView({ product }: Props) {
  const firstInStock = product.variants.find((variant) => variant.in_stock) ?? product.variants[0];
  const [color, setColor] = useState(firstInStock?.color ?? product.colors[0]);
  const [size, setSize] = useState<string | null>(product.sizes.length === 1 ? product.sizes[0] : null);
  const [notice, setNotice] = useState<string | null>(null);
  const { addItem, openDrawer, lines } = useCart();

  const variantFor = (s: string, c: string): Variant | undefined =>
    product.variants.find((variant) => variant.size === s && variant.color === c);
  const selected = size ? variantFor(size, color) : undefined;
  const colorInStock = (c: string) => product.variants.some((variant) => variant.color === c && variant.in_stock);

  const price = selected
    ? formatPrice(selected.price_cents)
    : formatPriceRange(product.price_min_cents, product.price_max_cents);

  return (
    <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
      <div className="space-y-4">
        <ProductArt
          name={product.name}
          slug={product.slug}
          categorySlug={product.category_slug}
          color={color}
          imageUrl={product.image_url}
          priority
          sizes="(min-width: 1024px) 55vw, 100vw"
          className="aspect-[4/5] rounded-sm"
        />
        {product.colors.length > 1 && !product.image_url && (
          <div className="grid grid-cols-4 gap-3" aria-hidden="true">
            {product.colors.slice(0, 4).map((c) => (
              <button
                key={c}
                type="button"
                tabIndex={-1}
                onClick={() => setColor(c)}
                className={`rounded-sm ring-offset-2 ring-offset-paper ${c === color ? "ring-2 ring-ink" : ""}`}
              >
                <ProductArt name={product.name} slug={product.slug} categorySlug={product.category_slug} color={c} className="aspect-square rounded-sm" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="lg:sticky lg:top-32 lg:self-start">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">{product.category}</p>
        <h1 className="mt-3 font-serif text-4xl tracking-tight sm:text-5xl">{product.name}</h1>
        <p className="mt-4 text-2xl" aria-live="polite">
          {price}
        </p>
        {product.is_final_sale && (
          <div className="mt-4">
            <Badge tone="accent">Final sale · cannot be returned</Badge>
          </div>
        )}
        <p className="mt-6 leading-relaxed text-ink/80">{product.description}</p>

        <fieldset className="mt-8">
          <legend className="text-sm">
            Colour: <span className="font-medium">{color}</span>
          </legend>
          <div className="mt-3 flex flex-wrap gap-3">
            {product.colors.map((c) => {
              const hex = swatchColor(c);
              const available = colorInStock(c);
              return (
                <label key={c} className="cursor-pointer" title={available ? c : `${c} (sold out)`}>
                  <input
                    type="radio"
                    name="color"
                    value={c}
                    checked={c === color}
                    onChange={() => {
                      setColor(c);
                      setNotice(null);
                    }}
                    className="peer sr-only"
                  />
                  <span className="sr-only">
                    {c}
                    {!available && " (sold out)"}
                  </span>
                  <span
                    aria-hidden="true"
                    className={`relative block size-9 rounded-full ring-1 ring-ink/20 ring-offset-2 ring-offset-paper transition peer-checked:ring-2 peer-checked:ring-ink peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-accent ${available ? "" : "opacity-50"}`}
                    style={{ backgroundColor: hex }}
                  >
                    {!available && (
                      <span
                        className={`absolute left-1/2 top-1/2 h-px w-10 -translate-x-1/2 -translate-y-1/2 -rotate-45 ${isLightColor(hex) ? "bg-ink/60" : "bg-white/80"}`}
                      />
                    )}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <fieldset className="mt-7">
          <legend className="text-sm">
            Size: <span className="font-medium">{size ?? "Select a size"}</span>
          </legend>
          <div className="mt-3 flex flex-wrap gap-2">
            {product.sizes.map((s) => {
              const variant = variantFor(s, color);
              const available = variant?.in_stock ?? false;
              return (
                <label key={s} className={available ? "cursor-pointer" : "cursor-not-allowed"}>
                  <input
                    type="radio"
                    name="size"
                    value={s}
                    checked={s === size}
                    disabled={!available}
                    onChange={() => {
                      setSize(s);
                      setNotice(null);
                    }}
                    className="peer sr-only"
                  />
                  <span className="inline-flex h-11 min-w-14 items-center justify-center rounded-full border border-line bg-card px-4 text-sm transition peer-checked:border-ink peer-checked:bg-ink peer-checked:text-paper peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent peer-disabled:border-dashed peer-disabled:text-muted/70 peer-disabled:line-through hover:border-ink/60 peer-disabled:hover:border-line">
                    {s}
                    {!available && <span className="sr-only"> (sold out)</span>}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <StockMessage product={product} selected={selected} />

        <button
          type="button"
          disabled={!selected?.in_stock}
          onClick={() => {
            if (!selected) return;
            const inBag = lines.find((line) => line.variantId === selected.id)?.quantity ?? 0;
            if (inBag >= selected.stock) {
              setNotice(`You already have all ${selected.stock} in your bag.`);
              return;
            }
            addItem(selected.id);
            setNotice(null);
            openDrawer();
          }}
          className="mt-6 h-14 w-full rounded-full bg-ink text-sm font-medium text-paper transition hover:bg-accent disabled:cursor-not-allowed disabled:bg-ink/30"
        >
          {!product.in_stock ? "Sold out" : size ? "Add to bag" : "Select a size"}
        </button>
        <p className="mt-3 min-h-5 text-center text-sm text-muted" role="status">
          {notice}
        </p>

        <div className="mt-6 divide-y divide-line border-y border-line">
          {product.fit_notes && <Details title="Fit">{product.fit_notes}</Details>}
          {product.material_care && <Details title="Material & care">{product.material_care}</Details>}
          <Details title="Shipping & returns">
            Free US shipping on orders over $75.{" "}
            {product.is_final_sale ? "This item is final sale and cannot be returned." : "Free returns within 30 days of delivery."}{" "}
            <Link href="/policies/returns" className="underline underline-offset-2 hover:text-accent">
              Read the full policy
            </Link>
          </Details>
        </div>
      </div>
    </div>
  );
}

function StockMessage({ product, selected }: { product: Props["product"]; selected?: Variant }) {
  let tone = "text-muted";
  let text: string;
  if (!product.in_stock) {
    tone = "text-accent";
    text = product.restock_note ? `Sold out. ${product.restock_note}.` : "Sold out.";
  } else if (!selected) {
    text = "Choose a size to see availability.";
  } else if (!selected.in_stock) {
    tone = "text-accent";
    text = "This size is sold out in this colour.";
  } else if (selected.stock <= LOW_STOCK) {
    tone = "text-accent";
    text = `Only ${selected.stock} left — order soon.`;
  } else {
    tone = "text-emerald-800";
    text = "In stock, ready to ship in 1–2 business days.";
  }
  return (
    <p className={`mt-6 text-sm ${tone}`} aria-live="polite">
      {text}
    </p>
  );
}

function Details({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="group py-4">
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium [&::-webkit-details-marker]:hidden">
        {title}
        <span aria-hidden="true" className="text-lg leading-none transition group-open:rotate-45">
          +
        </span>
      </summary>
      <p className="mt-3 text-sm leading-relaxed text-ink/75">{children}</p>
    </details>
  );
}

import Link from "next/link";

import { ProductArt } from "@/components/product-art";
import { ProductPhoto } from "@/components/product-photo";
import { swatchColor } from "@/lib/colors";
import { formatPriceRange } from "@/lib/format";
import { cardImages } from "@/lib/product-images";
import type { ProductSummary } from "@/lib/types";

const MAX_SWATCHES = 4;
// Card width at each breakpoint (the grid has 2 / 3 / 4 columns), so phones get a small file.
const CARD_SIZES = "(min-width: 1280px) 300px, (min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw";

export function ProductCard({ product, priority = false }: { product: ProductSummary; priority?: boolean }) {
  const extraColors = product.colors.length - MAX_SWATCHES;
  const { main, hover } = cardImages(product.images, product.colors);
  const art = (
    <ProductArt
      name={product.name}
      slug={product.slug}
      categorySlug={product.category_slug}
      color={main?.color ?? product.colors[0]}
      imageUrl={product.image_url}
      eager={priority}
      sizes={CARD_SIZES}
      className="h-full w-full"
    />
  );
  return (
    <Link href={`/products/${product.slug}`} className="group block rounded-sm">
      <div className="relative aspect-[4/5] overflow-hidden rounded-sm bg-card">
        {/* Slow, small zoom on hover; motion-safe: skipped when the visitor asks for reduced motion. */}
        <div className="absolute inset-0 transition-transform duration-500 ease-calm motion-safe:group-hover:scale-[1.04]">
          {main ? <ProductPhoto image={main} fallback={art} sizes={CARD_SIZES} eager={priority} /> : art}
          {hover && (
            // Fades in over the product photo on hover. Lazy: most visitors never hover most cards.
            <ProductPhoto
              image={hover}
              fallback={null}
              sizes={CARD_SIZES}
              decorative
              className="opacity-0 transition-opacity duration-500 group-hover:opacity-100"
            />
          )}
        </div>
        <div className="absolute left-3 top-3 flex flex-col gap-1.5">
          {!product.in_stock && <Badge tone="ink">Sold out</Badge>}
          {product.is_final_sale && <Badge tone="accent">Final sale</Badge>}
        </div>
      </div>
      <div className="mt-3 space-y-1">
        <h3 className="font-medium leading-snug underline-offset-4 group-hover:underline">{product.name}</h3>
        <p className="text-sm text-muted">{formatPriceRange(product.price_min_cents, product.price_max_cents)}</p>
        {product.colors.length > 1 && (
          <div className="flex items-center gap-1.5 pt-1" aria-label={`${product.colors.length} colours`}>
            {product.colors.slice(0, MAX_SWATCHES).map((color) => (
              <span
                key={color}
                title={color}
                className="size-3 rounded-full ring-1 ring-ink/15"
                style={{ backgroundColor: swatchColor(color) }}
              />
            ))}
            {extraColors > 0 && <span className="text-xs text-muted">+{extraColors}</span>}
          </div>
        )}
      </div>
    </Link>
  );
}

export function Badge({ tone, children }: { tone: "ink" | "accent" | "sage"; children: React.ReactNode }) {
  const tones = {
    ink: "bg-ink text-paper",
    accent: "bg-accent text-white",
    sage: "bg-sage text-ink",
  };
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function ProductGrid({ products, priorityCount = 0 }: { products: ProductSummary[]; priorityCount?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:gap-x-6 xl:grid-cols-4">
      {products.map((product, index) => (
        <li key={product.slug}>
          <ProductCard product={product} priority={index < priorityCount} />
        </li>
      ))}
    </ul>
  );
}

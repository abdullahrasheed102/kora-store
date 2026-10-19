import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ChevronIcon } from "@/components/icons";
import { ProductGrid } from "@/components/product-card";
import { ProductView } from "@/components/product/product-view";
import { ProductDetailSkeleton } from "@/components/skeletons";
import { api, isNotFound } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import type { ProductDetail } from "@/lib/types";

// Identical fetches in one render are deduplicated, so metadata and the page share one API call.
async function loadProduct(slug: string): Promise<ProductDetail> {
  try {
    return await api.product(slug);
  } catch (error) {
    if (isNotFound(error)) notFound();
    throw error;
  }
}

export async function generateMetadata({ params }: PageProps<"/products/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  const product = await loadProduct(slug);
  return {
    title: product.name,
    description: `${product.description} ${formatPrice(product.price_cents)}.`,
    openGraph: { title: product.name, description: product.description, type: "website" },
  };
}

export default function ProductPage({ params }: PageProps<"/products/[slug]">) {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
      <Suspense fallback={<ProductDetailSkeleton />}>
        <ProductContent params={params} />
      </Suspense>
    </div>
  );
}

async function ProductContent({ params }: Pick<PageProps<"/products/[slug]">, "params">) {
  const { slug } = await params;
  const { related, ...product } = await loadProduct(slug);

  // Structured data: lets search engines show price and availability in results.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description,
    category: product.category,
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "USD",
      lowPrice: (product.price_min_cents / 100).toFixed(2),
      highPrice: (product.price_max_cents / 100).toFixed(2),
      availability: product.in_stock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
    },
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <nav aria-label="Breadcrumb" className="mb-8 text-sm text-muted">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link href="/shop" className="hover:text-ink">
              Shop
            </Link>
          </li>
          <ChevronIcon className="size-3.5" />
          <li>
            <Link href={`/shop/${product.category_slug}`} className="hover:text-ink">
              {product.category}
            </Link>
          </li>
          <ChevronIcon className="size-3.5" />
          <li aria-current="page" className="text-ink">
            {product.name}
          </li>
        </ol>
      </nav>

      {/* key: reset the pickers when navigating from one product to another. */}
      <ProductView key={product.slug} product={product} />

      {related.length > 0 && (
        <section aria-labelledby="related-heading" className="mt-24">
          <h2 id="related-heading" className="border-b border-line pb-4 font-serif text-3xl tracking-tight">
            You may also like
          </h2>
          <div className="mt-8">
            <ProductGrid products={related} />
          </div>
        </section>
      )}
    </>
  );
}

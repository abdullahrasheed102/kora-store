import type { Metadata } from "next";
import { Suspense } from "react";

import { ShopResults } from "@/components/shop/shop-results";
import { ShopSkeleton } from "@/components/skeletons";
import { NAV_CATEGORIES } from "@/lib/site";
import { parseShopFilters } from "@/lib/shop-url";

export async function generateMetadata({ params }: PageProps<"/shop/[category]">): Promise<Metadata> {
  const { category } = await params;
  const name = NAV_CATEGORIES.find((item) => item.slug === category)?.name ?? "Shop";
  return { title: name, description: `Shop ${name.toLowerCase()} at Kora Outfitters.` };
}

export default function CategoryPage({ params, searchParams }: PageProps<"/shop/[category]">) {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
      <Suspense fallback={<ShopSkeleton />}>
        <CategoryShop params={params} searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function CategoryShop({ params, searchParams }: PageProps<"/shop/[category]">) {
  const [{ category }, query] = await Promise.all([params, searchParams]);
  return <ShopResults category={category} filters={parseShopFilters(query)} />;
}

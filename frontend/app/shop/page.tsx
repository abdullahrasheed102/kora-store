import type { Metadata } from "next";
import { Suspense } from "react";

import { ShopResults } from "@/components/shop/shop-results";
import { ShopSkeleton } from "@/components/skeletons";
import { parseShopFilters } from "@/lib/shop-url";

export async function generateMetadata({ searchParams }: PageProps<"/shop">): Promise<Metadata> {
  const { q } = parseShopFilters(await searchParams);
  return q
    ? { title: `Search: ${q}`, robots: { index: false } } // search result pages shouldn't be indexed
    : { title: "Shop all", description: "Browse every Kora Outfitters product." };
}

export default function ShopPage({ searchParams }: PageProps<"/shop">) {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
      <Suspense fallback={<ShopSkeleton />}>
        <Shop searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

// searchParams only exist at request time, so the part that reads them sits inside <Suspense>.
async function Shop({ searchParams }: Pick<PageProps<"/shop">, "searchParams">) {
  return <ShopResults filters={parseShopFilters(await searchParams)} />;
}

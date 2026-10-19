import Link from "next/link";
import { Suspense } from "react";

import { ChatIcon, LeafIcon, ReturnIcon, TruckIcon } from "@/components/icons";
import { ProductArt } from "@/components/product-art";
import { ProductGrid } from "@/components/product-card";
import { ProductGridSkeleton } from "@/components/skeletons";
import { api } from "@/lib/api";
import { NAV_CATEGORIES } from "@/lib/site";

// Representative products for the hero and category tiles (static, so they're in the prerendered shell).
const HERO_TILES = [
  { name: "Merino Crew Sweater", slug: "merino-crew-sweater", category: "tops", color: "Oatmeal" },
  { name: "Wool Blend Overcoat", slug: "wool-blend-overcoat", category: "outerwear", color: "Camel" },
  { name: "Straight-Leg Jeans", slug: "straight-leg-jeans", category: "bottoms", color: "Light Wash" },
];

const CATEGORY_TILES: Record<string, { slug: string; color: string; blurb: string }> = {
  tops: { slug: "everyday-cotton-tee", color: "Sage", blurb: "Tees, shirts & knits" },
  bottoms: { slug: "relaxed-chino-pants", color: "Khaki", blurb: "Denim, chinos & skirts" },
  outerwear: { slug: "quilted-puffer-jacket", color: "Forest", blurb: "Coats & shells" },
  footwear: { slug: "chelsea-boots", color: "Tan", blurb: "Sneakers & boots" },
  accessories: { slug: "canvas-tote-bag", color: "Natural", blurb: "Bags, belts & beanies" },
  "gift-cards": { slug: "gift-card", color: "Clay", blurb: "Delivered by email" },
};

const PERKS = [
  { icon: TruckIcon, title: "Free US shipping", text: "On orders over $75. Ships in 1–2 business days." },
  { icon: ReturnIcon, title: "30-day returns", text: "Free US returns with a prepaid label." },
  { icon: ChatIcon, title: "Help, 24/7", text: "Our AI assistant answers any time. People reply weekdays." },
  { icon: LeafIcon, title: "Natural fibres", text: "Organic cotton, linen, merino and recycled fills." },
];

export default function HomePage() {
  return (
    <>
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-20 pt-12 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:px-8 lg:pt-20">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">Autumn edit</p>
          <h1 className="mt-5 font-serif text-5xl font-medium leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
            Clothes you&apos;ll reach for <em className="font-normal text-accent">every day.</em>
          </h1>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-muted">
            Honest basics in organic cotton, linen and merino. Cut to fit well, made to wear for years.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link
              href="/shop"
              className="rounded-full bg-ink px-7 py-3.5 text-sm font-medium text-paper transition hover:bg-accent"
            >
              Shop the collection
            </Link>
            <Link
              href="/shop/outerwear"
              className="rounded-full border border-ink/20 px-7 py-3.5 text-sm font-medium transition hover:border-ink"
            >
              New outerwear
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ProductArt
            name={HERO_TILES[0].name}
            slug={HERO_TILES[0].slug}
            categorySlug={HERO_TILES[0].category}
            color={HERO_TILES[0].color}
            className="row-span-2 aspect-[3/5] rounded-sm sm:aspect-auto"
          />
          {HERO_TILES.slice(1).map((tile) => (
            <ProductArt
              key={tile.slug}
              name={tile.name}
              slug={tile.slug}
              categorySlug={tile.category}
              color={tile.color}
              className="aspect-square rounded-sm"
            />
          ))}
        </div>
      </section>

      <section aria-labelledby="categories-heading" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeading id="categories-heading" title="Shop by category" />
        <ul className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          {NAV_CATEGORIES.map((category) => {
            const tile = CATEGORY_TILES[category.slug];
            return (
              <li key={category.slug}>
                <Link href={`/shop/${category.slug}`} className="group block">
                  <ProductArt
                    name={category.name}
                    slug={tile.slug}
                    categorySlug={category.slug}
                    color={tile.color}
                    className="aspect-square rounded-sm transition duration-500 group-hover:scale-[1.03]"
                  />
                  <p className="mt-3 font-serif text-lg group-hover:text-accent">{category.name}</p>
                  <p className="text-sm text-muted">{tile.blurb}</p>
                </Link>
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="bestsellers-heading" className="mx-auto mt-24 max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionHeading id="bestsellers-heading" title="Bestsellers" link={{ href: "/shop", label: "Shop all" }} />
        <div className="mt-8">
          {/* Static shell above; the live product list streams in at request time. */}
          <Suspense fallback={<ProductGridSkeleton count={4} />}>
            <Bestsellers />
          </Suspense>
        </div>
      </section>

      <section aria-label="Why shop with us" className="mx-auto mt-24 max-w-7xl px-4 sm:px-6 lg:px-8">
        <ul className="grid gap-8 rounded-sm bg-sage px-6 py-12 sm:grid-cols-2 sm:px-10 lg:grid-cols-4">
          {PERKS.map(({ icon: Icon, title, text }) => (
            <li key={title}>
              <Icon className="size-7 text-accent" />
              <h3 className="mt-4 font-serif text-xl">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink/75">{text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto mt-24 max-w-3xl px-4 text-center sm:px-6">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">Our approach</p>
        <p className="mt-5 font-serif text-3xl leading-snug sm:text-4xl">
          Fewer, better pieces. We design for fit and fabric first, and keep our collection small so every piece
          earns its place.
        </p>
        <Link href="/policies/returns" className="mt-8 inline-block text-sm font-medium underline underline-offset-4 hover:text-accent">
          Read our returns promise
        </Link>
      </section>
    </>
  );
}

async function Bestsellers() {
  const { items } = await api.products({ sort: "best_selling", per_page: 4 });
  return <ProductGrid products={items} />;
}

function SectionHeading({ id, title, link }: { id: string; title: string; link?: { href: string; label: string } }) {
  return (
    <div className="flex items-end justify-between gap-4 border-b border-line pb-4">
      <h2 id={id} className="font-serif text-3xl tracking-tight sm:text-4xl">
        {title}
      </h2>
      {link && (
        <Link href={link.href} className="text-sm font-medium underline-offset-4 hover:text-accent hover:underline">
          {link.label}
        </Link>
      )}
    </div>
  );
}

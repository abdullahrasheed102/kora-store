import Link from "next/link";

import { NAV_CATEGORIES } from "@/lib/site";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-24 text-center sm:px-6">
      <p className="font-serif text-8xl text-accent">404</p>
      <h1 className="mt-6 font-serif text-4xl tracking-tight">We couldn&apos;t find that page</h1>
      <p className="mt-4 text-muted">It may have moved, or the product may no longer be available.</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link href="/shop" className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Shop all products
        </Link>
        <Link href="/" className="rounded-full border border-ink/20 px-6 py-3 text-sm font-medium hover:border-ink">
          Go home
        </Link>
      </div>
      <ul className="mt-12 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-muted">
        {NAV_CATEGORIES.map((category) => (
          <li key={category.slug}>
            <Link href={`/shop/${category.slug}`} className="hover:text-ink">
              {category.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

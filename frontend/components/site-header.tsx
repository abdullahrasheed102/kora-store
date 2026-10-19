import Form from "next/form";
import Link from "next/link";

import { CartButton } from "@/components/cart/cart-button";
import { SearchIcon, UserIcon } from "@/components/icons";
import { MobileNav } from "@/components/mobile-nav";
import { AUTHOR, NAV_CATEGORIES } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/75">
      <div className="bg-ink px-4 py-2 text-center text-xs text-paper/85">
        A demo store built by{" "}
        <a href={AUTHOR.url} className="font-medium text-paper underline underline-offset-2 hover:text-sage">
          {AUTHOR.name}
        </a>{" "}
        · No real orders are shipped
      </div>

      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6 lg:px-8">
        <MobileNav />

        <Link href="/" className="font-serif text-2xl font-semibold tracking-tight">
          Kora<span className="text-accent">.</span>
        </Link>

        <nav aria-label="Main" className="ml-6 hidden lg:block">
          <ul className="flex items-center gap-6 text-sm">
            <li>
              <Link href="/shop" className="hover:text-accent">
                Shop all
              </Link>
            </li>
            {NAV_CATEGORIES.map((category) => (
              <li key={category.slug}>
                <Link href={`/shop/${category.slug}`} className="hover:text-accent">
                  {category.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {/* next/form: a normal GET form (works without JavaScript) with client-side navigation on top. */}
          <Form action="/shop" role="search" className="relative hidden sm:block">
            <label htmlFor="site-search" className="sr-only">
              Search products
            </label>
            <input
              id="site-search"
              name="q"
              type="search"
              placeholder="Search"
              className="h-10 w-44 rounded-full border border-line bg-card pl-10 pr-4 text-sm placeholder:text-muted focus:w-60 focus:border-ink/40 focus:outline-none focus-visible:outline-2 transition-[width]"
            />
            <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
          </Form>

          <Link
            href="/account"
            className="inline-flex size-10 items-center justify-center rounded-full hover:bg-line/60"
            aria-label="Your account"
          >
            <UserIcon className="size-6" />
          </Link>
          <CartButton />
        </div>
      </div>
    </header>
  );
}

import Link from "next/link";

import { AUTHOR, ABOUT_LINK, HELP_LINKS, NAV_CATEGORIES, POLICY_LINKS, SITE_NAME } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-24 bg-ink text-paper/80">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-2 lg:grid-cols-4 lg:px-8">
        <div className="lg:col-span-2">
          <p className="font-serif text-3xl font-semibold text-paper">
            Kora<span className="text-accent">.</span>
          </p>
          <p className="mt-4 max-w-sm text-sm leading-relaxed">
            Everyday clothing in natural fibres, made to be worn for years. Free US shipping over $75 and 30-day returns.
          </p>
        </div>

        <nav aria-label="Shop">
          <h2 className="text-xs font-medium uppercase tracking-widest text-paper">Shop</h2>
          <ul className="mt-4 space-y-2.5 text-sm">
            <li>
              <Link href="/shop" className="hover:text-paper">
                Shop all
              </Link>
            </li>
            {NAV_CATEGORIES.map((category) => (
              <li key={category.slug}>
                <Link href={`/shop/${category.slug}`} className="hover:text-paper">
                  {category.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="Help">
          <h2 className="text-xs font-medium uppercase tracking-widest text-paper">Help</h2>
          <ul className="mt-4 space-y-2.5 text-sm">
            <li>
              <Link href={ABOUT_LINK.href} className="hover:text-paper">
                {ABOUT_LINK.title}
              </Link>
            </li>
            {HELP_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="hover:text-paper">
                  {link.title}
                </Link>
              </li>
            ))}
            {POLICY_LINKS.map((policy) => (
              <li key={policy.key}>
                <Link href={`/policies/${policy.key}`} className="hover:text-paper">
                  {policy.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      <div className="border-t border-paper/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs sm:flex-row sm:justify-between sm:px-6 lg:px-8">
          <p>© {SITE_NAME}</p>
          <p>
            Built by{" "}
            <a href={AUTHOR.url} className="underline underline-offset-2 hover:text-paper">
              {AUTHOR.name}
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}

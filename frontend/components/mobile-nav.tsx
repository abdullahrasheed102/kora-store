"use client";

import Form from "next/form";
import Link from "next/link";
import { useRef } from "react";

import { CloseIcon, MenuIcon, SearchIcon } from "@/components/icons";
import { NAV_CATEGORIES, POLICY_LINKS } from "@/lib/site";

// A native <dialog> opened with showModal() gives us focus trapping, Escape to close and an
// inert background for free: better accessibility than a hand-made overlay.
export function MobileNav() {
  const dialog = useRef<HTMLDialogElement>(null);
  // Close the menu when a link inside it is followed. (Watching the URL with usePathname()
  // would also work, but it would stop every page from being prerendered.)
  const closeOnLink = (event: React.MouseEvent) => {
    if ((event.target as HTMLElement).closest("a")) dialog.current?.close();
  };

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => dialog.current?.showModal()}
        className="-ml-2 inline-flex size-10 items-center justify-center rounded-full hover:bg-line/60"
        aria-label="Open menu"
      >
        <MenuIcon />
      </button>

      <dialog
        ref={dialog}
        aria-label="Menu"
        className="m-0 h-dvh max-h-none w-[min(22rem,88vw)] max-w-none bg-paper p-0 text-ink backdrop:bg-ink/40"
        onClick={(event) => {
          if (event.target === dialog.current) dialog.current.close(); // click on the backdrop
        }}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center justify-between border-b border-line px-4">
            <span className="font-serif text-2xl font-semibold">
              Kora<span className="text-accent">.</span>
            </span>
            <button
              type="button"
              onClick={() => dialog.current?.close()}
              className="inline-flex size-10 items-center justify-center rounded-full hover:bg-line/60"
              aria-label="Close menu"
            >
              <CloseIcon />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-6" onClick={closeOnLink}>
            <Form action="/shop" role="search" className="relative" onSubmit={() => dialog.current?.close()}>
              <label htmlFor="mobile-search" className="sr-only">
                Search products
              </label>
              <input
                id="mobile-search"
                name="q"
                type="search"
                placeholder="Search products"
                className="h-11 w-full rounded-full border border-line bg-card pl-10 pr-4 text-sm placeholder:text-muted"
              />
              <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
            </Form>

            <nav aria-label="Mobile" className="mt-8">
              <ul className="space-y-1 font-serif text-2xl">
                <li>
                  <Link href="/shop" className="block py-1.5 hover:text-accent">
                    Shop all
                  </Link>
                </li>
                {NAV_CATEGORIES.map((category) => (
                  <li key={category.slug}>
                    <Link href={`/shop/${category.slug}`} className="block py-1.5 hover:text-accent">
                      {category.name}
                    </Link>
                  </li>
                ))}
              </ul>
              <h2 className="mt-10 text-xs font-medium uppercase tracking-widest text-muted">Account</h2>
              <ul className="mt-3 space-y-2 text-sm">
                <li>
                  <Link href="/account" className="hover:text-accent">
                    Your account
                  </Link>
                </li>
                <li>
                  <Link href="/cart" className="hover:text-accent">
                    Your bag
                  </Link>
                </li>
              </ul>
              <h2 className="mt-10 text-xs font-medium uppercase tracking-widest text-muted">Help</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {POLICY_LINKS.map((policy) => (
                  <li key={policy.key}>
                    <Link href={`/policies/${policy.key}`} className="hover:text-accent">
                      {policy.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </div>
      </dialog>
    </div>
  );
}

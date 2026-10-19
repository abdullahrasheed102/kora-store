"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTransition } from "react";

import { useCart } from "@/components/cart/cart-provider";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/account", label: "Overview" },
  { href: "/account/orders", label: "Orders" },
  { href: "/account/addresses", label: "Addresses" },
];

export function AccountNav() {
  const pathname = usePathname();
  return (
    <ul className="flex gap-1 overflow-x-auto lg:flex-col">
      {LINKS.map((link) => {
        const active = link.href === "/account" ? pathname === "/account" : pathname.startsWith(link.href);
        return (
          <li key={link.href}>
            <Link
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={`block whitespace-nowrap rounded-full px-4 py-2 text-sm ${active ? "bg-ink text-paper" : "hover:bg-line/60"}`}
            >
              {link.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Fallback while the pathname isn't known yet: the same links, nothing highlighted. */
export function AccountNavFallback() {
  return (
    <ul className="flex gap-1 lg:flex-col">
      {LINKS.map((link) => (
        <li key={link.href}>
          <Link href={link.href} className="block whitespace-nowrap rounded-full px-4 py-2 text-sm hover:bg-line/60">
            {link.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function LogoutButton() {
  const [isPending, startTransition] = useTransition();
  const { closeDrawer } = useCart();
  return (
    <button
      type="button"
      disabled={isPending}
      onClick={async () => {
        await api.logout().catch(() => undefined); // even if this fails, leave the account area
        closeDrawer();
        // Full page load: drops every page the client router cached while logged in, so no
        // private data stays in memory (or reappears with the Back button).
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- deliberate: reset all client state on logout
        startTransition(() => window.location.assign("/"));
      }}
      className="px-4 py-2 text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
    >
      {isPending ? "Logging out…" : "Log out"}
    </button>
  );
}

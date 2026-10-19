"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/orders", label: "Orders" },
  { href: "/admin/products", label: "Products" },
  { href: "/admin/returns", label: "Returns" },
  { href: "/admin/tickets", label: "Tickets" },
  { href: "/admin/policies", label: "Policies" },
];

export function AdminNav() {
  const pathname = usePathname();
  return <NavList isActive={(href) => (href === "/admin" ? pathname === "/admin" : pathname.startsWith(href))} />;
}

export function AdminNavFallback() {
  return <NavList isActive={() => false} />;
}

function NavList({ isActive }: { isActive: (href: string) => boolean }) {
  return (
    <ul className="flex gap-1 overflow-x-auto lg:flex-col">
      {LINKS.map((link) => (
        <li key={link.href}>
          <Link
            href={link.href}
            aria-current={isActive(link.href) ? "page" : undefined}
            className={`block whitespace-nowrap rounded-full px-4 py-2 text-sm ${isActive(link.href) ? "bg-ink text-paper" : "hover:bg-line/60"}`}
          >
            {link.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

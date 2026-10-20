import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { StatusBadge } from "@/components/account/status-badge";
import { VerifyBanner } from "@/components/account/verify-banner";
import { TextSkeleton } from "@/components/skeletons";
import { accountApi, requireCustomer } from "@/lib/api-server";
import { COUNTRY_NAMES, formatDate, formatPrice } from "@/lib/format";

export const metadata: Metadata = { title: "Your account", robots: { index: false } };

export default function AccountPage({ searchParams }: PageProps<"/account">) {
  return (
    <Suspense fallback={<TextSkeleton lines={8} />}>
      <Overview searchParams={searchParams} />
    </Suspense>
  );
}

async function Overview({ searchParams }: Pick<PageProps<"/account">, "searchParams">) {
  const [user, { email_confirmed: justConfirmed }] = await Promise.all([requireCustomer("/account"), searchParams]);
  const [orders, addresses] = await Promise.all([accountApi.orders(), accountApi.addresses()]);
  const defaultAddress = addresses.find((address) => address.is_default);

  return (
    <div className="space-y-12">
      {/* Arriving from the link in the confirmation email */}
      {justConfirmed === "1" && user.email_verified && (
        <p role="status" className="rounded-sm bg-sage px-5 py-4 text-sm">
          <span className="font-medium">Email confirmed.</span> You&apos;ll now get order confirmations and delivery
          updates at {user.email}.
        </p>
      )}
      {!user.email_verified && <VerifyBanner email={user.email} />}
      <section>
        {/* The full name: "first word" broke for names like "Store Admin" ("Hello, Store."). */}
        <p className="font-serif text-2xl">Hello, {user.name}.</p>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-muted">Name</dt>
            <dd className="mt-1 font-medium">{user.name}</dd>
          </div>
          <div>
            <dt className="text-muted">Email</dt>
            <dd className="mt-1 break-all font-medium">{user.email}</dd>
          </div>
          <div>
            <dt className="text-muted">Member since</dt>
            <dd className="mt-1 font-medium">{formatDate(user.created_at)}</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="recent-orders">
        <div className="flex items-end justify-between border-b border-line pb-3">
          <h2 id="recent-orders" className="font-serif text-2xl">
            Recent orders
          </h2>
          {orders.length > 0 && (
            <Link href="/account/orders" className="text-sm font-medium hover:text-accent">
              View all
            </Link>
          )}
        </div>
        {orders.length === 0 ? (
          <p className="mt-4 text-sm text-muted">
            No orders yet. Orders you place while logged in will appear here.{" "}
            <Link href="/shop" className="font-medium text-ink underline underline-offset-4">
              Start shopping
            </Link>
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {orders.slice(0, 3).map((order) => (
              <li key={order.order_number}>
                <Link href={`/account/orders/${order.order_number}`} className="flex items-center justify-between gap-4 py-4 hover:text-accent">
                  <span className="font-medium">{order.order_number}</span>
                  <span className="text-sm text-muted">{formatDate(order.created_at)}</span>
                  <StatusBadge status={order.status} />
                  <span className="text-sm">{formatPrice(order.total_cents)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="default-address">
        <div className="flex items-end justify-between border-b border-line pb-3">
          <h2 id="default-address" className="font-serif text-2xl">
            Default address
          </h2>
          <Link href="/account/addresses" className="text-sm font-medium hover:text-accent">
            Manage
          </Link>
        </div>
        {defaultAddress ? (
          <address className="mt-4 text-sm not-italic leading-relaxed">
            {defaultAddress.name}
            <br />
            {defaultAddress.line1}
            {defaultAddress.line2 && <>, {defaultAddress.line2}</>}
            <br />
            {defaultAddress.city}
            {defaultAddress.state && `, ${defaultAddress.state}`} {defaultAddress.postal_code}
            <br />
            {COUNTRY_NAMES[defaultAddress.country]}
          </address>
        ) : (
          <p className="mt-4 text-sm text-muted">No saved addresses yet.</p>
        )}
      </section>
    </div>
  );
}

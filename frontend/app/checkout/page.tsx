import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { CheckoutForm } from "@/components/checkout/checkout-form";
import { TextSkeleton } from "@/components/skeletons";
import { accountApi, getCurrentUser } from "@/lib/api-server";

export const metadata: Metadata = { title: "Checkout", robots: { index: false } };

export default function CheckoutPage({ searchParams }: PageProps<"/checkout">) {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 lg:px-8">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Checkout</h1>
      <div className="mt-10">
        <Suspense fallback={<TextSkeleton lines={10} />}>
          <Checkout searchParams={searchParams} />
        </Suspense>
      </div>
    </div>
  );
}

// Reads cookies (who is logged in) and the URL, so it streams in at request time.
async function Checkout({ searchParams }: Pick<PageProps<"/checkout">, "searchParams">) {
  const [user, { cancelled, payment }] = await Promise.all([getCurrentUser(), searchParams]);
  if (user?.role === "admin") {
    // The API refuses admin checkouts with a 403; this just explains it before anyone tries.
    return (
      <div className="rounded-sm bg-card p-8 text-center ring-1 ring-line" role="status">
        <p className="font-serif text-2xl">Checkout is off for admin accounts</p>
        <p className="mx-auto mt-3 max-w-md text-muted">
          Admin accounts can&apos;t place orders. Log in with a customer account to test checkout.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link href="/admin" className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
            Back to the admin dashboard
          </Link>
          <Link href="/shop" className="rounded-full border border-ink/20 px-6 py-3 text-sm font-medium hover:border-ink">
            Keep browsing
          </Link>
        </div>
      </div>
    );
  }
  const addresses = user ? await accountApi.addresses() : [];
  return (
    <CheckoutForm user={user} addresses={addresses} cancelled={cancelled === "1"} declined={payment === "declined"} />
  );
}

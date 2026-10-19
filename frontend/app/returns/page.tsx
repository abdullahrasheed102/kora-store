import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ReturnWizard } from "@/components/orders/return-wizard";
import { getCurrentUser } from "@/lib/api-server";

export const metadata: Metadata = {
  title: "Start a return",
  description: "Return or exchange items within 30 days of delivery.",
};

export default function ReturnsPage({ searchParams }: PageProps<"/returns">) {
  return (
    <div className="mx-auto max-w-4xl px-4 pt-12 sm:px-6">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Start a return</h1>
      <p className="mt-3 text-muted">
        Unworn items with tags can be returned within 30 days of delivery. Exchanges are free.{" "}
        <Link href="/policies/returns" className="underline underline-offset-2">
          Returns policy
        </Link>
      </p>
      <div className="mt-10">
        <Suspense fallback={<div className="h-32 rounded-sm bg-card ring-1 ring-line" aria-busy="true" />}>
          <Returns searchParams={searchParams} />
        </Suspense>
      </div>
    </div>
  );
}

async function Returns({ searchParams }: Pick<PageProps<"/returns">, "searchParams">) {
  const [user, { order }] = await Promise.all([getCurrentUser(), searchParams]);
  return <ReturnWizard user={user} initialOrder={typeof order === "string" ? order : null} />;
}

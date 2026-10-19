import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { TextSkeleton } from "@/components/skeletons";
import { api } from "@/lib/api";

export const metadata: Metadata = {
  title: "Store policies",
  description: "Shipping, returns, refunds, cancellations and support hours.",
};

export default function PoliciesPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-12 sm:px-6">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Store policies</h1>
      <p className="mt-3 text-muted">The same policies our support team and AI assistant follow.</p>
      <Suspense fallback={<div className="mt-10"><TextSkeleton lines={8} /></div>}>
        <PolicyList />
      </Suspense>
    </div>
  );
}

async function PolicyList() {
  const policies = await api.policies();
  return (
    <ul className="mt-10 divide-y divide-line border-y border-line">
      {policies.map((policy) => (
        <li key={policy.key} className="py-6">
          <h2 className="font-serif text-2xl">
            <Link href={`/policies/${policy.key}`} className="hover:text-accent">
              {policy.title}
            </Link>
          </h2>
          <p className="mt-2 leading-relaxed text-ink/80">{policy.body}</p>
        </li>
      ))}
    </ul>
  );
}

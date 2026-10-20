import type { Metadata } from "next";
import { Suspense } from "react";

import { VerifyEmailForm } from "@/components/account/verify-email-form";

export const metadata: Metadata = { title: "Confirm your email", robots: { index: false } };

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto max-w-xl px-4 pt-16 text-center sm:px-6">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Confirm your email</h1>
      <div className="mt-8">
        {/* useSearchParams (?token=) is request data, so the form streams in. */}
        <Suspense fallback={<div className="mx-auto h-12 w-56 rounded-full bg-card ring-1 ring-line" aria-busy="true" />}>
          <VerifyEmailForm />
        </Suspense>
      </div>
    </div>
  );
}

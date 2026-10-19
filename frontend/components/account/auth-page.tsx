import { Suspense } from "react";

import { AuthForm } from "@/components/account/auth-form";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  return (
    <div className="mx-auto max-w-md px-4 pb-10 pt-16 sm:px-6">
      <h1 className="text-center font-serif text-4xl tracking-tight">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p className="mt-3 text-center text-muted">
        {mode === "login" ? "Log in to see your orders and saved addresses." : "Save addresses and track your orders in one place."}
      </p>
      <div className="mt-10 rounded-sm bg-card p-6 ring-1 ring-line sm:p-8">
        {/* useSearchParams (for ?next=) only exists at request time, so the form streams in. */}
        <Suspense fallback={<div className="h-72" aria-busy="true" />}>
          <AuthForm mode={mode} />
        </Suspense>
      </div>
    </div>
  );
}

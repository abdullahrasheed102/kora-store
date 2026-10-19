import { Suspense } from "react";

import { AccountNav, AccountNavFallback, LogoutButton } from "@/components/account/account-nav";

export default function AccountLayout({ children }: LayoutProps<"/account">) {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-10 sm:px-6 lg:px-8">
      <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Your account</h1>
      <div className="mt-10 grid gap-10 lg:grid-cols-[200px_1fr]">
        <nav aria-label="Account" className="min-w-0 space-y-4">
          {/* usePathname() is request data, so the highlighted nav streams in. */}
          <Suspense fallback={<AccountNavFallback />}>
            <AccountNav />
          </Suspense>
          <LogoutButton />
        </nav>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}

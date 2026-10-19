import type { Metadata } from "next";
import { Suspense } from "react";

import { LogoutButton } from "@/components/account/account-nav";
import { AdminNav, AdminNavFallback } from "@/components/admin/admin-nav";
import { TextSkeleton } from "@/components/skeletons";
import { getCurrentUser, requireAdmin } from "@/lib/api-server";

export const metadata: Metadata = { title: { default: "Admin", template: "%s · Admin" }, robots: { index: false, follow: false } };

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
      <div className="grid gap-8 lg:grid-cols-[180px_1fr]">
        {/* min-w-0: a grid item is at least as wide as its content by default, so without it the
            sideways-scrolling nav would stretch the whole page on phones instead of scrolling. */}
        <nav aria-label="Admin" className="min-w-0 space-y-2">
          <p className="px-4 text-xs font-medium uppercase tracking-widest text-accent">Admin</p>
          <Suspense fallback={<AdminNavFallback />}>
            <AdminNav />
          </Suspense>
          <Suspense fallback={null}>
            <AdminProfile />
          </Suspense>
        </nav>
        <div className="min-w-0">
          <Suspense fallback={<TextSkeleton lines={12} />}>
            <AdminGate>{children}</AdminGate>
          </Suspense>
        </div>
      </div>
    </div>
  );
}

// Admins don't use /account, so their profile and "Log out" live here.
async function AdminProfile() {
  const user = await getCurrentUser(); // same request as the gate's: Next dedupes identical fetches
  if (user?.role !== "admin") return null;
  return (
    <div className="mt-6 hidden border-t border-line pt-4 lg:block">
      <p className="px-4 text-sm font-medium">{user.name}</p>
      <p className="break-all px-4 text-xs text-muted">{user.email}</p>
      <div className="mt-1 px-0">
        <LogoutButton />
      </div>
    </div>
  );
}

// One gate for every admin page: not logged in → login; not an admin → 404.
async function AdminGate({ children }: { children: React.ReactNode }) {
  const user = await requireAdmin("/admin");
  return (
    <>
      {/* On phones the sidebar profile is hidden, so show a compact one here. */}
      <div className="mb-6 flex items-center justify-between gap-3 rounded-sm bg-card px-4 py-2 text-sm ring-1 ring-line lg:hidden">
        <span className="min-w-0 truncate">
          {user.name} <span className="text-muted">· {user.email}</span>
        </span>
        <LogoutButton />
      </div>
      {children}
    </>
  );
}

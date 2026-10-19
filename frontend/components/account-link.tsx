import { cookies } from "next/headers";
import Link from "next/link";

import { UserIcon } from "@/components/icons";
import { roleHint } from "@/lib/session-hint";

const iconLink = "relative inline-flex h-10 items-center justify-center gap-2 rounded-full px-2.5 hover:bg-line/60";

/** The header's account link. Admins get a link to their dashboard and a visible "Admin" badge. */
export async function AccountLink() {
  // Reading cookies makes this request-time data, so the header wraps it in <Suspense>.
  const role = roleHint((await cookies()).get("access_token_cookie")?.value);
  if (role === "admin") {
    return (
      <Link href="/admin" className={iconLink} aria-label="Admin dashboard" title="Admin dashboard">
        <UserIcon className="size-6" />
        <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
          Admin
        </span>
      </Link>
    );
  }
  return <AccountLinkFallback />;
}

/** Shown until the role is known, and for customers and visitors. */
export function AccountLinkFallback() {
  return (
    <Link href="/account" className={iconLink} aria-label="Your account" title="Your account">
      <UserIcon className="size-6" />
    </Link>
  );
}

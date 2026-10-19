// Small shared building blocks for the admin pages (server-safe: no hooks).
import Link from "next/link";

export function AdminPageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-serif text-3xl tracking-tight sm:text-4xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-sm bg-card p-5 ring-1 ring-line ${className}`}>
      {title && <h2 className="mb-4 text-sm font-medium">{title}</h2>}
      {children}
    </section>
  );
}

export function StatTile({ label, value, hint, href }: { label: string; value: string; hint?: string; href?: string }) {
  const body = (
    <>
      <p className="text-sm text-muted">{label}</p>
      {/* Figures are sans (Inter), never the serif display face. */}
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </>
  );
  return href ? (
    <Link href={href} className="block rounded-sm bg-card p-5 ring-1 ring-line hover:ring-ink/40">
      {body}
    </Link>
  ) : (
    <div className="rounded-sm bg-card p-5 ring-1 ring-line">{body}</div>
  );
}

export const tableClass = "w-full text-left text-sm";
export const theadClass = "border-b border-line text-xs uppercase tracking-widest text-muted";
export const thClass = "py-3 pr-4 font-medium";
export const tdClass = "py-3 pr-4 align-top";

/** Prev/next + page count, keeping the other query parameters. */
export function Pager({ basePath, params, page, totalPages }: {
  basePath: string;
  params: Record<string, string | undefined>;
  page: number;
  totalPages: number;
}) {
  if (totalPages <= 1) return null;
  const href = (target: number) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
    if (target > 1) search.set("page", String(target));
    const text = search.toString();
    return text ? `${basePath}?${text}` : basePath;
  };
  const link = "rounded-full px-4 py-2 text-sm ring-1 ring-line hover:ring-ink/40";
  return (
    <nav aria-label="Pagination" className="mt-6 flex items-center justify-between text-sm">
      {page > 1 ? <Link href={href(page - 1)} className={link} rel="prev">Previous</Link> : <span />}
      <span className="text-muted">Page {page} of {totalPages}</span>
      {page < totalPages ? <Link href={href(page + 1)} className={link} rel="next">Next</Link> : <span />}
    </nav>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-sm border border-dashed border-line px-6 py-12 text-center text-sm text-muted">{children}</p>;
}

export const inputClass =
  "mt-1.5 h-10 w-full rounded-sm border border-line bg-paper px-3 text-sm focus:border-ink/50 focus:outline-none focus-visible:outline-2";
export const buttonClass = "rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-accent disabled:bg-ink/40";
export const secondaryButtonClass = "rounded-full px-4 py-2 text-sm ring-1 ring-line hover:ring-ink/40 disabled:opacity-50";

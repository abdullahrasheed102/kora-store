import Link from "next/link";

import { shopHref, type ShopFilters } from "@/lib/shop-url";

type Props = { category?: string; filters: ShopFilters; page: number; totalPages: number };

export function Pagination({ category, filters, page, totalPages }: Props) {
  if (totalPages <= 1) return null;
  const href = (target: number) => shopHref(category, { ...filters, page: target });
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1);
  const linkClass = "inline-flex h-10 min-w-10 items-center justify-center rounded-full px-3 text-sm";

  return (
    <nav aria-label="Pagination" className="mt-14 flex items-center justify-center gap-1">
      {page > 1 ? (
        <Link href={href(page - 1)} className={`${linkClass} hover:bg-line/60`} rel="prev">
          Previous
        </Link>
      ) : (
        <span className={`${linkClass} text-muted/60`}>Previous</span>
      )}
      {pages.map((number) =>
        number === page ? (
          <span key={number} aria-current="page" className={`${linkClass} bg-ink text-paper`}>
            {number}
          </span>
        ) : (
          <Link key={number} href={href(number)} className={`${linkClass} hover:bg-line/60`} aria-label={`Page ${number}`}>
            {number}
          </Link>
        ),
      )}
      {page < totalPages ? (
        <Link href={href(page + 1)} className={`${linkClass} hover:bg-line/60`} rel="next">
          Next
        </Link>
      ) : (
        <span className={`${linkClass} text-muted/60`}>Next</span>
      )}
    </nav>
  );
}

"use client";

import Image from "next/image";
import { useState } from "react";

type Props = {
  image: { url: string; alt_text: string };
  // What to show if the file fails to load (e.g. the database has a row but the deploy lacks the file).
  fallback: React.ReactNode;
  sizes: string;
  eager?: boolean; // load immediately (above the fold) instead of lazily
  decorative?: boolean; // a second photo of something already described: hide it from screen readers
  className?: string;
};

/**
 * A product photo from public/images/products, through next/image (resized WebP per device).
 * Fills its parent, which must be `relative` and have a size (we use aspect-[4/5]).
 */
export function ProductPhoto({ image, fallback, sizes, eager, decorative, className = "" }: Props) {
  // Remember WHICH url failed, so switching to another colour tries again.
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  if (failedUrl === image.url) return <>{fallback}</>;
  return (
    <Image
      src={image.url}
      alt={decorative ? "" : image.alt_text}
      fill
      sizes={sizes}
      loading={eager ? "eager" : "lazy"}
      onError={() => setFailedUrl(image.url)}
      className={`object-cover ${className}`}
    />
  );
}

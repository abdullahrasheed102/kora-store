import Image from "next/image";

import { NAV_CATEGORIES } from "@/lib/site";
import { CATEGORY_PHOTOS } from "@/lib/site-images";

/** The top of a category page: the category's photo with its name over it, or a plain styled
 *  banner for categories without a photo (Gift Cards). The <h1> lives here. */
export function CategoryBanner({ slug, name }: { slug: string; name: string }) {
  const photo = CATEGORY_PHOTOS[slug];
  const blurb = NAV_CATEGORIES.find((category) => category.slug === slug)?.blurb;

  if (!photo) {
    return (
      <div className="mt-6 rounded-sm bg-sage px-6 py-12 sm:px-10 sm:py-16">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">Kora Outfitters</p>
        <h1 className="mt-3 font-serif text-4xl tracking-tight sm:text-6xl">{name}</h1>
        {blurb && <p className="mt-3 max-w-md text-ink/75">{blurb}</p>}
      </div>
    );
  }

  return (
    <div className="relative isolate mt-6 flex aspect-[4/3] items-end overflow-hidden rounded-sm bg-ink sm:aspect-[3/1]">
      <Image
        src={photo.src}
        alt={photo.alt}
        fill
        placeholder="blur"
        // The banner is page-wide, capped at the 1280px content width.
        sizes="(min-width: 1280px) 1216px, (min-width: 640px) calc(100vw - 48px), calc(100vw - 32px)"
        className="-z-20 object-cover"
        style={{ objectPosition: photo.focus }}
      />
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-linear-to-t from-ink/80 via-ink/25 to-ink/0 sm:bg-linear-to-r sm:from-ink/75 sm:via-ink/20" />
      <div className="max-w-md p-6 text-paper sm:p-10">
        <h1 className="font-serif text-4xl tracking-tight sm:text-6xl">{name}</h1>
        {blurb && <p className="mt-2 text-paper/85">{blurb}</p>}
      </div>
    </div>
  );
}

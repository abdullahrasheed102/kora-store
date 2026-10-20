import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { ABOUT_PHOTO } from "@/lib/site-images";

export const metadata: Metadata = {
  title: "About",
  description: "Kora Outfitters makes a small collection of everyday clothing in natural fibres, designed to last.",
};

const VALUES = [
  { title: "Fewer, better pieces", text: "A small collection we can stand behind, rather than a new trend every week." },
  { title: "Natural fibres", text: "Organic cotton, linen, merino and recycled fills, chosen to wear well and age well." },
  { title: "Made to be worn", text: "Cut for real life, with fit notes on every product and free exchanges if it's not right." },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-12 sm:px-6 lg:px-8">
      <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">About Kora</p>
          <h1 className="mt-4 font-serif text-5xl leading-tight tracking-tight">Designed slowly, worn daily.</h1>
          <p className="mt-6 text-lg leading-relaxed text-ink/80">
            Every Kora piece starts on a worktable like this one: fabric swatches, paper patterns and a lot of trying
            things on. We design for fit and fabric first, and keep our collection small so each piece earns its place.
          </p>
        </div>
        <div className="relative aspect-[3/2] overflow-hidden rounded-sm bg-line">
          <Image
            src={ABOUT_PHOTO.src}
            alt={ABOUT_PHOTO.alt}
            fill
            placeholder="blur"
            sizes="(min-width: 1280px) 600px, (min-width: 1024px) 50vw, calc(100vw - 32px)"
            className="object-cover"
          />
        </div>
      </div>

      <ul className="mt-20 grid gap-8 border-t border-line pt-12 sm:grid-cols-3">
        {VALUES.map((value) => (
          <li key={value.title}>
            <h2 className="font-serif text-2xl">{value.title}</h2>
            <p className="mt-2 leading-relaxed text-ink/75">{value.text}</p>
          </li>
        ))}
      </ul>

      <div className="mt-16 rounded-sm bg-sage p-8 sm:p-10">
        <h2 className="font-serif text-2xl">Find your everyday pieces</h2>
        <p className="mt-3 max-w-2xl leading-relaxed text-ink/80">
          Organic cotton tees, linen shirts, merino knits and coats made for many winters, cut to fit well and made
          to be worn for years.
        </p>
        <Link href="/shop" className="mt-6 inline-block rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper hover:bg-accent">
          Browse the collection
        </Link>
      </div>
    </div>
  );
}

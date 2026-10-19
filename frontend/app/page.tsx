import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import { NewsletterForm } from "@/components/home/newsletter-form";
import { ProductRow } from "@/components/home/product-row";
import { ChatIcon, ReturnIcon, TruckIcon } from "@/components/icons";
import { Reveal } from "@/components/motion/reveal";
import { ProductArt } from "@/components/product-art";
import { ProductCard, ProductGrid } from "@/components/product-card";
import { ProductPhoto } from "@/components/product-photo";
import { ProductGridSkeleton } from "@/components/skeletons";
import { api } from "@/lib/api";
import { ASSISTANT, NAV_CATEGORIES } from "@/lib/site";
import { CATEGORY_PHOTOS, HERO_PHOTO } from "@/lib/site-images";

// Every product section below is chosen by a TAG, not by product ids. Re-tag products in the
// admin and the homepage changes on the next request, with no code change.
const TAG_NEW = "new";
const TAG_EDIT = "autumn-edit";
const TAG_BESTSELLER = "bestseller";

// The three policies shown in the perks strip, with their icons. The text comes from the database.
const PERK_POLICIES = [
  { key: "shipping", icon: TruckIcon },
  { key: "returns", icon: ReturnIcon },
  { key: "support_hours", icon: ChatIcon },
] as const;

// ~1.4 cards visible on phones (the next one peeks in), 2.5 on tablets, 4 on desktops.
const ROW_ITEM_CLASS = "w-[70%] shrink-0 snap-start sm:w-[40%] md:w-[31%] lg:w-[calc((100%-4.5rem)/4)]";

export default function HomePage() {
  return (
    <>
      <section aria-labelledby="hero-heading" className="relative isolate overflow-hidden bg-ink">
        {/* The image is NOT animated: it's the largest thing on screen (LCP) and must paint at once. */}
        <Image
          src={HERO_PHOTO.src}
          alt={HERO_PHOTO.alt}
          fill
          preload // the largest thing on screen (LCP): start downloading it from the <head>
          placeholder="blur"
          sizes="100vw"
          className="-z-20 object-cover"
          style={{ objectPosition: HERO_PHOTO.focus }}
        />
        {/* Darkens only where the text sits: the bottom on phones, the left side from tablets up. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-linear-to-t from-ink/90 via-ink/60 to-ink/0 sm:bg-linear-to-r sm:from-ink/80 sm:via-ink/35 sm:to-ink/0"
        />
        <div className="mx-auto flex min-h-[78svh] max-w-7xl items-end px-4 pb-14 pt-32 sm:items-center sm:px-6 sm:py-24 lg:px-8">
          {/* Plain CSS animation (no JavaScript needed), staggered by 80ms per line. */}
          <div className="max-w-md text-paper sm:w-1/2 lg:w-1/3">
            <p className="animate-fade-up text-xs font-medium uppercase tracking-[0.2em] text-sage">Autumn edit</p>
            <h1
              id="hero-heading"
              className="mt-4 animate-fade-up font-serif text-5xl font-medium leading-[1.05] tracking-tight [animation-delay:80ms] sm:text-6xl"
            >
              Clothes you&apos;ll reach for every day.
            </h1>
            <p className="mt-5 animate-fade-up text-lg leading-relaxed text-paper/85 [animation-delay:160ms]">
              Honest basics in organic cotton, linen and merino. Cut to fit well, made to wear for years.
            </p>
            <div className="mt-8 flex animate-fade-up flex-wrap gap-3 [animation-delay:240ms]">
              <Link href="/shop" className="rounded-full bg-paper px-7 py-3.5 text-sm font-medium text-ink transition hover:bg-sage">
                Shop now
              </Link>
              <Link
                href="/shop/outerwear"
                className="rounded-full border border-paper/50 px-7 py-3.5 text-sm font-medium text-paper transition hover:border-paper hover:bg-paper/10"
              >
                New outerwear
              </Link>
            </div>
          </div>
        </div>
      </section>

      <Section id="categories-heading">
        <SectionHeading id="categories-heading" title="Shop by category" />
        <ul className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          {NAV_CATEGORIES.map((category) => {
            const photo = CATEGORY_PHOTOS[category.slug];
            return (
              <li key={category.slug}>
                <Link href={`/shop/${category.slug}`} className="group block">
                  <div className="relative aspect-[4/5] overflow-hidden rounded-sm bg-line">
                    {photo ? (
                      <Image
                        src={photo.src}
                        alt={photo.alt}
                        fill
                        placeholder="blur"
                        // Tile width at each breakpoint, so phones download a ~400px version, not 1200px.
                        sizes="(min-width: 1280px) 200px, (min-width: 1024px) 16vw, (min-width: 768px) 33vw, 50vw"
                        className="object-cover transition-transform duration-500 ease-calm motion-safe:group-hover:scale-[1.04]"
                        style={{ objectPosition: photo.focus }}
                      />
                    ) : (
                      <ProductArt name={category.name} slug="gift-card" categorySlug={category.slug} color="Clay" className="h-full w-full" />
                    )}
                  </div>
                  <p className="mt-3 font-serif text-lg group-hover:text-accent">{category.name}</p>
                </Link>
              </li>
            );
          })}
        </ul>
      </Section>

      <Section id="new-heading">
        <SectionHeading id="new-heading" title="New for autumn" link={{ href: `/shop?tag=${TAG_NEW}`, label: "See all new" }} />
        <div className="mt-8">
          {/* Static shell above; the live product list streams in at request time. */}
          <Suspense fallback={<ProductGridSkeleton count={4} />}>
            <NewArrivals />
          </Suspense>
        </div>
      </Section>

      <Section id="edit-heading">
        <Suspense fallback={<EditSkeleton />}>
          <AutumnEdit />
        </Suspense>
      </Section>

      <Section id="bestsellers-heading">
        <SectionHeading id="bestsellers-heading" title="Bestsellers" link={{ href: `/shop?tag=${TAG_BESTSELLER}`, label: "Shop bestsellers" }} />
        <div className="mt-8">
          <Suspense fallback={<ProductGridSkeleton count={4} />}>
            <Bestsellers />
          </Suspense>
        </div>
      </Section>

      <Section id="assistant-heading">
        <AssistantTeaser />
      </Section>

      <Section label="Why shop with us">
        <Suspense fallback={<PerksSkeleton />}>
          <Perks />
        </Suspense>
      </Section>

      <Section id="newsletter-heading" className="mb-4">
        <div className="grid items-center gap-8 border-t border-line pt-16 lg:grid-cols-2 lg:gap-16">
          <div>
            <h2 id="newsletter-heading" className="font-serif text-3xl tracking-tight sm:text-4xl">
              Letters from Kora
            </h2>
            <p className="mt-3 max-w-md leading-relaxed text-ink/75">
              New pieces, care guides and the occasional early sale. One email a month, never more. Unsubscribe any time.
            </p>
          </div>
          <NewsletterForm />
        </div>
      </Section>
    </>
  );
}

// --- data sections (each streams in on its own) -------------------------------------------------

async function NewArrivals() {
  const { items } = await api.products({ tag: TAG_NEW, sort: "newest", per_page: 12 });
  if (items.length === 0) return <EmptyNote>New pieces are on their way.</EmptyNote>;
  return (
    <ProductRow label="New for autumn">
      {items.map((product) => (
        <li key={product.slug} className={ROW_ITEM_CLASS}>
          <ProductCard product={product} />
        </li>
      ))}
    </ProductRow>
  );
}

async function AutumnEdit() {
  const { items } = await api.products({ tag: TAG_EDIT, sort: "best_selling", per_page: 3 });
  if (items.length === 0) return null; // nothing tagged: the section simply doesn't show
  // The big photo is a lifestyle shot of a product in the edit, so it always matches the products.
  const photo = items.flatMap((product) => product.images).find((image) => image.kind === "lifestyle");
  const fallback = CATEGORY_PHOTOS.outerwear!;
  const fallbackImage = (
    <Image src={fallback.src} alt={fallback.alt} fill placeholder="blur" sizes={EDIT_PHOTO_SIZES} className="object-cover" />
  );

  return (
    <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
      <div className="relative aspect-[4/5] overflow-hidden rounded-sm bg-line">
        {photo ? <ProductPhoto image={photo} fallback={fallbackImage} sizes={EDIT_PHOTO_SIZES} /> : fallbackImage}
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">The Autumn Edit</p>
        <h2 id="edit-heading" className="mt-4 font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
          Layers for cold mornings.
        </h2>
        <p className="mt-5 max-w-md leading-relaxed text-ink/75">
          A wool overcoat, a merino knit and boots made to be resoled. Three pieces we reach for as the days get
          shorter, chosen to work together and to last for many autumns.
        </p>
        <ul className="mt-8 grid grid-cols-3 gap-3 sm:gap-4">
          {items.map((product) => (
            <li key={product.slug}>
              <ProductCard product={product} />
            </li>
          ))}
        </ul>
        <Link
          href={`/shop?tag=${TAG_EDIT}`}
          className="mt-8 inline-block rounded-full bg-ink px-7 py-3.5 text-sm font-medium text-paper transition-colors duration-300 hover:bg-accent"
        >
          Shop the edit
        </Link>
      </div>
    </div>
  );
}

const EDIT_PHOTO_SIZES = "(min-width: 1280px) 600px, (min-width: 1024px) 50vw, calc(100vw - 32px)";

async function Bestsellers() {
  const { items } = await api.products({ tag: TAG_BESTSELLER, sort: "best_selling", per_page: 4 });
  return <ProductGrid products={items} />;
}

async function Perks() {
  const policies = await api.policies();
  const perks = PERK_POLICIES.flatMap(({ key, icon }) => {
    const policy = policies.find((item) => item.key === key);
    return policy?.summary ? [{ policy, summary: policy.summary, Icon: icon }] : [];
  });
  return (
    <ul className="grid gap-8 rounded-sm bg-sage px-6 py-12 sm:grid-cols-3 sm:px-10">
      {perks.map(({ policy, summary, Icon }) => (
        <li key={policy.key}>
          <Icon className="size-7 text-accent" />
          <h3 className="mt-4 font-serif text-xl leading-snug">{summary}</h3>
          <Link href={`/policies/${policy.key}`} className="mt-2 inline-block text-sm text-ink/75 underline-offset-4 hover:text-ink hover:underline">
            {policy.title} policy
          </Link>
        </li>
      ))}
    </ul>
  );
}

// --- static sections ----------------------------------------------------------------------------

const CHAT_PREVIEW = [
  { from: "customer", text: "Where's my order KO-1004?" },
  { from: "kora", text: "It shipped yesterday and should arrive on Thursday. Want the tracking link?" },
  { from: "customer", text: "Yes please. And can I swap the tee for a size M?" },
  { from: "kora", text: "Here's your link. Exchanges are free, so I can start one for you now." },
] as const;

function AssistantTeaser() {
  return (
    <div className="grid items-center gap-10 overflow-hidden rounded-sm bg-ink px-6 py-12 text-paper sm:px-10 lg:grid-cols-2 lg:gap-16 lg:px-14 lg:py-16">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-sage">Help, any time</p>
        <h2 id="assistant-heading" className="mt-4 font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
          Meet {ASSISTANT.name}, your AI assistant.
        </h2>
        <p className="mt-5 max-w-md leading-relaxed text-paper/80">
          {ASSISTANT.name} tracks your orders, helps you find your size and handles returns and exchanges, 24 hours a
          day, 7 days a week. Our team is here on weekdays for anything else.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-4">
          {ASSISTANT.enabled ? (
            <Link href={ASSISTANT.href} className="rounded-full bg-paper px-7 py-3.5 text-sm font-medium text-ink transition hover:bg-sage">
              Try it
            </Link>
          ) : (
            <button
              type="button"
              disabled
              className="cursor-not-allowed rounded-full border border-paper/40 px-7 py-3.5 text-sm font-medium text-paper/80"
            >
              Coming soon
            </button>
          )}
          <Link href="/contact" className="text-sm text-paper/80 underline underline-offset-4 hover:text-paper">
            Or contact our team
          </Link>
        </div>
      </div>

      {/* A picture of a conversation, not a working chat: the caption says so for screen readers. */}
      <figure className="mx-auto w-full max-w-md rounded-2xl bg-paper p-5 text-ink shadow-2xl shadow-black/30 sm:p-6">
        <figcaption className="flex items-center gap-3 border-b border-line pb-4">
          <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-full bg-sage font-serif text-lg">
            K
          </span>
          <span>
            <span className="block text-sm font-medium">{ASSISTANT.name}</span>
            <span className="block text-xs text-muted">Example conversation</span>
          </span>
        </figcaption>
        <ol className="mt-5 space-y-3 text-sm leading-relaxed">
          {CHAT_PREVIEW.map((message, index) => (
            <li key={index} className={message.from === "customer" ? "flex justify-end" : "flex justify-start"}>
              <Reveal delay={0.15 + index * 0.12}>
                <p
                  className={
                    message.from === "customer"
                      ? "max-w-[85%] rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-paper"
                      : "max-w-[85%] rounded-2xl rounded-bl-sm bg-sage px-4 py-2.5"
                  }
                >
                  <span className="sr-only">{message.from === "customer" ? "Customer: " : `${ASSISTANT.name}: `}</span>
                  {message.text}
                </p>
              </Reveal>
            </li>
          ))}
        </ol>
      </figure>
    </div>
  );
}

// --- layout helpers -----------------------------------------------------------------------------

/** A homepage section that fades up once as it scrolls into view. */
function Section({ id, label, className = "", children }: { id?: string; label?: string; className?: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} aria-label={label} className={`mx-auto mt-24 max-w-7xl px-4 sm:px-6 lg:px-8 ${className}`}>
      <Reveal>{children}</Reveal>
    </section>
  );
}

function SectionHeading({ id, title, link }: { id: string; title: string; link?: { href: string; label: string } }) {
  return (
    <div className="flex items-end justify-between gap-4 border-b border-line pb-4">
      <h2 id={id} className="font-serif text-3xl tracking-tight sm:text-4xl">
        {title}
      </h2>
      {link && (
        <Link href={link.href} className="shrink-0 text-sm font-medium underline-offset-4 hover:text-accent hover:underline">
          {link.label}
        </Link>
      )}
    </div>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="rounded-sm border border-dashed border-line px-6 py-12 text-center text-muted">{children}</p>;
}

function EditSkeleton() {
  return (
    <div className="grid gap-10 lg:grid-cols-2 lg:gap-16" aria-hidden="true">
      <div className="aspect-[4/5] animate-pulse rounded-sm bg-line/70" />
      <div className="space-y-4 self-center">
        <div className="h-4 w-32 animate-pulse rounded-sm bg-line/70" />
        <div className="h-12 w-3/4 animate-pulse rounded-sm bg-line/70" />
        <div className="h-20 w-full animate-pulse rounded-sm bg-line/70" />
      </div>
    </div>
  );
}

function PerksSkeleton() {
  return <div aria-hidden="true" className="h-64 animate-pulse rounded-sm bg-sage sm:h-52" />;
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ChevronIcon } from "@/components/icons";

/**
 * A horizontal row of product cards. On phones you swipe (native scrolling with scroll-snap);
 * from tablets up, arrow buttons scroll one "page" at a time.
 *
 * The cards are rendered on the server and passed in as children: this component only adds
 * scrolling behaviour, so the cards' code isn't sent to the browser twice.
 */
export function ProductRow({ label, children }: { label: string; children: React.ReactNode }) {
  const list = useRef<HTMLUListElement>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const updateEdges = useCallback(() => {
    const element = list.current;
    if (!element) return;
    setAtStart(element.scrollLeft <= 4);
    setAtEnd(element.scrollLeft + element.clientWidth >= element.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const element = list.current;
    if (!element) return;
    updateEdges();
    element.addEventListener("scroll", updateEdges, { passive: true });
    window.addEventListener("resize", updateEdges);
    return () => {
      element.removeEventListener("scroll", updateEdges);
      window.removeEventListener("resize", updateEdges);
    };
  }, [updateEdges]);

  function scrollPage(direction: 1 | -1) {
    const element = list.current;
    if (!element) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    element.scrollBy({ left: direction * element.clientWidth * 0.9, behavior: reduce ? "auto" : "smooth" });
  }

  const arrow =
    "absolute top-[38%] z-10 hidden size-11 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-paper/95 shadow-sm transition-opacity duration-300 hover:border-ink md:flex";
  return (
    <div className="relative">
      <ul
        ref={list}
        aria-label={label}
        // Bleeds to the screen edge on phones so the next card peeks in: a hint that it scrolls.
        className="-mx-4 flex snap-x snap-mandatory scroll-px-4 gap-4 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:-mx-6 sm:scroll-px-6 sm:px-6 lg:mx-0 lg:scroll-px-0 lg:gap-6 lg:px-0 [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </ul>
      <button
        type="button"
        aria-label="Scroll back"
        onClick={() => scrollPage(-1)}
        disabled={atStart}
        className={`${arrow} -left-5 ${atStart ? "pointer-events-none opacity-0" : "opacity-100"}`}
      >
        <ChevronIcon className="size-4 rotate-180" />
      </button>
      <button
        type="button"
        aria-label="Scroll forward"
        onClick={() => scrollPage(1)}
        disabled={atEnd}
        className={`${arrow} -right-5 ${atEnd ? "pointer-events-none opacity-0" : "opacity-100"}`}
      >
        <ChevronIcon className="size-4" />
      </button>
    </div>
  );
}


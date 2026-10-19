"use client";

import { LazyMotion, MotionConfig, domAnimation } from "motion/react";

/**
 * Site-wide animation settings.
 * - reducedMotion="user": if the visitor's system asks for reduced motion, Motion skips every
 *   movement (transforms) and keeps only fades.
 * - LazyMotion + domAnimation + the small `m` components (see reveal.tsx) load only the
 *   animation features we use, instead of the whole library. `strict` makes using the big
 *   `motion` component by mistake an error.
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domAnimation} strict>
        {children}
      </LazyMotion>
    </MotionConfig>
  );
}

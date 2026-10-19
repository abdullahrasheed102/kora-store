"use client";

import * as m from "motion/react-m";

// One calm curve for the whole site: starts quickly, settles gently, never overshoots (no bounce).
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

type Props = {
  children: React.ReactNode;
  className?: string;
  delay?: number; // seconds, for a small stagger between siblings
};

/**
 * Fades its content up a little the first time it scrolls into view, then never again.
 * Only opacity and transform change, which the browser animates without re-doing layout,
 * so nothing around it moves (no layout shift).
 */
export function Reveal({ children, className, delay = 0 }: Props) {
  return (
    <m.div
      data-reveal // lets the <noscript> rule in app/layout.tsx show it when JavaScript is off
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.5, ease: EASE_OUT, delay }}
    >
      {children}
    </m.div>
  );
}

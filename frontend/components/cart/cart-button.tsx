"use client";

import { useCart } from "@/components/cart/cart-provider";
import { BagIcon } from "@/components/icons";

export function CartButton() {
  const { count, openDrawer } = useCart();
  return (
    <button
      type="button"
      onClick={openDrawer}
      className="relative inline-flex size-10 items-center justify-center rounded-full hover:bg-line/60"
      aria-label={`Shopping bag, ${count} ${count === 1 ? "item" : "items"}`}
    >
      <BagIcon className="size-6" />
      {count > 0 && (
        <span
          aria-hidden="true"
          className="absolute right-0.5 top-0.5 flex size-4 items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-white"
        >
          {count > 9 ? "9+" : count}
        </span>
      )}
    </button>
  );
}

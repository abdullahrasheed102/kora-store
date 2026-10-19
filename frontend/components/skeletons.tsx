// Placeholders shown while data streams in. They match the real layout, so nothing jumps.

function Bar({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-sm bg-line/70 ${className}`} />;
}

export function ProductGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:gap-x-6 xl:grid-cols-4" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <li key={index} className="space-y-3">
          <Bar className="aspect-[4/5]" />
          <Bar className="h-4 w-3/4" />
          <Bar className="h-3 w-1/3" />
        </li>
      ))}
    </ul>
  );
}

export function ShopSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading products">
      <Bar className="h-10 w-56" />
      <Bar className="mt-3 h-4 w-24" />
      <div className="mt-10 grid gap-10 lg:grid-cols-[220px_1fr]">
        <div className="hidden space-y-4 lg:block">
          {Array.from({ length: 6 }, (_, index) => (
            <Bar key={index} className="h-4 w-3/4" />
          ))}
        </div>
        <ProductGridSkeleton count={9} />
      </div>
    </div>
  );
}

export function ProductDetailSkeleton() {
  return (
    <div className="grid gap-10 lg:grid-cols-2" aria-busy="true" aria-label="Loading product">
      <Bar className="aspect-[4/5]" />
      <div className="space-y-4 pt-4">
        <Bar className="h-3 w-24" />
        <Bar className="h-10 w-3/4" />
        <Bar className="h-6 w-20" />
        <Bar className="h-20 w-full" />
        <Bar className="h-12 w-full" />
      </div>
    </div>
  );
}

export function TextSkeleton({ lines = 4 }: { lines?: number }) {
  return (
    <div className="space-y-3" aria-busy="true">
      {Array.from({ length: lines }, (_, index) => (
        <Bar key={index} className={`h-4 ${index === lines - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

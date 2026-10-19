// Small inline icons (stroke style, 24px grid). aria-hidden: always paired with visible or sr-only text.
type IconProps = { className?: string };

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
  "aria-hidden": true,
};

export const SearchIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...base} className={className}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export const BagIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M5 8h14l-1 12H6L5 8Z" />
    <path d="M9 8V6a3 3 0 0 1 6 0v2" />
  </svg>
);

export const MenuIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

export const CloseIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export const TruckIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M3 7h11v9H3zM14 10h4l3 3v3h-7" />
    <circle cx="7" cy="17.5" r="1.5" />
    <circle cx="17" cy="17.5" r="1.5" />
  </svg>
);

export const ReturnIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h10a6 6 0 0 1 0 12h-3" />
  </svg>
);

export const ChatIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M4 5h16v11H9l-5 4V5Z" />
    <path d="M8 10h8M8 13h5" />
  </svg>
);

export const LeafIcon = ({ className = "size-6" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M5 19c0-8 6-14 15-14 0 9-6 15-14 15" />
    <path d="M5 19 13 11" />
  </svg>
);

export const ChevronIcon = ({ className = "size-4" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="m9 6 6 6-6 6" />
  </svg>
);

export const FilterIcon = ({ className = "size-4" }: IconProps) => (
  <svg {...base} className={className}>
    <path d="M4 6h16M7 12h10M10 18h4" />
  </svg>
);

export const UserIcon = ({ className = "size-5" }: IconProps) => (
  <svg {...base} className={className}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
  </svg>
);

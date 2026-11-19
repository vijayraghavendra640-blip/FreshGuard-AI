import { useId } from 'react';

/** FreshGuard mark: emerald gradient shield with a check on a dark tile. Same artwork as public/favicon.svg. */
export function Logo({ size = 32 }: { size?: number }) {
  const id = useId().replace(/:/g, '');
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="logo">
      <defs>
        <linearGradient id={`${id}-tile`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#27272a" />
          <stop offset="1" stopColor="#09090b" />
        </linearGradient>
        <linearGradient id={`${id}-shield`} x1="0.2" y1="0" x2="0.8" y2="1">
          <stop offset="0" stopColor="#6ee7b7" />
          <stop offset="0.55" stopColor="#10b981" />
          <stop offset="1" stopColor="#047857" />
        </linearGradient>
        <linearGradient id={`${id}-shine`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.45" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="62" height="62" rx="16" fill={`url(#${id}-tile)`} />
      <rect x="1.5" y="1.5" width="61" height="61" rx="15.5" fill="none" stroke="#ffffff" strokeOpacity="0.12" />
      <path d="M32 11.5 47.5 17v12.6c0 10.6-6.5 18.3-15.5 22.4-9-4.1-15.5-11.8-15.5-22.4V17z" fill={`url(#${id}-shield)`} />
      <path d="M32 11.5 47.5 17v6c-5 2.6-10.2 3.9-15.5 3.9S21.5 25.6 16.5 23v-6z" fill={`url(#${id}-shine)`} />
      <path d="m24.5 31.5 5.2 5.2 10-10.4" fill="none" stroke="#ffffff" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

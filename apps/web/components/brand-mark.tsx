"use client";

import { useId } from "react";

/** ADDA AI ribbon mark — gradient follows theme CSS variables. */
export default function BrandMark({ className = "brand-icon", title = "ADDA AI" }: { className?: string; title?: string }) {
  const uid = useId().replace(/:/g, "");
  const gid = `addaGrad-${uid}`;
  const soft = `addaSoft-${uid}`;
  const spark = `addaSpark-${uid}`;
  return (
    <span className={className} title={title}>
      <svg viewBox="0 0 64 64" width="100%" height="100%" role="img" aria-label={title}>
        <defs>
          <linearGradient id={gid} x1="8%" y1="18%" x2="92%" y2="88%">
            <stop offset="0%" stopColor="var(--logo-from)" />
            <stop offset="48%" stopColor="var(--logo-mid)" />
            <stop offset="100%" stopColor="var(--logo-to)" />
          </linearGradient>
          <linearGradient id={soft} x1="20%" y1="0%" x2="80%" y2="100%">
            <stop offset="0%" stopColor="var(--logo-from)" stopOpacity="0.95" />
            <stop offset="100%" stopColor="var(--logo-to)" stopOpacity="0.92" />
          </linearGradient>
          <radialGradient id={spark} cx="50%" cy="35%" r="55%">
            <stop offset="0%" stopColor="var(--logo-spark)" stopOpacity="1" />
            <stop offset="55%" stopColor="var(--logo-spark)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--logo-spark)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path fill={`url(#${gid})`} d="M31.2 6.2c-1.1-.2-2.2.4-2.7 1.4L8.4 52.2c-.5 1.1.1 2.4 1.3 2.8 2.4.8 4.7-.4 5.6-2.4l7.4-16.2c.4-.9 1.3-1.4 2.3-1.4h7.1c1.4 0 2.4-1.4 1.9-2.7L31.2 6.2Z" />
        <path fill={`url(#${soft})`} d="M32.8 6.2c1.1-.2 2.2.4 2.7 1.4l20.1 44.6c.5 1.1-.1 2.4-1.3 2.8-2.4.8-4.7-.4-5.6-2.4l-7.4-16.2c-.4-.9-1.3-1.4-2.3-1.4h-7.1c-1.4 0-2.4-1.4-1.9-2.7L32.8 6.2Z" />
        <path fill={`url(#${gid})`} d="M18.6 36.8c8.2-3.4 13.1-1.2 18.8 1.6 3.2 1.6 6.7 2.2 9.8.2 1.2-.8 1.5-2.4.6-3.5-.9-1.1-2.5-1.3-3.7-.5-1.7 1.1-3.7.8-5.7-.1-6.2-2.9-12.1-5.2-21.4-1.4-1.3.5-1.9 2-.1 3.1.5.4 1.1.6 1.7.6Z" />
        <path fill="none" stroke="var(--logo-spark)" strokeOpacity="0.35" strokeWidth="1.2" strokeLinecap="round" d="M30.5 10.5 19.8 34.2M33.5 10.5 44.2 34.2" />
        <g transform="translate(32 22)">
          <circle r="5.5" fill={`url(#${spark})`} />
          <path fill="var(--logo-spark)" d="M0-4.2 1.1-1.1 4.2 0 1.1 1.1 0 4.2-1.1 1.1-4.2 0-1.1-1.1Z" />
        </g>
      </svg>
    </span>
  );
}

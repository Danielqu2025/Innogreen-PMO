/** 侧栏描边图标（与 Portal / qcc 同一套 24 viewBox stroke） */
import type { ReactNode } from "react";

type IconProps = { className?: string };

function Ico({
  children,
  className = "shell-side-ico",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={className} aria-hidden="true">
      <svg viewBox="0 0 24 24">{children}</svg>
    </span>
  );
}

export function SideIconDashboard(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M4 4h7v7H4z" />
      <path d="M13 4h7v5h-7z" />
      <path d="M13 11h7v9h-7z" />
      <path d="M4 13h7v7H4z" />
    </Ico>
  );
}

export function SideIconTeam(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="3.5" />
      <path d="M22 21v-2a3.5 3.5 0 0 0-2.5-3.35" />
      <path d="M16.5 3.6a3.5 3.5 0 0 1 0 6.8" />
    </Ico>
  );
}

export function SideIconStages(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <circle cx="12" cy="18" r="2.5" />
      <path d="M8.2 7.5 10.5 15" />
      <path d="M15.8 7.5 13.5 15" />
    </Ico>
  );
}

export function SideIconWarning(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M12 3 3 20h18L12 3z" />
      <path d="M12 9v5" />
      <path d="M12 17h.01" />
    </Ico>
  );
}

export function SideIconSettings(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8" />
    </Ico>
  );
}

export function SideIconList(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M8 6h12M8 12h12M8 18h12" />
      <path d="M4 6h.01M4 12h.01M4 18h.01" />
    </Ico>
  );
}

export function SideIconUser(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="3.5" />
      <path d="M22 21v-2a3.5 3.5 0 0 0-2.5-3.35" />
      <path d="M16.5 3.6a3.5 3.5 0 0 1 0 6.8" />
    </Ico>
  );
}

export function SideIconExport(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M12 4v12" />
      <path d="m7 11 5 5 5-5" />
      <path d="M4 20h16" />
    </Ico>
  );
}

export function SideIconImport(p?: IconProps) {
  return (
    <Ico className={p?.className}>
      <path d="M12 16V4" />
      <path d="m7 9 5-5 5 5" />
      <path d="M4 20h16" />
    </Ico>
  );
}

export function SideIconCaret(p?: IconProps) {
  return (
    <span className={p?.className ?? "shell-side-caret"} aria-hidden="true">
      <svg viewBox="0 0 24 24" width="12" height="12">
        <path
          d="m9 6 6 6-6 6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

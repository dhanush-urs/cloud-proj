import { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
};

export function Card({ children, className = "" }: Props) {
  return (
    <div
      className={`rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow ${className}`}
    >
      {children}
    </div>
  );
}

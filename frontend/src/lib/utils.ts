import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const PRIORITY_CONFIG: Record<number, { label: string; color: string; bg: string; border: string }> = {
  1: { label: "CRITICAL", color: "text-red-600", bg: "bg-red-50", border: "border-red-500" },
  2: { label: "URGENT", color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-500" },
  3: { label: "STANDARD", color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-500" },
  4: { label: "LOW RISK", color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-500" },
  5: { label: "LOW RISK", color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-400" },
};

export const CONFIDENCE_CONFIG: Record<string, { color: string; bg: string }> = {
  High: { color: "text-green-700", bg: "bg-green-100" },
  Medium: { color: "text-amber-700", bg: "bg-amber-100" },
  Low: { color: "text-red-700", bg: "bg-red-100" },
};

export function formatWait(minutes: number): string {
  if (minutes < 1) return "<1m";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

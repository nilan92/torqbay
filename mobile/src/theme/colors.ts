import { Color } from "expo-router";
import { Platform, useColorScheme } from "react-native";

/** Chrome: native semantic colors, so light/dark and accessibility adapt for free. */
export const colors = {
  label: Platform.select({
    ios: Color.ios.label,
    android: Color.android.dynamic.onSurface,
    default: "#111111",
  })!,
  secondaryLabel: Platform.select({
    ios: Color.ios.secondaryLabel,
    android: Color.android.dynamic.onSurfaceVariant,
    default: "#5B5B60",
  })!,
  separator: Platform.select({
    ios: Color.ios.separator,
    android: Color.android.dynamic.outlineVariant,
    default: "#D6D6DA",
  })!,
  background: Platform.select({
    ios: Color.ios.systemBackground,
    android: Color.android.dynamic.surface,
    default: "#FFFFFF",
  })!,
  groupedBackground: Platform.select({
    ios: Color.ios.secondarySystemBackground,
    android: Color.android.dynamic.surfaceVariant,
    default: "#F2F2F7",
  })!,
};

/** Identity and status: fixed values, chosen to stay legible in direct sunlight. */
const palette = {
  light: {
    brand: "#0F4C5C",
    accent: "#F4A208",
    danger: "#C92A2A",
    open: "#6B7280",
    in_progress: "#F4A208",
    done: "#2F9E44",
    invoiced: "#0F4C5C",
    paid: "#1B7F3B",
    cancelled: "#9CA3AF",
  },
  dark: {
    brand: "#2A8FA6",
    accent: "#FFB627",
    danger: "#FF6B6B",
    open: "#9CA3AF",
    in_progress: "#FFB627",
    done: "#51CF66",
    invoiced: "#2A8FA6",
    paid: "#40C057",
    cancelled: "#6B7280",
  },
} as const;

export type JobStatus =
  | "open"
  | "in_progress"
  | "done"
  | "invoiced"
  | "paid"
  | "cancelled";

/**
 * Brand and status colors for the active scheme.
 *
 * A hook rather than a constant because Android needs a re-render when the
 * system theme flips; iOS re-resolves semantic colors on its own, but these
 * are fixed values so both platforms need the subscription.
 */
export function useBrandColors() {
  const scheme = useColorScheme();
  return palette[scheme === "dark" ? "dark" : "light"];
}

export function useStatusColor(status: JobStatus | string) {
  const brand = useBrandColors();
  return (brand as Record<string, string>)[status] ?? brand.open;
}

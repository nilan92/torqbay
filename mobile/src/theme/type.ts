import type { TextStyle } from "react-native";

/**
 * One scale, used everywhere. Screen titles come from the navigation stack,
 * so there is deliberately no `screenTitle` entry here.
 */
export const type = {
  title: { fontSize: 28, fontWeight: "700", letterSpacing: -0.4 },
  heading: { fontSize: 20, fontWeight: "600", letterSpacing: -0.2 },
  body: { fontSize: 16, fontWeight: "400" },
  label: { fontSize: 15, fontWeight: "500" },
  caption: { fontSize: 13, fontWeight: "400" },
  overline: {
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  /** Any number that appears in a column, so digits line up. */
  numeric: { fontSize: 16, fontWeight: "500", fontVariant: ["tabular-nums"] },
} satisfies Record<string, TextStyle>;

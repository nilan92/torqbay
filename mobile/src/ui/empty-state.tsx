import { Text, View } from "react-native";

import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";

/** Centers loading/error/empty content — the shape every list screen needs. */
export function Centered({ children }: { children: React.ReactNode }) {
  return (
    <View style={{ padding: spacing.xxl, alignItems: "center", gap: spacing.md }}>
      {children}
    </View>
  );
}

/** A blank screen is dead space; this names what's missing and, when there
 * is one, what fills it — never just "arrives in the next release" on its own. */
export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <Centered>
      <Text style={{ ...type.heading, color: colors.label }}>{title}</Text>
      <Text style={{ ...type.caption, color: colors.secondaryLabel, textAlign: "center" }}>
        {message}
      </Text>
    </Centered>
  );
}

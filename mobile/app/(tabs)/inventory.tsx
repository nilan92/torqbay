import { ScrollView, Text } from "react-native";

import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";

export default function Inventory() {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
    >
      <Text style={{ ...type.body, color: colors.secondaryLabel }}>
        Inventory arrives in the next release.
      </Text>
    </ScrollView>
  );
}

import { ScrollView, Text } from "react-native";

import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";

export default function Jobs() {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg }}
    >
      <Text style={{ ...type.body, color: colors.secondaryLabel }}>Loading jobs…</Text>
    </ScrollView>
  );
}

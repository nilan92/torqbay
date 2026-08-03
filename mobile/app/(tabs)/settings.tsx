import { ScrollView, Text, View } from "react-native";

import { useAuth } from "@/auth/auth-context";
import { colors } from "@/theme/colors";
import { spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";

export default function Settings() {
  const { user, signOut } = useAuth();

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.xl }}
    >
      <View style={{ gap: spacing.xs }}>
        <Text style={{ ...type.overline, color: colors.secondaryLabel }}>Signed in as</Text>
        <Text selectable style={{ ...type.heading, color: colors.label }}>
          {user?.name}
        </Text>
        <Text selectable style={{ ...type.caption, color: colors.secondaryLabel }}>
          {user?.email} · {user?.role}
        </Text>
      </View>

      <Button label="Sign out" onPress={signOut} />
    </ScrollView>
  );
}

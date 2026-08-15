import { Stack } from "expo-router";

import { colors } from "@/theme/colors";

export default function InventoryLayout() {
  return (
    <Stack
      screenOptions={{
        headerTintColor: colors.label as string,
        headerStyle: { backgroundColor: colors.background as string },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Inventory" }} />
      <Stack.Screen name="[id]" options={{ title: "" }} />
      <Stack.Screen name="new" options={{ title: "New item", presentation: "modal" }} />
    </Stack>
  );
}

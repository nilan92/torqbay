import { Stack } from "expo-router";

import { colors } from "@/theme/colors";

export default function CustomersLayout() {
  return (
    <Stack
      screenOptions={{
        headerTintColor: colors.label as string,
        headerStyle: { backgroundColor: colors.background as string },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Customers" }} />
      <Stack.Screen name="[id]" options={{ title: "" }} />
      <Stack.Screen name="new" options={{ title: "New customer", presentation: "modal" }} />
    </Stack>
  );
}

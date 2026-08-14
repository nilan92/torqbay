import { Stack } from "expo-router";

import { colors } from "@/theme/colors";

export default function JobsLayout() {
  return (
    <Stack
      screenOptions={{
        headerTintColor: colors.label as string,
        headerStyle: { backgroundColor: colors.background as string },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Jobs" }} />
      <Stack.Screen name="[id]" options={{ title: "" }} />
    </Stack>
  );
}

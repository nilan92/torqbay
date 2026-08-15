import { Tabs } from "expo-router";
import { Image } from "expo-image";
import { Text, type ColorValue } from "react-native";

import { useAuth } from "@/auth/auth-context";
import { canSeeTab } from "@/auth/permissions";
import { colors, useBrandColors } from "@/theme/colors";

// SF Symbols only render on iOS. On Android/web (most of this app's users,
// who are in Sri Lanka) `sf:` sources come back blank, so those platforms
// fall back to an emoji glyph rather than shipping an empty tab bar.
function TabIcon({
  sfSymbol,
  glyph,
  color,
}: {
  sfSymbol: string;
  glyph: string;
  color: ColorValue;
}) {
  if (process.env.EXPO_OS === "ios") {
    // Safe cast: the tint colors we hand to Tabs are literal strings (see
    // screenOptions below), not DynamicColorIOS objects, even though
    // react-navigation's callback types this as the wider ColorValue.
    return <Image source={`sf:${sfSymbol}`} tintColor={color as string} style={{ width: 26, height: 26 }} />;
  }
  return <Text style={{ fontSize: 22, color }}>{glyph}</Text>;
}

export default function TabsLayout() {
  const { user } = useAuth();
  const brand = useBrandColors();
  const role = user?.role ?? "technician";

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: brand.brand as string,
        tabBarInactiveTintColor: colors.secondaryLabel as string,
        headerTintColor: colors.label as string,
      }}
    >
      <Tabs.Screen
        name="jobs"
        options={{
          title: "Jobs",
          // The jobs tab has its own nested Stack (app/(tabs)/jobs/_layout.tsx)
          // which renders its own header for both the list and the detail
          // screen. Without this, the Tabs navigator's header stacks on top
          // of it — "Jobs" shown twice, once from each navigator.
          headerShown: false,
          tabBarIcon: ({ color }) => (
            <TabIcon sfSymbol="wrench.and.screwdriver" glyph="🔧" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="customers"
        options={{
          title: "Customers",
          // Nested Stack (app/(tabs)/customers/_layout.tsx) provides its own
          // headers — see the same fix on the jobs tab.
          headerShown: false,
          href: canSeeTab(role, "customers") ? undefined : null,
          tabBarIcon: ({ color }) => <TabIcon sfSymbol="person.2" glyph="👥" color={color} />,
        }}
      />
      <Tabs.Screen
        name="inventory"
        options={{
          title: "Inventory",
          // Nested Stack (app/(tabs)/inventory/_layout.tsx) provides its own
          // headers — see the same fix on the jobs tab.
          headerShown: false,
          href: canSeeTab(role, "inventory") ? undefined : null,
          tabBarIcon: ({ color }) => <TabIcon sfSymbol="shippingbox" glyph="📦" color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: ({ color }) => <TabIcon sfSymbol="gearshape" glyph="⚙️" color={color} />,
        }}
      />
    </Tabs>
  );
}

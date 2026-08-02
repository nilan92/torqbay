import { ActivityIndicator, Pressable, Text } from "react-native";

import { useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";

type ButtonProps = {
  label: string;
  onPress: () => void;
  busy?: boolean;
  disabled?: boolean;
};

export function Button({ label, onPress, busy = false, disabled = false }: ButtonProps) {
  const brand = useBrandColors();
  const inactive = disabled || busy;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy }}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => ({
        backgroundColor: brand.brand,
        opacity: inactive ? 0.5 : pressed ? 0.85 : 1,
        paddingVertical: spacing.lg,
        paddingHorizontal: spacing.xl,
        borderRadius: radius.md,
        alignItems: "center",
        justifyContent: "center",
        minHeight: 52,
        ...continuous,
      })}
    >
      {busy ? (
        <ActivityIndicator color="#FFFFFF" />
      ) : (
        <Text style={{ ...type.label, color: "#FFFFFF", fontSize: 17 }}>{label}</Text>
      )}
    </Pressable>
  );
}

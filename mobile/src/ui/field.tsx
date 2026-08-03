import { TextInput, View, Text } from "react-native";
import type { TextInputProps } from "react-native";

import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";

type FieldProps = TextInputProps & {
  label: string;
};

export function Field({ label, ...inputProps }: FieldProps) {
  const brand = useBrandColors();

  return (
    <View style={{ gap: spacing.sm }}>
      <Text style={{ ...type.overline, color: colors.secondaryLabel }}>{label}</Text>
      <TextInput
        {...inputProps}
        placeholderTextColor={colors.secondaryLabel}
        selectionColor={brand.brand}
        style={{
          ...type.body,
          color: colors.label,
          backgroundColor: colors.groupedBackground,
          borderRadius: radius.md,
          paddingHorizontal: spacing.lg,
          paddingVertical: spacing.lg,
          minHeight: 52,
          ...continuous,
        }}
      />
    </View>
  );
}

import { Text, View } from "react-native";

import { type JobStatus, useStatusColor } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";

const LABELS: Record<string, string> = {
  open: "Not started",
  in_progress: "In progress",
  done: "Done",
  invoiced: "Invoiced",
  paid: "Paid",
  cancelled: "Cancelled",
};

export function StatusTag({ status }: { status: JobStatus | string }) {
  const color = useStatusColor(status);

  return (
    <View
      style={{
        alignSelf: "flex-start",
        backgroundColor: `${color}1A`,
        borderLeftWidth: 3,
        borderLeftColor: color,
        paddingVertical: spacing.xs,
        paddingHorizontal: spacing.sm,
        borderRadius: radius.sm,
        ...continuous,
      }}
    >
      <Text style={{ ...type.overline, color }}>{LABELS[status] ?? status}</Text>
    </View>
  );
}

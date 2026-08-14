import { ScrollView } from "react-native";

import { colors } from "@/theme/colors";
import { EmptyState } from "@/ui/empty-state";

export default function Customers() {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}
    >
      <EmptyState
        title="Customers"
        message="Managing customers and their vehicles is coming in the next release."
      />
    </ScrollView>
  );
}

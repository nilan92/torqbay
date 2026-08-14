import { ScrollView } from "react-native";

import { colors } from "@/theme/colors";
import { EmptyState } from "@/ui/empty-state";

export default function Inventory() {
  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}
    >
      <EmptyState
        title="Inventory"
        message="Stock levels and parts tracking are coming in the next release."
      />
    </ScrollView>
  );
}

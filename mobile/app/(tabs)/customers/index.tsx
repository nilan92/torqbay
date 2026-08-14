import { Link } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text } from "react-native";

import { useCustomers, type Customer } from "@/customers/use-customer";
import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { Centered, EmptyState } from "@/ui/empty-state";

function CustomerCard({ customer }: { customer: Customer }) {
  return (
    <Link href={`/(tabs)/customers/${customer.id}`} asChild>
      <Pressable
        style={({ pressed }) => ({
          backgroundColor: colors.groupedBackground,
          borderRadius: radius.md,
          padding: spacing.lg,
          gap: spacing.xs,
          opacity: pressed ? 0.7 : 1,
          ...continuous,
        })}
      >
        <Text selectable style={{ ...type.heading, color: colors.label }}>
          {customer.name}
        </Text>
        {customer.phone ? (
          <Text style={{ ...type.caption, color: colors.secondaryLabel }}>{customer.phone}</Text>
        ) : null}
      </Pressable>
    </Link>
  );
}

export default function Customers() {
  const { data, isLoading, isRefetching, error, refetch } = useCustomers();
  const brand = useBrandColors();

  if (isLoading) {
    return (
      <Centered>
        <ActivityIndicator />
      </Centered>
    );
  }

  if (error) {
    return (
      <Centered>
        <Text selectable style={{ ...type.body, color: brand.danger, textAlign: "center" }}>
          {error instanceof Error ? error.message : "Couldn't load customers."}
        </Text>
        <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
          Pull down to try again.
        </Text>
      </Centered>
    );
  }

  return (
    <FlatList
      contentInsetAdjustmentBehavior="automatic"
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
      data={data?.items ?? []}
      keyExtractor={(customer) => customer.id}
      renderItem={({ item }) => <CustomerCard customer={item} />}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      ListHeaderComponent={
        <Link href="/(tabs)/customers/new" asChild>
          <Button label="Add customer" onPress={() => {}} />
        </Link>
      }
      ListHeaderComponentStyle={{ marginBottom: spacing.md }}
      ListEmptyComponent={
        <EmptyState
          title="No customers yet"
          message="Add your first customer to start creating jobs for them."
        />
      }
    />
  );
}

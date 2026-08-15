import { router } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "@/api/client";
import { useAssets } from "@/customers/use-assets";
import { useCustomers, type Customer } from "@/customers/use-customer";
import { useCreateJob } from "@/jobs/use-jobs";
import { useTechnicians } from "@/technicians/use-technicians";
import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";

function SelectRow({
  primary,
  secondary,
  selected,
  onPress,
}: {
  primary: string;
  secondary?: string;
  selected?: boolean;
  onPress: () => void;
}) {
  const brand = useBrandColors();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        backgroundColor: selected ? `${brand.brand}1A` : colors.groupedBackground,
        borderRadius: radius.md,
        padding: spacing.lg,
        gap: spacing.xs,
        borderWidth: selected ? 1 : 0,
        borderColor: brand.brand,
        opacity: pressed ? 0.7 : 1,
        ...continuous,
      })}
    >
      <Text selectable style={{ ...type.body, color: colors.label }}>
        {primary}
      </Text>
      {secondary ? (
        <Text selectable style={{ ...type.caption, color: colors.secondaryLabel }}>
          {secondary}
        </Text>
      ) : null}
    </Pressable>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: spacing.md }}>
      <Text style={{ ...type.overline, color: colors.secondaryLabel }}>{title}</Text>
      {children}
    </View>
  );
}

export default function NewJob() {
  const brand = useBrandColors();
  const { data: customers, isLoading: customersLoading } = useCustomers();
  const { data: technicians } = useTechnicians();
  const createJob = useCreateJob();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [customerSearch, setCustomerSearch] = useState("");
  const [assetId, setAssetId] = useState<string | null>(null);
  const [technicianId, setTechnicianId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: assets, isLoading: assetsLoading } = useAssets(customer?.id ?? "");

  const filteredCustomers = useMemo(() => {
    const items = customers?.items ?? [];
    const q = customerSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter((c) => c.name.toLowerCase().includes(q));
  }, [customers, customerSearch]);

  const canSubmit = Boolean(customer) && Boolean(assetId) && title.trim().length > 0;

  async function submit() {
    if (!canSubmit || !customer || !assetId) return;
    setError(null);
    try {
      const job = await createJob.mutateAsync({
        customer_id: customer.id,
        asset_id: assetId,
        title: title.trim(),
        description: description.trim() || undefined,
        assigned_technician_id: technicianId ?? undefined,
      });
      router.replace(`/(tabs)/jobs/${job.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't create this job. Try again.");
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={process.env.EXPO_OS === "ios" ? "padding" : undefined}
      style={{ flex: 1 }}
    >
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
        style={{ backgroundColor: colors.background }}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.xl }}
      >
        <Section title="Customer">
          {customer ? (
            <SelectRow
              primary={customer.name}
              secondary={customer.phone ?? undefined}
              selected
              onPress={() => {
                setCustomer(null);
                setAssetId(null);
              }}
            />
          ) : (
            <View style={{ gap: spacing.sm }}>
              <TextInput
                value={customerSearch}
                onChangeText={setCustomerSearch}
                placeholder="Search customers by name"
                placeholderTextColor={colors.secondaryLabel}
                style={{
                  ...type.body,
                  color: colors.label,
                  backgroundColor: colors.groupedBackground,
                  borderRadius: radius.md,
                  paddingHorizontal: spacing.lg,
                  paddingVertical: spacing.md,
                  minHeight: 52,
                  ...continuous,
                }}
              />
              {customersLoading ? (
                <ActivityIndicator />
              ) : (
                filteredCustomers.slice(0, 20).map((c) => (
                  <SelectRow
                    key={c.id}
                    primary={c.name}
                    secondary={c.phone ?? undefined}
                    onPress={() => setCustomer(c)}
                  />
                ))
              )}
            </View>
          )}
        </Section>

        {customer ? (
          <Section title="Vehicle">
            {assetsLoading ? (
              <ActivityIndicator />
            ) : assets?.items.length ? (
              <View style={{ gap: spacing.sm }}>
                {assets.items.map((asset) => (
                  <SelectRow
                    key={asset.id}
                    primary={asset.label}
                    secondary={asset.identifier ?? undefined}
                    selected={assetId === asset.id}
                    onPress={() => setAssetId(asset.id)}
                  />
                ))}
              </View>
            ) : (
              <Text style={{ ...type.caption, color: colors.secondaryLabel }}>
                This customer has no vehicles yet — add one from their customer page first.
              </Text>
            )}
          </Section>
        ) : null}

        <Field label="Title" value={title} onChangeText={setTitle} placeholder="Brake service" />
        <Field
          label="Description (optional)"
          value={description}
          onChangeText={setDescription}
          multiline
        />

        {technicians?.items.length ? (
          <Section title="Assign to (optional)">
            <View style={{ gap: spacing.sm }}>
              {technicians.items.map((tech) => (
                <SelectRow
                  key={tech.id}
                  primary={tech.name}
                  selected={technicianId === tech.id}
                  onPress={() => setTechnicianId((current) => (current === tech.id ? null : tech.id))}
                />
              ))}
            </View>
          </Section>
        ) : null}

        {error ? (
          <Text selectable style={{ color: brand.danger }}>
            {error}
          </Text>
        ) : null}

        <Button
          label="Create job"
          busy={createJob.isPending}
          disabled={!canSubmit || createJob.isPending}
          onPress={submit}
        />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

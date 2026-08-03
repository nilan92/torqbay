import { ActivityIndicator, FlatList, RefreshControl, Text, View } from "react-native";

import { useJobs, type Job } from "@/jobs/use-jobs";
import { colors, useBrandColors } from "@/theme/colors";
import { continuous, radius, spacing } from "@/theme/layout";
import { type } from "@/theme/type";
import { StatusTag } from "@/ui/status-tag";

function JobCard({ job }: { job: Job }) {
  return (
    <View
      style={{
        backgroundColor: colors.groupedBackground,
        borderRadius: radius.md,
        padding: spacing.lg,
        gap: spacing.sm,
        ...continuous,
      }}
    >
      <Text selectable style={{ ...type.heading, color: colors.label }}>
        {job.title}
      </Text>
      {job.description ? (
        <Text
          numberOfLines={2}
          style={{ ...type.caption, color: colors.secondaryLabel }}
        >
          {job.description}
        </Text>
      ) : null}
      <StatusTag status={job.status} />
    </View>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <View style={{ padding: spacing.xxl, alignItems: "center", gap: spacing.md }}>
      {children}
    </View>
  );
}

export default function Jobs() {
  const { data, isLoading, isRefetching, error, refetch } = useJobs();
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
          {error instanceof Error ? error.message : "Couldn't load jobs."}
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
      keyExtractor={(job) => job.id}
      renderItem={({ item }) => <JobCard job={item} />}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
      ListEmptyComponent={
        <Centered>
          <Text style={{ ...type.heading, color: colors.label }}>No jobs yet</Text>
          <Text style={{ ...type.caption, color: colors.secondaryLabel, textAlign: "center" }}>
            Jobs you create will show up here.
          </Text>
        </Centered>
      }
    />
  );
}

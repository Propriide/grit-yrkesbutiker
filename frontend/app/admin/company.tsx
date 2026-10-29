import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, User } from "@/src/api";
import { EmptyState, ScreenHeader } from "@/src/components/ui";
import { UserRow } from "@/src/components/user-row";
import { makeStyles, spacing, useTheme } from "@/src/theme";

export default function AdminCompany() {
  const { name = "" } = useLocalSearchParams<{ name: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const users = useQuery({ queryKey: ["admin-company-users", name], queryFn: () => api<User[]>(`/admin/company-users?name=${encodeURIComponent(name)}`) });

  return (
    <View style={styles.root}>
      <ScreenHeader title={name} subtitle={users.data ? `${users.data.length} ${users.data.length === 1 ? "person" : "personer"} på företaget` : undefined} />
      <FlatList
        testID="company-users-list"
        data={users.data ?? []}
        keyExtractor={(u) => u.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={users.isRefetching} onRefresh={() => users.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={users.isLoading ? <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} /> : <EmptyState icon="domain-off" title="Inga konton" />}
        renderItem={({ item }) => <UserRow user={item} onPress={() => router.push(`/admin/user/${item.id}`)} />}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
}));

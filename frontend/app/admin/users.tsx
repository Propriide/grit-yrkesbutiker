import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { FlatList, Pressable, RefreshControl, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, User } from "@/src/api";
import { EmptyState, Icon, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function AdminUsers() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(search), 300);
    return () => clearTimeout(t);
  }, [search]);
  const users = useQuery({ queryKey: ["admin-users", q], queryFn: () => api<User[]>(`/admin/users?q=${encodeURIComponent(q)}`) });

  return (
    <View style={styles.root}>
      <ScreenHeader title="Kunder" subtitle={users.data ? `${users.data.length} konton` : undefined} />
      <View style={styles.searchWrap}>
        <View style={styles.search}>
          <Icon name="magnify" size={22} color={colors.muted} />
          <TextInput
            testID="users-search-input"
            value={search}
            onChangeText={setSearch}
            placeholder="Sök e-post eller företag"
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
            autoCapitalize="none"
          />
        </View>
      </View>
      <FlatList
        testID="users-list"
        data={users.data ?? []}
        keyExtractor={(u) => u.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={users.isRefetching} onRefresh={() => users.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={users.isLoading ? null : <EmptyState icon="account-off" title="Inga konton" />}
        renderItem={({ item }) => (
          <Pressable testID={`user-row-${item.email}`} onPress={() => router.push(`/admin/user/${item.id}`)} style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceTertiary }]}>
            <View style={{ flex: 1 }}>
              <View style={styles.nameRow}>
                <Text style={styles.company} numberOfLines={1}>
                  {item.company}
                </Text>
                {item.role === "admin" && <Text style={styles.tagAdmin}>ADMIN</Text>}
                {item.disabled && <Text style={styles.tagDisabled}>SPÄRRAD</Text>}
              </View>
              <Text style={styles.email} numberOfLines={1}>
                {item.email}
              </Text>
              <Text style={styles.meta}>
                {item.city_name || "Ingen ort"}
                {item.org_number ? `  ·  ${item.org_number}` : ""}
              </Text>
            </View>
            <Icon name="chevron-right" size={22} color={colors.muted} />
          </Pressable>
        )}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  searchWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  search: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: c.surfaceTertiary, borderRadius: radius.md, paddingHorizontal: spacing.md, height: 48, borderWidth: 1, borderColor: c.border },
  searchInput: { flex: 1, color: c.onSurface, fontFamily: fonts.body, fontSize: 15, height: 48, ...({ outlineWidth: 0 } as object) },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg },
  nameRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  company: { color: c.onSurface, fontFamily: fonts.display, fontSize: 20, textTransform: "uppercase", flexShrink: 1 },
  tagAdmin: { color: c.onBrandSecondary, backgroundColor: c.brandSecondary, fontFamily: fonts.bodyBold, fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm, overflow: "hidden" },
  tagDisabled: { color: c.onError, backgroundColor: c.error, fontFamily: fonts.bodyBold, fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm, overflow: "hidden" },
  email: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 13 },
  meta: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
}));

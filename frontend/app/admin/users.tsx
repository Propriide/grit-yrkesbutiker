import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Company, User } from "@/src/api";
import { EmptyState, Icon, ScreenHeader } from "@/src/components/ui";
import { UserRow } from "@/src/components/user-row";
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
  const [view, setView] = useState<"users" | "companies">("users");
  const users = useQuery({ queryKey: ["admin-users", q], queryFn: () => api<User[]>(`/admin/users?q=${encodeURIComponent(q)}`), enabled: view === "users" });
  const companies = useQuery({ queryKey: ["admin-companies"], queryFn: () => api<Company[]>("/admin/companies"), enabled: view === "companies" });
  const key = q.trim().toLowerCase();
  const companyList = (companies.data ?? []).filter((c) => !key || c.key.includes(key));

  return (
    <View style={styles.root}>
      <ScreenHeader
        title="Kunder"
        subtitle={view === "users" ? (users.data ? `${users.data.length} konton` : undefined) : companies.data ? `${companies.data.length} företag` : undefined}
        right={
          <Pressable testID="create-user-button" onPress={() => router.push("/admin/user/new")} style={styles.addBtn}>
            <Icon name="account-plus" size={22} color={colors.onBrandPrimary} />
          </Pressable>
        }
      />
      <View style={styles.searchWrap}>
        <View style={styles.segment}>
          {(
            [
              ["users", "Konton"],
              ["companies", "Företag"],
            ] as const
          ).map(([v, label]) => (
            <Pressable key={v} testID={`users-view-${v}`} onPress={() => setView(v)} style={[styles.segBtn, view === v && styles.segBtnActive]}>
              <Text style={[styles.segText, view === v && styles.segTextActive]}>{label}</Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.search}>
          <Icon name="magnify" size={22} color={colors.muted} />
          <TextInput
            testID="users-search-input"
            value={search}
            onChangeText={setSearch}
            placeholder={view === "users" ? "Sök e-post eller företag" : "Sök företag"}
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
            autoCapitalize="none"
          />
        </View>
      </View>
      {view === "companies" ? (
        <FlatList
          testID="companies-list"
          data={companyList}
          keyExtractor={(c) => c.key}
          contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={companies.isRefetching} onRefresh={() => companies.refetch()} tintColor={colors.brandPrimary} />}
          ListEmptyComponent={companies.isLoading ? <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} /> : <EmptyState icon="domain-off" title="Inga företag" />}
          renderItem={({ item }) => (
            <Pressable
              testID={`company-row-${item.key.replace(/\s+/g, "-")}`}
              onPress={() => router.push(`/admin/company?name=${encodeURIComponent(item.name)}`)}
              style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceTertiary }]}
            >
              <View style={styles.companyIcon}>
                <Icon name="domain" size={22} color={colors.brandSecondary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.company} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={styles.meta}>
                  {item.count} {item.count === 1 ? "person" : "personer"}
                  {item.spellings.length > 1 ? `  ·  ${item.spellings.length} stavningar` : ""}
                </Text>
              </View>
              <Icon name="chevron-right" size={22} color={colors.muted} />
            </Pressable>
          )}
        />
      ) : (
        <FlatList
          testID="users-list"
          data={users.data ?? []}
          keyExtractor={(u) => u.id}
          contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={users.isRefetching} onRefresh={() => users.refetch()} tintColor={colors.brandPrimary} />}
          ListEmptyComponent={users.isLoading ? <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} /> : <EmptyState icon="account-off" title="Inga konton" />}
          renderItem={({ item }) => <UserRow user={item} onPress={() => router.push(`/admin/user/${item.id}`)} />}
        />
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  addBtn: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
  searchWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, gap: spacing.md },
  segment: { flexDirection: "row", backgroundColor: c.surfaceTertiary, borderRadius: radius.md, padding: 4, gap: 4 },
  segBtn: { flex: 1, height: 44, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  segBtnActive: { backgroundColor: c.brandPrimary },
  segText: { color: c.onSurfaceSecondary, fontFamily: fonts.display, fontSize: 17, textTransform: "uppercase", letterSpacing: 1 },
  segTextActive: { color: c.onBrandPrimary },
  search: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: c.surfaceTertiary, borderRadius: radius.md, paddingHorizontal: spacing.md, height: 48, borderWidth: 1, borderColor: c.border },
  searchInput: { flex: 1, color: c.onSurface, fontFamily: fonts.body, fontSize: 15, height: 48, ...({ outlineWidth: 0 } as object) },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg },
  companyIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  company: { color: c.onSurface, fontFamily: fonts.display, fontSize: 20, textTransform: "uppercase", flexShrink: 1 },
  meta: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
}));


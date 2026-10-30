import { useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, AppNotification } from "@/src/api";
import { formatDate } from "@/src/components/order-card";
import { useNotifications } from "@/src/components/notification-bell";
import { EmptyState, Icon, IconName, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const ICONS: Record<AppNotification["kind"], IconName> = { new: "package-variant", confirmed: "check-decagram", declined: "close-octagon", broadcast: "bullhorn", ready: "package-variant-closed-check" };

export default function Notifications() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();
  const q = useNotifications();
  const [expanded, setExpanded] = useState<string | null>(null);

  const open = async (n: AppNotification) => {
    if (!n.read) {
      await api(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
      qc.invalidateQueries({ queryKey: ["notifications"] });
    }
    if (n.kind === "broadcast" || !n.order_id) {
      setExpanded((e) => (e === n.id ? null : n.id));
      return;
    }
    router.push(`/order/${n.order_id}`);
  };

  const readAll = async () => {
    await api("/notifications/read-all", { method: "POST" }).catch(() => {});
    qc.invalidateQueries({ queryKey: ["notifications"] });
  };

  return (
    <View style={styles.root}>
      <ScreenHeader
        title="Notiser"
        subtitle={q.data?.unread ? `${q.data.unread} olästa` : undefined}
        right={
          q.data?.unread ? (
            <Pressable testID="notifications-read-all" onPress={readAll} hitSlop={8} style={styles.readAll}>
              <Icon name="check-all" size={22} color={colors.brandPrimary} />
            </Pressable>
          ) : undefined
        }
      />
      <FlatList
        testID="notifications-list"
        data={q.data?.items ?? []}
        keyExtractor={(n) => n.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={q.isLoading ? null : <EmptyState icon="bell-sleep-outline" title="Inga notiser" text="Här ser du när en order bekräftas eller nekas." />}
        renderItem={({ item }) => (
          <Pressable testID={`notification-${item.id}`} onPress={() => open(item)} style={({ pressed }) => [styles.row, !item.read && styles.unread, pressed && { opacity: 0.8 }]}>
            <View style={[styles.icon, item.kind === "declined" && { backgroundColor: colors.error }, item.kind === "confirmed" && { backgroundColor: colors.success }, item.kind === "ready" && { backgroundColor: colors.success }, item.kind === "broadcast" && { backgroundColor: colors.brandPrimary }]}>
              <Icon name={ICONS[item.kind] ?? "bell"} size={22} color={item.kind === "new" ? colors.brandSecondary : item.kind === "broadcast" ? colors.onBrandPrimary : colors.onSuccess} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{item.title}</Text>
              {!!item.body && (
                <Text style={styles.body} numberOfLines={expanded === item.id ? undefined : 2}>
                  {item.body}
                </Text>
              )}
              <Text style={styles.date}>{formatDate(item.created_at)}</Text>
            </View>
            {!item.read && <View style={styles.dot} />}
          </Pressable>
        )}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  readAll: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg },
  unread: { borderLeftWidth: 4, borderLeftColor: c.brandPrimary },
  icon: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  title: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  body: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 13, marginTop: 2 },
  date: { color: c.muted, fontFamily: fonts.body, fontSize: 11, marginTop: 4 },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: c.brandPrimary },
}));

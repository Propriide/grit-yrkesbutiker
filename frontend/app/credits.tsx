import { FlatList, RefreshControl, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { txLabel, useCredits } from "@/src/components/credits-badge";
import { formatDate } from "@/src/components/order-card";
import { EmptyState, ScreenHeader } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function CreditsScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const q = useCredits();
  const d = q.data;

  return (
    <View style={styles.root}>
      <ScreenHeader title="Mina credits" />
      <FlatList
        testID="credits-history"
        data={d?.enabled ? d.history : []}
        keyExtractor={(t) => t.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        ListHeaderComponent={
          d?.enabled ? (
            <View style={styles.hero}>
              <Text style={styles.heroNum} testID="credits-screen-balance">
                {d.balance}
              </Text>
              <Text style={styles.heroLabel}>credits</Text>
              <Text style={styles.heroHelp}>Du tjänar credits när dina ordrar bekräftas av butiken.</Text>
            </View>
          ) : null
        }
        ListEmptyComponent={
          q.isLoading ? null : d?.enabled ? (
            <EmptyState icon="star-four-points-outline" title="Inga händelser än" text="Här syns intjänade credits och justeringar." />
          ) : (
            <EmptyState icon="star-off-outline" title="Credits är inte aktiverat" />
          )
        }
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.label}>{txLabel(item)}</Text>
              <Text style={styles.date}>{formatDate(item.created_at)}</Text>
            </View>
            <Text style={[styles.amount, { color: item.amount > 0 ? colors.success : colors.error }]}>
              {item.amount > 0 ? "+" : ""}
              {item.amount}
            </Text>
          </View>
        )}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  hero: { alignItems: "center", padding: spacing.xl, marginBottom: spacing.md, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border },
  heroNum: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 64, lineHeight: 68 },
  heroLabel: { color: c.brandSecondary, fontFamily: fonts.display, fontSize: 18, textTransform: "uppercase", letterSpacing: 1.5 },
  heroHelp: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginTop: spacing.md, textAlign: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg },
  label: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  date: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
  amount: { fontFamily: fonts.displayHeavy, fontSize: 24 },
}));

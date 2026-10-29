import { router } from "expo-router";
import { Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { Button, Icon, IconName } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function Profile() {
  const styles = useStyles();
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const { user, logout } = useAuth();
  if (!user) return null;
  const isAdmin = user.role === "admin";

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.mark} />
        <Text style={styles.title}>Profil</Text>
        {isAdmin && (
          <View style={styles.adminBadge} testID="admin-badge">
            <Text style={styles.adminBadgeText}>ADMIN</Text>
          </View>
        )}
      </View>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: bottomChrome + spacing.xl }}>
        <View style={styles.card}>
          <Text style={styles.company} testID="profile-company">
            {user.company}
          </Text>
          <Text style={styles.email} testID="profile-email">
            {user.email}
          </Text>
          <View style={styles.infoGrid}>
            <Info label="Telefon" value={user.phone} />
            <Info label="Org.nr" value={user.org_number} />
            <Info label="Ort" value={user.city_name} />
          </View>
        </View>

        <View style={[styles.list, { marginTop: spacing.lg }]}>
          <Row icon="package-variant-closed" title="Mina ordrar" sub="Beställningar och svar från butiken" testID="my-orders-row" onPress={() => router.push("/orders")} last />
        </View>

        {isAdmin && (
          <>
            <Text style={styles.section}>Adminpanel</Text>
            <View style={styles.list}>
              <Row icon="email-fast" title="Ordermottagare & sortiment" sub="E-post för beställningar, uppdatera katalog" testID="admin-settings-row" onPress={() => router.push("/admin/settings")} />
              <Row icon="storefront" title="Startsida (standard)" sub="Visas för konton utan egen butikstext" testID="admin-default-store-row" onPress={() => router.push("/admin/store/default")} />
              <Row icon="map-marker-radius" title="Orter & butiker" sub="Orter och startsida per butik" testID="admin-cities-row" onPress={() => router.push("/admin/cities")} />
              <Row icon="account-group" title="Hantera kunder" sub="Kundkonton, ort, spärra & ta bort" testID="admin-users-row" onPress={() => router.push("/admin/users")} />
              <Row icon="clipboard-list" title="Alla ordrar" sub="Samtliga beställningar" testID="admin-orders-row" onPress={() => router.push("/admin/orders")} last />
            </View>
          </>
        )}

        <Button
          title="Logga ut"
          variant="danger"
          icon="logout"
          testID="logout-button"
          style={{ marginTop: spacing.xl }}
          onPress={async () => {
            await logout();
            router.replace("/login");
          }}
        />
      </ScrollView>
    </View>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  const styles = useStyles();
  return (
    <View style={styles.info}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value || "-"}</Text>
    </View>
  );
}

function Row({ icon, title, sub, onPress, testID, last }: { icon: IconName; title: string; sub: string; onPress: () => void; testID: string; last?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [styles.row, last && { borderBottomWidth: 0 }, pressed && { backgroundColor: colors.surfaceTertiary }]}>
      <View style={styles.rowIcon}>
        <Icon name={icon} size={22} color={colors.brandSecondary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle}>{title}</Text>
        <Text style={styles.rowSub}>{sub}</Text>
      </View>
      <Icon name="chevron-right" size={22} color={colors.muted} />
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  mark: { width: 8, height: 26, backgroundColor: c.brandPrimary },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 32, textTransform: "uppercase", flex: 1 },
  adminBadge: { backgroundColor: c.brandSecondary, paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radius.sm },
  adminBadgeText: { color: c.onBrandSecondary, fontFamily: fonts.display, fontSize: 14, letterSpacing: 1 },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg, borderLeftWidth: 4, borderLeftColor: c.brandPrimary },
  company: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 28, textTransform: "uppercase" },
  email: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 14 },
  infoGrid: { flexDirection: "row", marginTop: spacing.lg, gap: spacing.md },
  info: { flex: 1 },
  infoLabel: { color: c.muted, fontFamily: fonts.bodyBold, fontSize: 11, textTransform: "uppercase" },
  infoValue: { color: c.onSurface, fontFamily: fonts.body, fontSize: 13, marginTop: 2 },
  section: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.sm },
  list: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, minHeight: 64, borderBottomWidth: 1, borderBottomColor: c.divider },
  rowIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  rowTitle: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  rowSub: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
}));

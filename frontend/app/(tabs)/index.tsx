import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { router } from "expo-router";
import { Linking, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, CategoryGroup, StoreInfo } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, Icon, IconName } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Home = StoreInfo & { city_name: string | null };

export default function HomeScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const { user } = useAuth();
  const home = useQuery({ queryKey: ["home"], queryFn: () => api<Home>("/home") });
  const cats = useQuery({ queryKey: ["categories"], queryFn: () => api<CategoryGroup[]>("/categories") });
  const h = home.data;

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={{ paddingTop: insets.top + spacing.lg, paddingHorizontal: spacing.lg, paddingBottom: bottomChrome + spacing.xl }}
      refreshControl={<RefreshControl refreshing={home.isRefetching} onRefresh={() => home.refetch()} tintColor={colors.brandPrimary} />}
    >
      <Animated.View entering={FadeInDown.duration(350)} style={styles.logoCard}>
        <Image testID="home-logo" source={require("../../assets/images/yp-logo.png")} style={styles.logo} contentFit="contain" />
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(80).duration(350)}>
        {h?.city_name ? (
          <Text style={styles.store} testID="home-store-name">
            {h.city_name}
          </Text>
        ) : null}
        <Text style={styles.title} testID="home-title">
          {h?.title ?? " "}
        </Text>
        <Text style={styles.greeting}>Inloggad som {user?.company}</Text>
        {!!h?.text && (
          <Text style={styles.text} testID="home-text">
            {h.text}
          </Text>
        )}
      </Animated.View>

      {h && (h.address || h.phone || h.email || h.hours) ? (
        <Animated.View entering={FadeInDown.delay(160).duration(350)} style={styles.card} testID="home-contact-card">
          {!!h.address && <InfoRow icon="map-marker" text={h.address} testID="home-address" />}
          {!!h.phone && <InfoRow icon="phone" text={h.phone} testID="home-phone" onPress={() => Linking.openURL(`tel:${h.phone.replace(/\s/g, "")}`)} />}
          {!!h.email && <InfoRow icon="email" text={h.email} testID="home-email" onPress={() => Linking.openURL(`mailto:${h.email}`)} />}
          {!!h.hours && <InfoRow icon="clock-outline" text={h.hours} testID="home-hours" last />}
        </Animated.View>
      ) : null}

      <Button title="Till sortimentet" icon="arrow-right" testID="home-shop-button" onPress={() => router.push("/(tabs)/shop")} style={{ marginTop: spacing.xl }} />

      {(cats.data?.length ?? 0) > 0 && (
        <>
          <Text style={styles.section}>Handla efter plagg</Text>
          <View style={styles.grid}>
            {cats.data!.map((g) => (
              <Pressable
                key={g.slug}
                testID={`home-group-${g.slug}`}
                onPress={() => router.push({ pathname: "/(tabs)/shop", params: { group: g.slug, t: String(Date.now()) } })}
                style={({ pressed }) => [styles.tile, pressed && { transform: [{ scale: 0.97 }], borderColor: colors.brandPrimary }]}
              >
                <Text style={styles.tileName} numberOfLines={1}>
                  {g.name}
                </Text>
                <Text style={styles.tileCount}>{g.count} artiklar</Text>
              </Pressable>
            ))}
          </View>
        </>
      )}
    </ScrollView>
  );
}

function InfoRow({ icon, text, onPress, testID, last }: { icon: IconName; text: string; onPress?: () => void; testID: string; last?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} disabled={!onPress} onPress={onPress} style={[styles.infoRow, last && { borderBottomWidth: 0 }]}>
      <Icon name={icon} size={20} color={colors.brandPrimary} />
      <Text style={[styles.infoText, onPress && { color: colors.brandSecondary }]}>{text}</Text>
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  logoCard: { backgroundColor: "#FFFFFF", borderRadius: radius.lg, padding: spacing.lg, alignItems: "center", marginBottom: spacing.xl },
  logo: { width: "100%", height: 150 },
  store: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase" },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 34, lineHeight: 38, textTransform: "uppercase", marginTop: spacing.xs },
  greeting: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginTop: spacing.xs },
  text: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 15, lineHeight: 23, marginTop: spacing.lg },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, paddingHorizontal: spacing.lg, marginTop: spacing.xl },
  infoRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, paddingVertical: spacing.md, minHeight: 48, borderBottomWidth: 1, borderBottomColor: c.divider },
  infoText: { color: c.onSurface, fontFamily: fonts.body, fontSize: 15, flex: 1, lineHeight: 21 },
  section: { color: c.brandPrimary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginTop: spacing.xxl, marginBottom: spacing.md },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  tile: { width: "47%", flexGrow: 1, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg, borderLeftWidth: 4, borderLeftColor: c.brandPrimary },
  tileName: { color: c.onSurface, fontFamily: fonts.display, fontSize: 20, textTransform: "uppercase" },
  tileCount: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
}));

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Image } from "expo-image";
import { router } from "expo-router";
import { Linking, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Order, StoreInfo } from "@/src/api";
import { useAuth } from "@/src/auth";
import { OrderCard } from "@/src/components/order-card";
import { useFavorites } from "@/src/favorites";
import { Button, Icon, IconName } from "@/src/components/ui";
import { CreditsBadge } from "@/src/components/credits-badge";
import { NotificationBell } from "@/src/components/notification-bell";
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
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/orders") });
  const favs = useFavorites();
  const [showFavs, setShowFavs] = useState(true);
  const [showOrders, setShowOrders] = useState(true);
  const h = home.data;

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={{ paddingTop: insets.top + spacing.lg, paddingHorizontal: spacing.lg, paddingBottom: bottomChrome + spacing.xl }}
      refreshControl={<RefreshControl refreshing={home.isRefetching} onRefresh={() => home.refetch()} tintColor={colors.brandPrimary} />}
    >
      <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: spacing.sm, marginBottom: spacing.md }}>
        <CreditsBadge />
          <NotificationBell />
      </View>
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

      <Button title="Till sortimentet" icon="arrow-right" testID="home-shop-button" onPress={() => router.push({ pathname: "/(tabs)/shop", params: { pick: "1", t: String(Date.now()) } })} style={{ marginTop: spacing.xl }} />

      {favs.list.length > 0 && (
        <View testID="home-favorites">
          <SectionTitle title="Mina favoriter" open={showFavs} onToggle={() => setShowFavs((v) => !v)} action="Visa alla" onAction={() => router.push("/favorites")} testID="home-favorites" />
          {showFavs && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.md }} style={{ marginHorizontal: -spacing.lg }}>
            <View style={{ width: spacing.lg - spacing.md }} />
            {favs.list.slice(0, 12).map((f) => (
              <Pressable
                key={f.id}
                testID={`home-favorite-${f.part_no}-${f.color_code ?? "none"}`}
                onPress={() => router.push(f.color_code ? `/product/${f.part_no}?color=${f.color_code}` : `/product/${f.part_no}`)}
                style={({ pressed }) => [styles.favCard, pressed && { transform: [{ scale: 0.97 }] }]}
              >
                <View style={styles.favImg}>
                  <Image source={{ uri: f.image_url ? `${f.image_url}?w=300` : undefined }} style={{ width: "100%", height: "100%" }} contentFit="contain" />
                </View>
                <Text style={styles.favName} numberOfLines={2}>
                  {f.name}
                </Text>
                {!!f.color_name && (
                  <Text style={styles.favColor} numberOfLines={1}>
                    {f.color_name}
                  </Text>
                )}
              </Pressable>
            ))}
            <View style={{ width: spacing.lg - spacing.md }} />
          </ScrollView>
          )}
        </View>
      )}

      {!!orders.data?.length && (
        <View testID="home-recent-orders">
          <SectionTitle title="Senaste ordrar" open={showOrders} onToggle={() => setShowOrders((v) => !v)} action="Alla ordrar" onAction={() => router.push("/orders")} testID="home-orders" />
          {showOrders && (
            <View style={{ gap: spacing.sm }}>
              {orders.data.slice(0, 3).map((o) => (
                <OrderCard key={o.id} order={o} />
              ))}
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
}

function SectionTitle({ title, open, onToggle, action, onAction, testID }: { title: string; open: boolean; onToggle: () => void; action: string; onAction: () => void; testID: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.sectionRow}>
      <Pressable testID={`${testID}-toggle`} onPress={onToggle} hitSlop={8} style={styles.sectionToggle}>
        <Text style={styles.section}>{title}</Text>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={24} color={colors.brandSecondary} />
      </Pressable>
      <Pressable testID={`${testID}-all`} onPress={onAction} hitSlop={8} style={{ minHeight: 44, justifyContent: "center" }}>
        <Text style={styles.sectionAction}>{action} ›</Text>
      </Pressable>
    </View>
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
  sectionRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.xl, marginBottom: spacing.xs },
  sectionToggle: { flexDirection: "row", alignItems: "center", gap: spacing.xs, minHeight: 44, flex: 1 },
  section: { color: c.brandSecondary, fontFamily: fonts.display, fontSize: 18, letterSpacing: 1.5, textTransform: "uppercase" },
  sectionAction: { color: c.onSurfaceSecondary, fontFamily: fonts.bodyBold, fontSize: 13 },
  favCard: { width: 140, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, overflow: "hidden", paddingBottom: spacing.sm },
  favImg: { height: 120, backgroundColor: "#F2F2F2", padding: 6 },
  favName: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 12, lineHeight: 16, paddingHorizontal: spacing.sm, marginTop: spacing.sm, minHeight: 32 },
  favColor: { color: c.muted, fontFamily: fonts.body, fontSize: 11, paddingHorizontal: spacing.sm },
}));

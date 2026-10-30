import { Image } from "expo-image";
import { router } from "expo-router";
import { FlatList, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useCart } from "@/src/cart";
import { Button, EmptyState, Icon, Stepper } from "@/src/components/ui";
import { CreditsBadge } from "@/src/components/credits-badge";
import { NotificationBell } from "@/src/components/notification-bell";
import { usesNativeTabs } from "@/src/navigation";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function Cart() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const cart = useCart();

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.mark} />
        <Text style={styles.title}>Varukorg</Text>
        <CreditsBadge />
          <NotificationBell />
        <Text style={styles.count} testID="cart-count">
          {cart.count ? `${cart.count} st` : ""}
        </Text>
      </View>
      {cart.items.length === 0 ? (
        <View style={{ flex: 1, justifyContent: "center", paddingBottom: bottomChrome }}>
          <EmptyState
            icon="cart-outline"
            title="Varukorgen är tom"
            text="Bläddra i sortimentet och lägg till plagg."
            action={<Button title="Till sortimentet" testID="cart-browse-button" onPress={() => router.push("/(tabs)/shop")} />}
          />
        </View>
      ) : (
        <>
          <FlatList
            testID="cart-list"
            data={cart.items}
            keyExtractor={(i) => i.key}
            contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
            renderItem={({ item }) => (
              <View style={styles.row} testID={`cart-item-${item.key}`}>
                <View style={styles.thumbWrap}>
                  <Image source={{ uri: item.image_url ? `${item.image_url}?w=200` : undefined }} style={styles.thumb} contentFit="contain" />
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={styles.partNo}>
                    {item.part_no}
                    {item.color_code ? `-${item.color_code}` : ""}
                  </Text>
                  <Text style={styles.name} numberOfLines={2}>
                    {item.name}
                  </Text>
                  <Text style={styles.meta}>
                    Storlek <Text style={styles.metaStrong}>{item.size}</Text>
                    {item.color_name ? `  ·  ${item.color_name}` : ""}
                  </Text>
                  <View style={styles.rowFoot}>
                    <Stepper compact value={item.quantity} onChange={(v) => cart.setQuantity(item.key, v)} testIDPrefix={`cart-qty-${item.key}`} />
                    <Pressable testID={`cart-remove-${item.key}`} onPress={() => cart.remove(item.key)} hitSlop={8} style={styles.remove}>
                      <Icon name="trash-can-outline" size={22} color={colors.error} />
                    </Pressable>
                  </View>
                </View>
              </View>
            )}
          />
          <View style={[styles.footer, { paddingBottom: bottomChrome + spacing.md }]}>
            <Button title="Till kassan" icon="arrow-right" testID="cart-checkout-button" onPress={() => router.push("/checkout")} />
          </View>
        </>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  mark: { width: 8, height: 26, backgroundColor: c.brandPrimary },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 32, textTransform: "uppercase", flex: 1 },
  count: { color: c.muted, fontFamily: fonts.body, fontSize: 13 },
  row: { flexDirection: "row", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, padding: spacing.md, borderWidth: 1, borderColor: c.border },
  thumbWrap: { width: 84, height: 84, backgroundColor: "#F2F2F2", borderRadius: radius.sm, padding: 4 },
  thumb: { width: "100%", height: "100%" },
  partNo: { color: c.muted, fontFamily: fonts.body, fontSize: 11 },
  name: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  meta: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 12 },
  metaStrong: { color: c.brandSecondary, fontFamily: fonts.bodyBold },
  rowFoot: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  remove: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  footer: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: c.divider, backgroundColor: c.surface },
}));

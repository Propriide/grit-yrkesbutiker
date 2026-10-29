import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import Animated, { FadeIn } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Product } from "@/src/api";
import { useCart } from "@/src/cart";
import { Button, EmptyState, formatPrice, haptic, Icon, Stepper } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function ProductDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const cart = useCart();
  const toast = useToast();
  const q = useQuery({ queryKey: ["product", id], queryFn: () => api<Product>(`/products/${id}`) });
  const p = q.data;
  const [color, setColor] = useState<string | null>(null);
  const [size, setSize] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [sizeError, setSizeError] = useState(false);

  useEffect(() => {
    if (p) {
      setColor(p.colors?.[0]?.code ?? null);
      if (p.sizes?.length === 1) setSize(p.sizes[0]);
    }
  }, [p]);

  const selColor = p?.colors?.find((c) => c.code === color);
  const image = selColor?.image_url || p?.image_url;

  const add = () => {
    if (!p) return;
    if (!size) {
      setSizeError(true);
      haptic("error");
      return;
    }
    cart.add({ part_no: p.part_no, name: p.name, image_url: image, color_code: selColor?.code, color_name: selColor?.name, size, quantity: qty });
    haptic("success");
    toast(`${qty} st ${p.name} (${size}) i varukorgen`, "success");
    setQty(1);
  };

  return (
    <View style={styles.root}>
      <View style={[styles.topBar, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable testID="product-back-button" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} style={styles.roundBtn}>
          <Icon name="arrow-left" size={24} color={colors.onSurface} />
        </Pressable>
        <Pressable testID="product-cart-button" onPress={() => router.push("/(tabs)/cart")} style={styles.roundBtn}>
          <Icon name="cart" size={22} color={colors.onSurface} />
          {cart.count > 0 && (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{cart.count}</Text>
            </View>
          )}
        </Pressable>
      </View>

      {q.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brandPrimary} size="large" />
        </View>
      ) : q.isError || !p ? (
        <View style={styles.center}>
          <EmptyState icon="alert-octagon" title="Kunde inte ladda produkten" action={<Button title="Försök igen" testID="product-retry-button" onPress={() => q.refetch()} />} />
        </View>
      ) : (
        <>
          <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
            <View style={[styles.hero, { paddingTop: spacing.lg }]}>
              <Animated.View key={image} entering={FadeIn.duration(250)} style={{ flex: 1 }}>
                <Image testID="product-image" source={{ uri: image ? `${image}?w=900` : undefined }} style={styles.heroImg} contentFit="contain" />
              </Animated.View>
            </View>
            <View style={styles.body}>
              <Text style={styles.partNo} testID="product-part-no">
                ART.NR {p.part_no}
                {selColor ? `-${selColor.code}` : ""}
              </Text>
              <Text style={styles.name} testID="product-name">
                {p.name}
              </Text>
              {p.price != null && (
                <Text style={styles.price}>
                  {formatPrice(p.price)} <Text style={styles.priceNote}>exkl. moms, cirkapris</Text>
                </Text>
              )}

              {p.colors?.length > 0 && (
                <>
                  <Text style={styles.section}>
                    Färg <Text style={styles.sectionValue}>{selColor?.name}</Text>
                  </Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.colorRow}>
                    {p.colors.map((c) => (
                      <Pressable
                        key={c.code}
                        testID={`color-option-${c.code}`}
                        onPress={() => {
                          haptic("selection");
                          setColor(c.code);
                        }}
                        style={[styles.colorTile, c.code === color && styles.colorTileActive]}
                      >
                        <Image source={{ uri: c.image_url ? `${c.image_url}?w=160` : undefined }} style={styles.colorImg} contentFit="contain" />
                      </Pressable>
                    ))}
                  </ScrollView>
                </>
              )}

              <Text style={styles.section}>Storlek</Text>
              <View style={styles.sizeGrid}>
                {p.sizes.map((s) => (
                  <Pressable
                    key={s}
                    testID={`size-option-${s}`}
                    onPress={() => {
                      haptic("selection");
                      setSize(s);
                      setSizeError(false);
                    }}
                    style={[styles.sizePill, s === size && styles.sizePillActive, sizeError && styles.sizePillError]}
                  >
                    <Text style={[styles.sizeText, s === size && styles.sizeTextActive]}>{s}</Text>
                  </Pressable>
                ))}
              </View>
              {sizeError && <Text style={styles.err} testID="size-error">Välj en storlek först</Text>}

              <Text style={styles.section}>Antal</Text>
              <Stepper value={qty} onChange={setQty} testIDPrefix="product-quantity" />

              {!!p.description && (
                <>
                  <Text style={styles.section}>Beskrivning</Text>
                  <Text style={styles.desc}>{p.description}</Text>
                </>
              )}
            </View>
          </ScrollView>
          <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
            <Button title="Lägg i varukorg" icon="cart-plus" testID="add-to-cart-button" onPress={add} />
          </View>
        </>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  topBar: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, backgroundColor: c.surface, borderBottomWidth: 1, borderBottomColor: c.divider },
  roundBtn: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.surfaceSecondary, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: c.border },
  badge: { position: "absolute", top: -4, right: -4, minWidth: 20, height: 20, borderRadius: 10, backgroundColor: c.brandSecondary, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  badgeText: { color: c.onBrandSecondary, fontFamily: fonts.bodyBold, fontSize: 11 },
  hero: { backgroundColor: "#F2F2F2", height: 380, paddingBottom: spacing.lg },
  heroImg: { width: "100%", height: "100%" },
  body: { padding: spacing.lg },
  partNo: { color: c.brandPrimary, fontFamily: fonts.bodyBold, fontSize: 12, letterSpacing: 1 },
  name: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 32, textTransform: "uppercase", lineHeight: 34, marginTop: spacing.xs },
  price: { color: c.brandSecondary, fontFamily: fonts.displayHeavy, fontSize: 26, marginTop: spacing.sm },
  priceNote: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  section: { color: c.onSurfaceSecondary, fontFamily: fonts.display, fontSize: 16, letterSpacing: 1.5, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.md },
  sectionValue: { color: c.muted, fontFamily: fonts.body, fontSize: 13, textTransform: "none", letterSpacing: 0 },
  colorRow: { gap: spacing.sm },
  colorTile: { width: 64, height: 64, borderRadius: radius.md, backgroundColor: "#F2F2F2", borderWidth: 2, borderColor: c.border, padding: 4 },
  colorTileActive: { borderColor: c.brandPrimary },
  colorImg: { width: "100%", height: "100%" },
  sizeGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  sizePill: { minWidth: 60, height: 48, borderRadius: radius.sm, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.md },
  sizePillActive: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary },
  sizePillError: { borderColor: c.error },
  sizeText: { color: c.onSurface, fontFamily: fonts.display, fontSize: 18 },
  sizeTextActive: { color: c.onBrandPrimary },
  err: { color: c.error, fontFamily: fonts.body, fontSize: 13, marginTop: spacing.sm },
  desc: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 14, lineHeight: 21 },
  footer: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.divider },
}));

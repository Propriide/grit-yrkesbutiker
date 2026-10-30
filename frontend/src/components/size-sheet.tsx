import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Product } from "@/src/api";
import { CartItem, useCart } from "@/src/cart";
import { haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

/** Change the size of a cart line; sizes come from the product page data. */
export function SizeSheet({ item, onClose }: { item: CartItem | null; onClose: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const cart = useCart();
  const q = useQuery({ queryKey: ["product", item?.part_no], queryFn: () => api<Product>(`/products/${item!.part_no}`), enabled: !!item });

  return (
    <Modal visible={!!item} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose} testID="size-sheet-scrim" />
      <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]} testID="size-sheet">
        <View style={styles.handle} />
        <Text style={styles.title}>Välj storlek</Text>
        <Text style={styles.sub} numberOfLines={1}>
          {item?.name}
          {item?.color_name ? ` · ${item.color_name}` : ""}
        </Text>
        {q.isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginVertical: spacing.xl }} />
        ) : !q.data?.sizes?.length ? (
          <Text style={styles.sub} testID="size-sheet-empty">
            Inga andra storlekar finns för det här plagget.
          </Text>
        ) : (
          <ScrollView style={{ maxHeight: 360 }} contentContainerStyle={styles.grid}>
            {(q.data?.sizes ?? []).map((s) => {
              const active = s === item?.size;
              return (
                <Pressable
                  key={s}
                  testID={`size-option-${s}`}
                  onPress={() => {
                    haptic("selection");
                    if (item) cart.changeSize(item.key, s);
                    onClose();
                  }}
                  style={[styles.size, active && styles.sizeActive]}
                >
                  <Text style={[styles.sizeText, active && { color: colors.onBrandPrimary }]}>{s}</Text>
                  {active && <Icon name="check" size={14} color={colors.onBrandPrimary} />}
                </Pressable>
              );
            })}
          </ScrollView>
        )}
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((c) => ({
  scrim: { flex: 1, backgroundColor: c.scrim },
  sheet: { backgroundColor: c.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.lg, borderTopWidth: 1, borderColor: c.border },
  handle: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: c.borderStrong, marginBottom: spacing.md },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 26, textTransform: "uppercase" },
  sub: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.lg },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  size: { minWidth: 64, height: 48, paddingHorizontal: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceTertiary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 4 },
  sizeActive: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary },
  sizeText: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
}));

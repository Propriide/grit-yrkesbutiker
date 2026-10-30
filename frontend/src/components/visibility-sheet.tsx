import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, City, Product } from "@/src/api";
import { Button, haptic } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

/** Admin: choose in which stores (cities) a product is hidden from customers. */
export function VisibilitySheet({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const qc = useQueryClient();
  const cities = useQuery({ queryKey: ["cities"], queryFn: () => api<City[]>("/cities") });
  const [hidden, setHidden] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  useEffect(() => setHidden(product?.hidden_city_ids ?? []), [product]);

  const save = async () => {
    if (!product) return;
    setSaving(true);
    try {
      await api(`/admin/products/${product.part_no}/visibility`, { method: "PUT", body: { hidden_city_ids: hidden } });
      haptic("success");
      toast(hidden.length ? `Dold i ${hidden.length} ${hidden.length === 1 ? "butik" : "butiker"}` : "Synlig i alla butiker", "success");
      qc.invalidateQueries({ queryKey: ["products"] });
      onClose();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={!!product} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose} testID="visibility-scrim" />
      <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]} testID="visibility-sheet">
        <View style={styles.handle} />
        <Text style={styles.title}>Dölj i butik</Text>
        <Text style={styles.sub} numberOfLines={2}>
          {product?.part_no} · {product?.name}
        </Text>
        <ScrollView style={{ maxHeight: 380 }}>
          {(cities.data ?? []).map((c) => {
            const isHidden = hidden.includes(c.id);
            return (
              <View key={c.id} style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.city}>{c.name}</Text>
                  <Text style={[styles.state, isHidden && { color: colors.error }]}>{isHidden ? "Dold för kunder" : "Synlig"}</Text>
                </View>
                <Switch
                  testID={`visibility-switch-${c.name}`}
                  value={isHidden}
                  onValueChange={(v) => setHidden((h) => (v ? [...h, c.id] : h.filter((x) => x !== c.id)))}
                  trackColor={{ true: colors.error, false: colors.surfaceTertiary }}
                  thumbColor={colors.onSurface}
                  {...({ activeThumbColor: colors.onSurface } as object)}
                />
              </View>
            );
          })}
        </ScrollView>
        <Button title="Spara" testID="visibility-save-button" onPress={save} loading={saving} style={{ marginTop: spacing.lg }} />
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((c) => ({
  scrim: { flex: 1, backgroundColor: c.scrim },
  sheet: { backgroundColor: c.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing.lg, borderTopWidth: 1, borderColor: c.border },
  handle: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: c.borderStrong, marginBottom: spacing.md },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 26, textTransform: "uppercase" },
  sub: { color: c.muted, fontFamily: fonts.body, fontSize: 13, marginBottom: spacing.md },
  row: { flexDirection: "row", alignItems: "center", minHeight: 56, borderBottomWidth: 1, borderBottomColor: c.divider },
  city: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 15 },
  state: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
}));

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, FilterDef } from "@/src/api";
import { Button, haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export type FilterState = Record<string, string[]>;

type Props = {
  visible: boolean;
  onClose: () => void;
  value: FilterState;
  onApply: (v: FilterState) => void;
  query: string; // q/group/category query string for facet + count
};

export function filterCount(f: FilterState) {
  return Object.values(f).reduce((s, v) => s + v.length, 0);
}

export function FilterSheet({ visible, onClose, value, onApply, query }: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState<FilterState>(value);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (visible) setDraft(value);
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  const defs = useQuery({ queryKey: ["filters", query], queryFn: () => api<FilterDef[]>(`/filters?${query}`), enabled: visible });
  const draftJson = JSON.stringify(draft);
  const preview = useQuery({
    queryKey: ["filter-preview", query, draftJson],
    queryFn: () => api<{ total: number }>(`/products?page_size=1&${query}&filters=${encodeURIComponent(draftJson)}`),
    enabled: visible,
  });

  const toggle = (code: string, v: string) => {
    haptic("selection");
    setDraft((d) => {
      const cur = d[code] ?? [];
      const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v];
      const out = { ...d, [code]: next };
      if (!next.length) delete out[code];
      return out;
    });
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} presentationStyle="fullScreen">
      <View style={[styles.root, { paddingTop: insets.top }]} testID="filter-sheet">
        <View style={styles.header}>
          <Text style={styles.title}>Filter</Text>
          <Pressable testID="filter-close-button" onPress={onClose} style={styles.close} hitSlop={8}>
            <Icon name="close" size={26} color={colors.onSurface} />
          </Pressable>
        </View>
        {defs.isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
        ) : (
          <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
            {(defs.data ?? []).map((f, idx) => {
              const sel = draft[f.code] ?? [];
              const isOpen = open === f.code;
              const divider = f.code === "Size"; // Blåkläder separates the first block from size and below
              return (
                <View key={f.code} style={[divider && idx > 0 && styles.groupDivider]}>
                  <Pressable testID={`filter-section-${f.code}`} onPress={() => setOpen(isOpen ? null : f.code)} style={styles.sectionRow}>
                    <Text style={styles.sectionName}>{f.name}</Text>
                    {sel.length > 0 && (
                      <View style={styles.badge}>
                        <Text style={styles.badgeText}>{sel.length}</Text>
                      </View>
                    )}
                    <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={24} color={colors.onSurfaceTertiary} />
                  </Pressable>
                  {isOpen && (
                    <View style={styles.values}>
                      {f.values.map((v) => {
                        const on = sel.includes(v.value);
                        return (
                          <Pressable key={v.value} testID={`filter-option-${f.code}-${v.value}`} onPress={() => toggle(f.code, v.value)} style={styles.valueRow}>
                            <View style={[styles.check, on && styles.checkOn]}>{on && <Icon name="check-bold" size={16} color={colors.onBrandPrimary} />}</View>
                            <Text style={styles.valueText}>{v.value}</Text>
                            <Text style={styles.valueCount}>{v.count}</Text>
                          </Pressable>
                        );
                      })}
                    </View>
                  )}
                </View>
              );
            })}
          </ScrollView>
        )}
        <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
          <Button title="Rensa" variant="secondary" testID="filter-clear-button" onPress={() => setDraft({})} style={{ flex: 1 }} />
          <Button
            title={preview.data ? `Visa ${preview.data.total}` : "Visa"}
            testID="filter-apply-button"
            onPress={() => {
              onApply(draft);
              onClose();
            }}
            style={{ flex: 2 }}
          />
        </View>
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: c.borderStrong },
  title: { flex: 1, color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 30, textTransform: "uppercase" },
  close: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  groupDivider: { borderTopWidth: 1, borderTopColor: c.borderStrong, marginTop: spacing.sm, paddingTop: spacing.sm },
  sectionRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minHeight: 52, paddingHorizontal: spacing.lg },
  sectionName: { flex: 1, color: c.onSurface, fontFamily: fonts.displaySemi, fontSize: 18, textTransform: "uppercase", letterSpacing: 0.5 },
  badge: { minWidth: 22, height: 22, borderRadius: 11, backgroundColor: c.brandSecondary, alignItems: "center", justifyContent: "center", paddingHorizontal: 6 },
  badgeText: { color: c.onBrandSecondary, fontFamily: fonts.bodyBold, fontSize: 12 },
  values: { backgroundColor: c.surfaceSecondary, paddingHorizontal: spacing.lg, paddingVertical: spacing.xs },
  valueRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 48 },
  check: { width: 24, height: 24, borderRadius: radius.sm, borderWidth: 2, borderColor: c.borderStrong, alignItems: "center", justifyContent: "center" },
  checkOn: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary },
  valueText: { flex: 1, color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 15 },
  valueCount: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  footer: { flexDirection: "row", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.md, borderTopWidth: 1, borderTopColor: c.divider },
}));

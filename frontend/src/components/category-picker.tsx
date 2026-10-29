import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native";
import Animated, { FadeIn } from "react-native-reanimated";

import { CategoryGroup } from "@/src/api";
import { haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Props = { groups: CategoryGroup[]; group: string; category: string; onSelect: (group: string, category: string) => void };

/** Vertical category dropdown: tap a main category to unfold its sub-categories; closes once a choice is made. */
export function CategoryPicker({ groups, group, category, onSelect }: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { height } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(group);
  useEffect(() => setExpanded(group), [group]);

  const g = groups.find((x) => x.slug === group);
  const sub = g?.children.find((c) => c.slug === category);
  const label = g ? (sub ? `${g.name} › ${sub.name}` : g.name) : "Alla kategorier";

  const choose = (gs: string, cs: string) => {
    haptic("selection");
    onSelect(gs, cs);
    setOpen(false);
  };

  return (
    <View style={styles.wrap}>
      <Pressable testID="category-dropdown-toggle" onPress={() => setOpen((o) => !o)} style={[styles.toggle, open && { borderColor: colors.brandPrimary }]}>
        <Icon name="shape-outline" size={20} color={colors.brandPrimary} />
        <View style={{ flex: 1 }}>
          <Text style={styles.toggleLabel}>Kategori</Text>
          <Text style={styles.toggleValue} numberOfLines={1} testID="category-dropdown-value">
            {label}
          </Text>
        </View>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={26} color={colors.onSurface} />
      </Pressable>
      {open && (
        <Animated.View entering={FadeIn.duration(150)} style={[styles.panel, { maxHeight: height * 0.55 }]} testID="category-dropdown">
          <ScrollView nestedScrollEnabled keyboardShouldPersistTaps="handled">
            <Row testID="group-chip-alla" title="Alla kategorier" active={!group} onPress={() => choose("", "")} />
            {groups.map((x) => {
              const isOpen = expanded === x.slug && x.children.length > 0;
              return (
                <View key={x.slug}>
                  <Row
                    testID={`group-chip-${x.slug}`}
                    title={x.name}
                    count={x.count}
                    active={group === x.slug && !category}
                    chevron={x.children.length > 0 ? (isOpen ? "chevron-up" : "chevron-down") : undefined}
                    onPress={() => {
                      if (!x.children.length) return choose(x.slug, "");
                      haptic("selection");
                      setExpanded(isOpen ? "" : x.slug);
                    }}
                  />
                  {isOpen && (
                    <View style={styles.subList}>
                      <Row sub testID="category-chip-alla" title={`Alla ${x.name.toLowerCase()}`} count={x.count} active={group === x.slug && !category} onPress={() => choose(x.slug, "")} />
                      {x.children.map((c) => (
                        <Row key={c.slug} sub testID={`category-chip-${c.slug}`} title={c.name} count={c.count} active={group === x.slug && category === c.slug} onPress={() => choose(x.slug, c.slug)} />
                      ))}
                    </View>
                  )}
                </View>
              );
            })}
          </ScrollView>
        </Animated.View>
      )}
    </View>
  );
}

function Row({ title, count, active, onPress, testID, sub, chevron }: { title: string; count?: number; active: boolean; onPress: () => void; testID: string; sub?: boolean; chevron?: "chevron-up" | "chevron-down" }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [styles.row, sub && styles.rowSub, active && styles.rowActive, pressed && { backgroundColor: colors.surfaceTertiary }]}>
      {active && <View style={styles.activeBar} />}
      <Text style={[sub ? styles.subText : styles.rowText, active && { color: colors.brandPrimary }]} numberOfLines={1}>
        {title}
      </Text>
      {count !== undefined && <Text style={styles.count}>{count}</Text>}
      {chevron ? <Icon name={chevron} size={22} color={colors.muted} /> : active ? <Icon name="check" size={20} color={colors.brandPrimary} /> : null}
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  wrap: { marginTop: spacing.md, marginBottom: spacing.md },
  toggle: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 56, paddingHorizontal: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary },
  toggleLabel: { color: c.muted, fontFamily: fonts.bodyBold, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8 },
  toggleValue: { color: c.onSurface, fontFamily: fonts.display, fontSize: 19, textTransform: "uppercase" },
  panel: { marginTop: spacing.xs, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary, overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minHeight: 50, paddingHorizontal: spacing.lg, borderBottomWidth: 1, borderBottomColor: c.divider },
  rowSub: { paddingLeft: spacing.xl + spacing.sm, minHeight: 46, backgroundColor: c.surface },
  rowActive: { backgroundColor: c.brandTertiary },
  activeBar: { position: "absolute", left: 0, top: 0, bottom: 0, width: 4, backgroundColor: c.brandPrimary },
  rowText: { flex: 1, color: c.onSurface, fontFamily: fonts.display, fontSize: 18, textTransform: "uppercase" },
  subText: { flex: 1, color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 14 },
  count: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
}));

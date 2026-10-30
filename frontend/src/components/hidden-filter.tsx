import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { City } from "@/src/api";
import { haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

/** Admin-only: show only products hidden somewhere, or hidden in one chosen store. */
export function HiddenFilter({ cities, value, onChange }: { cities: City[]; value: string; onChange: (v: string) => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const label = !value ? "Alla artiklar" : value === "any" ? "Alla dolda artiklar" : `Dolda i ${cities.find((c) => c.id === value)?.name ?? "vald ort"}`;
  const options: [string, string][] = [["", "Alla artiklar"], ["any", "Alla dolda artiklar"], ...cities.map((c): [string, string] => [c.id, `Dolda i ${c.name}`])];

  return (
    <View style={styles.wrap}>
      <Pressable testID="hidden-filter-toggle" onPress={() => setOpen((o) => !o)} style={[styles.toggle, (open || !!value) && { borderColor: colors.error }]}>
        <Icon name={value ? "eye-off" : "eye-outline"} size={20} color={value ? colors.error : colors.muted} />
        <View style={{ flex: 1 }}>
          <Text style={styles.small}>Admin · dolda artiklar</Text>
          <Text style={styles.value} numberOfLines={1} testID="hidden-filter-value">
            {label}
          </Text>
        </View>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={24} color={colors.onSurface} />
      </Pressable>
      {open && (
        <View style={styles.panel} testID="hidden-filter-dropdown">
          {options.map(([id, text]) => {
            const active = id === value;
            return (
              <Pressable
                key={id || "all"}
                testID={`hidden-filter-option-${id || "all"}`}
                onPress={() => {
                  haptic("selection");
                  onChange(id);
                  setOpen(false);
                }}
                style={({ pressed }) => [styles.row, active && styles.rowActive, pressed && { backgroundColor: colors.surfaceTertiary }]}
              >
                <Text style={[styles.rowText, active && { color: colors.brandSecondary }]}>{text}</Text>
                {active && <Icon name="check" size={20} color={colors.brandSecondary} />}
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  wrap: { marginBottom: spacing.md },
  toggle: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 52, paddingHorizontal: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary },
  small: { color: c.muted, fontFamily: fonts.bodyBold, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8 },
  value: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  panel: { marginTop: spacing.xs, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surfaceSecondary, overflow: "hidden" },
  row: { flexDirection: "row", alignItems: "center", minHeight: 48, paddingHorizontal: spacing.lg, borderBottomWidth: 1, borderBottomColor: c.divider },
  rowActive: { backgroundColor: c.brandTertiary },
  rowText: { flex: 1, color: c.onSurface, fontFamily: fonts.body, fontSize: 14 },
}));

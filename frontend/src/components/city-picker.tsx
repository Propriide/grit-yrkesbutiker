import { useState } from "react";
import { FlatList, Modal, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { City } from "@/src/api";
import { Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Props = {
  cities: City[];
  value: string | null;
  onChange: (id: string | null) => void;
  label?: string;
  testID: string;
  allowNone?: boolean;
};

export function CityPicker({ cities, value, onChange, label = "Ort", testID, allowNone }: Props) {
  const [open, setOpen] = useState(false);
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const selected = cities.find((c) => c.id === value);
  const options: (City | { id: null; name: string })[] = allowNone ? [{ id: null, name: "Ingen ort" }, ...cities] : cities;

  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <Pressable testID={testID} onPress={() => setOpen(true)} style={styles.select}>
        <Text style={[styles.value, !selected && { color: colors.muted }]}>{selected?.name ?? "Välj ort"}</Text>
        <Icon name="chevron-down" size={22} color={colors.onSurfaceTertiary} />
      </Pressable>
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)} testID="city-picker-backdrop" />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}>
          <View style={styles.handle} />
          <Text style={styles.sheetTitle}>Välj ort</Text>
          <FlatList
            data={options}
            keyExtractor={(i) => i.id ?? "none"}
            style={{ maxHeight: 420 }}
            ListEmptyComponent={<Text style={styles.emptyText}>Inga orter har lagts upp ännu.</Text>}
            renderItem={({ item }) => (
              <Pressable
                testID={`city-option-${item.id ?? "none"}`}
                onPress={() => {
                  onChange(item.id);
                  setOpen(false);
                }}
                style={({ pressed }) => [styles.option, pressed && { backgroundColor: colors.surfaceTertiary }]}
              >
                <Text style={styles.optionText}>{item.name}</Text>
                {item.id === value && <Icon name="check-bold" size={20} color={colors.brandPrimary} />}
              </Pressable>
            )}
          />
        </View>
      </Modal>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  field: { marginBottom: spacing.lg },
  label: { color: c.onSurfaceSecondary, fontFamily: fonts.bodyBold, fontSize: 12, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: 0.8 },
  select: {
    minHeight: 50,
    backgroundColor: c.surfaceTertiary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: c.border,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  value: { color: c.onSurface, fontFamily: fonts.body, fontSize: 16 },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)" },
  sheet: { backgroundColor: c.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingHorizontal: spacing.lg },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: c.borderStrong, alignSelf: "center", marginVertical: spacing.md },
  sheetTitle: { color: c.onSurface, fontFamily: fonts.display, fontSize: 22, textTransform: "uppercase", marginBottom: spacing.sm },
  option: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: c.divider, paddingHorizontal: spacing.sm },
  optionText: { color: c.onSurface, fontFamily: fonts.body, fontSize: 16 },
  emptyText: { color: c.muted, fontFamily: fonts.body, padding: spacing.lg },
}));

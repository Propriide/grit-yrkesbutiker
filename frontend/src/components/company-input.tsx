import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { api, Company } from "@/src/api";
import { haptic, Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export const companyKey = (s: string) => s.split(/\s+/).filter(Boolean).join(" ").toLowerCase();

/** Company name field for admins: type freely or pick an existing company from the dropdown. */
export function CompanyInput({ value, onChange, testID }: { value: string; onChange: (v: string) => void; testID: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const companies = useQuery({ queryKey: ["admin-companies"], queryFn: () => api<Company[]>("/admin/companies") });
  const all = companies.data ?? [];
  const key = companyKey(value);
  const match = all.find((c) => c.key === key);
  const shown = (key && !match ? all.filter((c) => c.key.includes(key)) : all).slice(0, 40);

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>Företag</Text>
      <View style={[styles.inputRow, (focused || open) && { borderColor: colors.brandPrimary }]}>
        <TextInput
          testID={testID}
          value={value}
          onChangeText={(v) => {
            onChange(v);
            setOpen(true);
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Skriv eller välj företag"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />
        <Pressable testID={`${testID}-toggle`} onPress={() => setOpen((o) => !o)} style={styles.toggle} hitSlop={6}>
          <Icon name={open ? "chevron-up" : "chevron-down"} size={24} color={colors.onSurface} />
        </Pressable>
      </View>
      {!!match && (
        <Text style={styles.hint} testID={`${testID}-match`}>
          Kopplas till {match.name} ({match.count} {match.count === 1 ? "konto" : "konton"})
        </Text>
      )}
      {open && (
        <View style={styles.list} testID={`${testID}-dropdown`}>
          {shown.length === 0 ? (
            <Text style={styles.empty}>Inget befintligt företag matchar – ett nytt skapas.</Text>
          ) : (
            shown.map((c) => (
              <Pressable
                key={c.key}
                testID={`${testID}-option-${c.key.replace(/\s+/g, "-")}`}
                onPress={() => {
                  haptic("selection");
                  onChange(c.name);
                  setOpen(false);
                }}
                style={({ pressed }) => [styles.option, c.key === key && styles.optionActive, pressed && { backgroundColor: colors.surfaceTertiary }]}
              >
                <Text style={styles.optionText} numberOfLines={1}>
                  {c.name}
                </Text>
                <Text style={styles.optionCount}>{c.count}</Text>
              </Pressable>
            ))
          )}
        </View>
      )}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  wrap: { marginBottom: spacing.lg },
  label: { color: c.onSurfaceSecondary, fontFamily: fonts.bodyBold, fontSize: 12, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: 0.8 },
  inputRow: { flexDirection: "row", alignItems: "center", minHeight: 50, backgroundColor: c.surfaceTertiary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border },
  input: { flex: 1, color: c.onSurface, paddingHorizontal: spacing.lg, fontFamily: fonts.body, fontSize: 16, minHeight: 50, ...({ outlineWidth: 0 } as object) },
  toggle: { width: 48, height: 48, alignItems: "center", justifyContent: "center", borderLeftWidth: 1, borderLeftColor: c.border },
  hint: { color: c.success, fontFamily: fonts.body, fontSize: 12, marginTop: spacing.xs },
  list: { marginTop: spacing.xs, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, overflow: "hidden" },
  option: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 48, paddingHorizontal: spacing.lg, borderBottomWidth: 1, borderBottomColor: c.divider },
  optionActive: { backgroundColor: c.brandTertiary },
  optionText: { flex: 1, color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  optionCount: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  empty: { color: c.muted, fontFamily: fonts.body, fontSize: 13, padding: spacing.lg },
}));

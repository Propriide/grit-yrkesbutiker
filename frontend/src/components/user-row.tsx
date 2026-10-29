import { Pressable, Text, View } from "react-native";

import { User } from "@/src/api";
import { Icon } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export function UserRow({ user, onPress }: { user: User; onPress: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <Pressable testID={`user-row-${user.email}`} onPress={onPress} style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceTertiary }]}>
      <View style={{ flex: 1 }}>
        <View style={styles.nameRow}>
          <Text style={styles.company} numberOfLines={1}>
            {user.company}
          </Text>
          {user.role === "admin" && <Text style={styles.tagAdmin}>ADMIN</Text>}
          {user.disabled && <Text style={styles.tagDisabled}>SPÄRRAD</Text>}
        </View>
        <Text style={styles.email} numberOfLines={1}>
          {user.email}
        </Text>
        <Text style={styles.meta}>
          {user.city_name || "Ingen ort"}
          {user.org_number ? `  ·  ${user.org_number}` : ""}
        </Text>
      </View>
      <Icon name="chevron-right" size={22} color={colors.muted} />
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.lg },
  nameRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  company: { color: c.onSurface, fontFamily: fonts.display, fontSize: 20, textTransform: "uppercase", flexShrink: 1 },
  tagAdmin: { color: c.onBrandSecondary, backgroundColor: c.brandSecondary, fontFamily: fonts.bodyBold, fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm, overflow: "hidden" },
  tagDisabled: { color: c.onError, backgroundColor: c.error, fontFamily: fonts.bodyBold, fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: radius.sm, overflow: "hidden" },
  email: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 13 },
  meta: { color: c.muted, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
}));

import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { Icon } from "@/src/components/ui";
import { useFavorites } from "@/src/favorites";
import { fonts, makeStyles, radius, useTheme } from "@/src/theme";

export function FavoritesButton() {
  const styles = useStyles();
  const { colors } = useTheme();
  const n = useFavorites().list.length;
  return (
    <Pressable testID="favorites-button" onPress={() => router.push("/favorites")} hitSlop={6} style={styles.btn}>
      <Icon name={n ? "heart" : "heart-outline"} size={24} color={n ? colors.brandPrimary : colors.onSurface} />
      {n > 0 && (
        <View style={styles.badge}>
          <Text style={styles.badgeText} testID="favorites-count">
            {n > 99 ? "99+" : n}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const useStyles = makeStyles((c) => ({
  btn: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border, alignItems: "center", justifyContent: "center" },
  badge: { position: "absolute", top: -5, right: -5, minWidth: 20, height: 20, borderRadius: 10, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  badgeText: { color: c.onBrandPrimary, fontFamily: fonts.bodyBold, fontSize: 11 },
}));

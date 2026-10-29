import { Image } from "expo-image";
import { router } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button, EmptyState, haptic, Icon, ScreenHeader } from "@/src/components/ui";
import { useFavorites } from "@/src/favorites";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useToast } from "@/src/toast";

export default function Favorites() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const toast = useToast();
  const favs = useFavorites();

  return (
    <View style={styles.root}>
      <ScreenHeader title="Mina favoriter" subtitle={favs.list.length ? `${favs.list.length} sparade plagg` : undefined} />
      <FlatList
        testID="favorites-list"
        data={favs.list}
        keyExtractor={(f) => f.id}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={favs.query.isRefetching} onRefresh={() => favs.query.refetch()} tintColor={colors.brandPrimary} />}
        ListEmptyComponent={
          favs.query.isLoading ? (
            <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: spacing.xxl }} />
          ) : (
            <EmptyState
              icon="heart-outline"
              title="Inga favoriter än"
              text="Tryck på hjärtat på ett plagg för att spara det med vald färg."
              action={<Button title="Till sortimentet" testID="favorites-shop-button" onPress={() => router.push("/(tabs)/shop")} />}
            />
          )
        }
        renderItem={({ item }) => (
          <Pressable
            testID={`favorite-row-${item.part_no}-${item.color_code ?? "none"}`}
            onPress={() => router.push(item.color_code ? `/product/${item.part_no}?color=${item.color_code}` : `/product/${item.part_no}`)}
            style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceTertiary }]}
          >
            <View style={styles.imgWrap}>
              <Image source={{ uri: item.image_url ? `${item.image_url}?w=200` : undefined }} style={styles.img} contentFit="contain" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.partNo}>
                {item.part_no}
                {item.color_code ? `-${item.color_code}` : ""}
              </Text>
              <Text style={styles.name} numberOfLines={2}>
                {item.name}
              </Text>
              {!!item.color_name && <Text style={styles.color}>{item.color_name}</Text>}
              <Text style={styles.cta}>Välj storlek & beställ ›</Text>
            </View>
            <Pressable
              testID={`favorite-remove-${item.part_no}-${item.color_code ?? "none"}`}
              hitSlop={8}
              onPress={async () => {
                haptic("selection");
                try {
                  await favs.remove(item.id);
                } catch (e: any) {
                  toast(e.message, "error");
                }
              }}
              style={styles.removeBtn}
            >
              <Icon name="heart-remove" size={22} color={colors.error} />
            </Pressable>
          </Pressable>
        )}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: c.border, padding: spacing.md },
  imgWrap: { width: 80, height: 80, borderRadius: radius.sm, backgroundColor: "#F2F2F2", padding: 4 },
  img: { width: "100%", height: "100%" },
  partNo: { color: c.muted, fontFamily: fonts.body, fontSize: 11, letterSpacing: 0.5 },
  name: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 14 },
  color: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 12, marginTop: 2 },
  cta: { color: c.brandPrimary, fontFamily: fonts.bodyBold, fontSize: 12, marginTop: spacing.xs },
  removeBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
}));

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, ScrollView, Text, TextInput, View, useWindowDimensions } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, CategoryGroup, Product } from "@/src/api";
import { Button, EmptyState, haptic, Icon } from "@/src/components/ui";
import { filterCount, FilterSheet, FilterState } from "@/src/components/filter-sheet";
import { usesNativeTabs } from "@/src/navigation";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Page = { items: Product[]; total: number; page: number; has_more: boolean; syncing: boolean };

export default function Shop() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const { width } = useWindowDimensions();
  const cardW = (Math.min(width, 700) - spacing.lg * 3) / 2;
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [group, setGroup] = useState("");
  const [category, setCategory] = useState("");
  const [filters, setFilters] = useState<FilterState>({});
  const [filterOpen, setFilterOpen] = useState(false);
  const [gender, setGender] = useState<"unset" | "" | "herr" | "dam">("unset");
  const params = useLocalSearchParams<{ group?: string; t?: string; pick?: string }>();

  useEffect(() => {
    if (params.pick) setGender("unset");
  }, [params.pick, params.t]);

  useEffect(() => {
    if (params.group !== undefined) {
      setGroup(params.group);
      setCategory("");
    }
  }, [params.group, params.t]);

  useEffect(() => {
    const t = setTimeout(() => setQ(search), 350);
    return () => clearTimeout(t);
  }, [search]);

  const g = gender === "unset" ? "" : gender;
  const baseQuery = `q=${encodeURIComponent(q)}&group=${encodeURIComponent(group)}&category=${encodeURIComponent(category)}&gender=${g}`;
  const filtersJson = JSON.stringify(filters);
  const nFilters = filterCount(filters);
  const selColors = filters.Color ?? [];
  const cats = useQuery({ queryKey: ["categories", g], queryFn: () => api<CategoryGroup[]>(`/categories?gender=${g}`) });
  const list = useInfiniteQuery({
    queryKey: ["products", baseQuery, filtersJson],
    enabled: gender !== "unset",
    initialPageParam: 1,
    queryFn: ({ pageParam }) => api<Page>(`/products?page=${pageParam}&page_size=20&${baseQuery}&filters=${encodeURIComponent(filtersJson)}`),
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
    refetchInterval: (query) => (query.state.data?.pages[0]?.syncing && !query.state.data?.pages[0]?.total ? 5000 : false),
  });
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const total = list.data?.pages[0]?.total ?? 0;
  const syncing = list.data?.pages[0]?.syncing;

  const groups = cats.data ?? [];
  const activeGroup = groups.find((g) => g.slug === group);
  const selectGroup = (slug: string) => {
    haptic("selection");
    setGroup(slug);
    setCategory("");
  };
  const pickGender = (v: "" | "herr" | "dam") => {
    haptic("selection");
    setGender(v);
    setGroup("");
    setCategory("");
  };

  if (gender === "unset") {
    return (
      <View style={[styles.root, { paddingTop: insets.top + spacing.md, paddingBottom: bottomChrome + spacing.lg }]} testID="gender-picker">
        <View style={[styles.titleRow, { paddingHorizontal: spacing.lg }]}>
          <View style={styles.mark} />
          <Text style={styles.title}>Sortiment</Text>
        </View>
        <Text style={styles.pickHelp}>Välj vilket sortiment du vill se</Text>
        <View style={styles.pickWrap}>
          {(
            [
              ["herr", "Herr", "human-male"],
              ["dam", "Dam", "human-female"],
            ] as const
          ).map(([val, label, icon], i) => (
            <Animated.View key={val} entering={FadeInDown.delay(i * 80).duration(300)} style={{ flex: 1 }}>
              <Pressable testID={`gender-pick-${val}`} onPress={() => pickGender(val)} style={({ pressed }) => [styles.pickTile, pressed && { transform: [{ scale: 0.98 }], borderColor: colors.brandPrimary }]}>
                <Icon name={icon} size={56} color={colors.brandPrimary} />
                <Text style={styles.pickLabel}>{label}</Text>
                <Icon name="arrow-right" size={26} color={colors.onSurface} />
              </Pressable>
            </Animated.View>
          ))}
        </View>
        <Pressable testID="gender-pick-all" onPress={() => pickGender("")} style={styles.pickAll}>
          <Text style={styles.pickAllText}>Visa hela sortimentet</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.titleRow}>
          <View style={styles.mark} />
          <Text style={styles.title}>Sortiment</Text>
          <Text style={styles.count} testID="product-count">
            {total ? `${total} artiklar` : ""}
          </Text>
        </View>
        <View style={styles.segment} testID="gender-toggle">
          {(
            [
              ["herr", "Herr"],
              ["dam", "Dam"],
              ["", "Alla"],
            ] as const
          ).map(([val, label]) => {
            const active = gender === val;
            return (
              <Pressable
                key={label}
                testID={`gender-toggle-${label.toLowerCase()}`}
                onPress={() => pickGender(active && val !== "" ? "" : val)}
                style={[styles.segBtn, active && styles.segBtnActive]}
              >
                <Text style={[styles.segText, active && styles.segTextActive]}>{label}</Text>
              </Pressable>
            );
          })}
        </View>
        <View style={styles.searchRow}>
          <View style={[styles.search, { flex: 1 }]}>
            <Icon name="magnify" size={22} color={colors.muted} />
            <TextInput
              testID="product-search-input"
              value={search}
              onChangeText={setSearch}
              placeholder="Sök namn eller artikelnummer"
              placeholderTextColor={colors.muted}
              style={styles.searchInput}
              returnKeyType="search"
              autoCorrect={false}
            />
            {!!search && (
              <Pressable testID="product-search-clear" onPress={() => setSearch("")} hitSlop={8}>
                <Icon name="close-circle" size={20} color={colors.muted} />
              </Pressable>
            )}
          </View>
          <Pressable testID="open-filter-button" onPress={() => setFilterOpen(true)} style={[styles.filterBtn, nFilters > 0 && styles.filterBtnActive]}>
            <Icon name="tune-variant" size={22} color={nFilters > 0 ? colors.onBrandPrimary : colors.onSurface} />
            {nFilters > 0 && (
              <View style={styles.filterBadge}>
                <Text style={styles.filterBadgeText} testID="filter-count-badge">
                  {nFilters}
                </Text>
              </View>
            )}
          </Pressable>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow} contentContainerStyle={styles.chipContent}>
          {[{ slug: "", name: "Alla" }, ...groups].map((g) => {
            const active = g.slug === group;
            return (
              <Pressable
                key={g.slug || "all"}
                testID={`group-chip-${g.slug || "alla"}`}
                hitSlop={{ top: 6, bottom: 6 }}
                onPress={() => selectGroup(g.slug)}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{g.name}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
        {activeGroup && activeGroup.children.length > 0 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.subRow} contentContainerStyle={styles.chipContent}>
            {[{ slug: "", name: `Alla ${activeGroup.name.toLowerCase()}`, count: activeGroup.count }, ...activeGroup.children].map((c) => {
              const active = c.slug === category;
              return (
                <Pressable
                  key={c.slug || "all"}
                  testID={`category-chip-${c.slug || "alla"}`}
                  onPress={() => {
                    haptic("selection");
                    setCategory(c.slug);
                  }}
                  style={[styles.subChip, active && styles.subChipActive]}
                >
                  <Text style={[styles.subChipText, active && styles.subChipTextActive]}>
                    {c.name} <Text style={styles.subCount}>{c.count}</Text>
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
        )}
      </View>

      {list.isLoading ? (
        <View style={styles.grid}>
          {Array.from({ length: 6 }).map((_, i) => (
            <View key={i} style={[styles.skeleton, { width: cardW }]} />
          ))}
        </View>
      ) : list.isError ? (
        <EmptyState
          icon="alert-octagon"
          title="Kunde inte ladda produkter"
          text={(list.error as Error).message}
          action={<Button title="Försök igen" testID="products-retry-button" onPress={() => list.refetch()} />}
        />
      ) : (
        <FlatList
          testID="product-list"
          data={items}
          numColumns={2}
          keyExtractor={(p) => p.part_no}
          columnWrapperStyle={{ gap: spacing.lg }}
          contentContainerStyle={[styles.listContent, { paddingBottom: bottomChrome + spacing.xl }]}
          onEndReachedThreshold={0.5}
          onEndReached={() => list.hasNextPage && !list.isFetchingNextPage && list.fetchNextPage()}
          refreshControl={<RefreshControl refreshing={list.isRefetching && !list.isFetchingNextPage} onRefresh={() => list.refetch()} tintColor={colors.brandPrimary} />}
          ListEmptyComponent={
            syncing ? (
              <EmptyState icon="warehouse" title="Hämtar sortimentet" text="Produkterna laddas in från Blåkläder. Det tar någon minut första gången." />
            ) : (
              <EmptyState
                icon="warehouse"
                title="Inga produkter hittades"
                text="Prova en annan sökning, kategori eller färre filter."
                action={nFilters > 0 ? <Button title="Rensa filter" variant="secondary" testID="clear-filters-button" onPress={() => setFilters({})} /> : undefined}
              />
            )
          }
          ListFooterComponent={list.isFetchingNextPage ? <ActivityIndicator color={colors.brandPrimary} style={{ margin: spacing.lg }} /> : null}
          renderItem={({ item, index }) => {
            const match = selColors.length ? item.colors?.find((c) => c.base?.some((b) => selColors.includes(b))) : undefined;
            const img = match?.image_url || item.image_url;
            return (
            <Animated.View entering={FadeInDown.delay((index % 10) * 40).duration(300)}>
              <Pressable
                testID={`product-card-${item.part_no}`}
                onPress={() => router.push(match ? `/product/${item.part_no}?color=${match.code}` : `/product/${item.part_no}`)}
                style={({ pressed }) => [styles.card, { width: cardW }, pressed && { transform: [{ scale: 0.97 }] }]}
              >
                <View style={styles.imgWrap}>
                  <Image source={{ uri: img ? `${img}?w=400` : undefined }} style={styles.img} contentFit="contain" transition={200} />
                </View>
                <View style={styles.cardBody}>
                  <Text style={styles.partNo}>{item.part_no}</Text>
                  <Text style={styles.name} numberOfLines={2}>
                    {item.name}
                  </Text>
                  {(match || item.colors?.length > 1) && (
                    <View style={styles.cardFoot}>
                      <Text style={styles.colorsCount}>{match ? match.name : `${item.colors.length} färger`}</Text>
                    </View>
                  )}
                </View>
              </Pressable>
            </Animated.View>
            );
          }}
        />
      )}
      <FilterSheet visible={filterOpen} onClose={() => setFilterOpen(false)} value={filters} onApply={setFilters} query={baseQuery} />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  pickHelp: { color: c.onSurfaceSecondary, fontFamily: fonts.body, fontSize: 15, paddingHorizontal: spacing.lg, marginBottom: spacing.xl },
  pickWrap: { flex: 1, gap: spacing.lg, paddingHorizontal: spacing.lg },
  pickTile: { flex: 1, flexDirection: "row", alignItems: "center", gap: spacing.lg, backgroundColor: c.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: c.border, borderLeftWidth: 6, borderLeftColor: c.brandPrimary, paddingHorizontal: spacing.xl },
  pickLabel: { flex: 1, color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 44, textTransform: "uppercase" },
  pickAll: { minHeight: 52, alignItems: "center", justifyContent: "center", marginTop: spacing.md },
  pickAllText: { color: c.brandPrimary, fontFamily: fonts.bodyBold, fontSize: 15 },
  segment: { flexDirection: "row", backgroundColor: c.surfaceTertiary, borderRadius: radius.md, padding: 4, marginBottom: spacing.md, gap: 4 },
  segBtn: { flex: 1, height: 44, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  segBtnActive: { backgroundColor: c.brandPrimary },
  segText: { color: c.onSurfaceSecondary, fontFamily: fonts.display, fontSize: 17, textTransform: "uppercase", letterSpacing: 1 },
  segTextActive: { color: c.onBrandPrimary },
  searchRow: { flexDirection: "row", gap: spacing.sm },
  filterBtn: { width: 48, height: 48, borderRadius: radius.md, backgroundColor: c.surfaceTertiary, borderWidth: 1, borderColor: c.border, alignItems: "center", justifyContent: "center" },
  filterBtnActive: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary },
  filterBadge: { position: "absolute", top: -6, right: -6, minWidth: 20, height: 20, borderRadius: 10, backgroundColor: c.brandSecondary, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  filterBadgeText: { color: c.onBrandSecondary, fontFamily: fonts.bodyBold, fontSize: 11 },
  header: { backgroundColor: c.surface, paddingHorizontal: spacing.lg, borderBottomWidth: 1, borderBottomColor: c.divider },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.md },
  mark: { width: 8, height: 26, backgroundColor: c.brandPrimary },
  title: { color: c.onSurface, fontFamily: fonts.displayHeavy, fontSize: 32, textTransform: "uppercase", flex: 1 },
  count: { color: c.muted, fontFamily: fonts.body, fontSize: 12 },
  search: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: c.surfaceTertiary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 48,
    borderWidth: 1,
    borderColor: c.border,
  },
  searchInput: { flex: 1, color: c.onSurface, fontFamily: fonts.body, fontSize: 15, height: 48, ...({ outlineWidth: 0 } as object) },
  chipRow: { height: 56, flexGrow: 0, marginHorizontal: -spacing.lg },
  chipContent: { gap: spacing.sm, paddingHorizontal: spacing.lg, alignItems: "center" },
  chip: {
    height: 36,
    flexShrink: 0,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: c.border,
    backgroundColor: c.surfaceSecondary,
    justifyContent: "center",
  },
  chipActive: { backgroundColor: c.brandPrimary, borderColor: c.brandPrimary },
  chipText: { color: c.onSurfaceSecondary, fontFamily: fonts.bodyBold, fontSize: 13 },
  chipTextActive: { color: c.onBrandPrimary },
  subRow: { height: 48, flexGrow: 0, marginHorizontal: -spacing.lg, marginTop: -spacing.sm },
  subChip: {
    height: 36,
    flexShrink: 0,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: c.border,
    justifyContent: "center",
  },
  subChipActive: { borderColor: c.brandSecondary, backgroundColor: c.brandTertiary },
  subChipText: { color: c.onSurfaceTertiary, fontFamily: fonts.body, fontSize: 13 },
  subChipTextActive: { color: c.brandSecondary },
  subCount: { color: c.muted, fontSize: 11 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.lg, padding: spacing.lg },
  skeleton: { height: 250, borderRadius: radius.md, backgroundColor: c.surfaceSecondary },
  listContent: { padding: spacing.lg, gap: spacing.lg },
  card: { backgroundColor: c.surfaceSecondary, borderRadius: radius.md, overflow: "hidden", borderWidth: 1, borderColor: c.border },
  imgWrap: { backgroundColor: "#F2F2F2", aspectRatio: 1, padding: spacing.sm },
  img: { width: "100%", height: "100%" },
  cardBody: { padding: spacing.md, gap: 2 },
  partNo: { color: c.muted, fontFamily: fonts.body, fontSize: 11, letterSpacing: 0.5 },
  name: { color: c.onSurface, fontFamily: fonts.bodyBold, fontSize: 13, minHeight: 34 },
  cardFoot: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", marginTop: spacing.xs },
  colorsCount: { color: c.muted, fontFamily: fonts.body, fontSize: 11 },
}));

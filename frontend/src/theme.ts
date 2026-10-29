// Design tokens (from /app/design_guidelines.json). Dark-first utility theme.
// Use `makeStyles` for sheets and `useTheme().colors` for non-style color props.

import { useMemo } from "react";
import { Appearance, StyleSheet } from "react-native";

export type ColorScheme = "light" | "dark";

const dark = {
  surface: "#121212",
  onSurface: "#FFFFFF",
  surfaceSecondary: "#1C1C1E",
  onSurfaceSecondary: "#E0E0E0",
  surfaceTertiary: "#2C2C2E",
  onSurfaceTertiary: "#BDBDBD",
  surfaceInverse: "#FFFFFF",
  onSurfaceInverse: "#121212",
  muted: "#8A8A8A",

  brand: "#FF9900",
  onBrand: "#000000",
  brandPrimary: "#FF9900",
  onBrandPrimary: "#000000",
  brandSecondary: "#FFCC00",
  onBrandSecondary: "#000000",
  brandTertiary: "#4A3100",
  onBrandTertiary: "#FFCC00",

  success: "#4CAF50",
  onSuccess: "#000000",
  warning: "#FFC107",
  onWarning: "#000000",
  error: "#F44336",
  onError: "#FFFFFF",
  info: "#2196F3",
  onInfo: "#FFFFFF",

  border: "#333333",
  borderStrong: "#555555",
  divider: "#2C2C2C",
  scrim: "rgba(18,18,18,0.92)",
};

export type ThemeColors = typeof dark;

export const defaultScheme = "dark" satisfies ColorScheme;

export const themes: { light?: ThemeColors; dark: ThemeColors } = { dark };

export const colors = dark;

export const fonts = {
  display: "BarlowCondensed-Bold",
  displaySemi: "BarlowCondensed-SemiBold",
  displayHeavy: "BarlowCondensed-ExtraBold",
  body: "Chivo-Regular",
  bodyBold: "Chivo-Bold",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 };
export const radius = { sm: 4, md: 8, lg: 12, pill: 999 };

export function setColorScheme(scheme: ColorScheme | null) {
  Appearance.setColorScheme?.(scheme ?? "unspecified");
}

// App ships dark only: keep native chrome dark.
setColorScheme?.(defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  return { scheme: "dark", colors: dark };
}

export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors: c } = useTheme();
    return useMemo(() => StyleSheet.create(factory(c)), [c]);
  };
}

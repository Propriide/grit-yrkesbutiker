// Design tokens (from /app/design_guidelines.json). Dark-first utility theme.
// Use `makeStyles` for sheets and `useTheme().colors` for non-style color props.

import { useMemo } from "react";
import { Appearance, StyleSheet } from "react-native";

export type ColorScheme = "light" | "dark";

const dark = {
  surface: "#0D1523",
  onSurface: "#FFFFFF",
  surfaceSecondary: "#131E30",
  onSurfaceSecondary: "#DDE1E8",
  surfaceTertiary: "#1C2A42",
  onSurfaceTertiary: "#B8C2D1",
  surfaceInverse: "#FFFFFF",
  onSurfaceInverse: "#0D1523",
  muted: "#94A3B8",

  brand: "#D0102E",
  onBrand: "#FFFFFF",
  brandPrimary: "#D0102E",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#FF5468",
  onBrandSecondary: "#FFFFFF",
  brandTertiary: "#3B1222",
  onBrandTertiary: "#FF5468",

  success: "#4CAF50",
  onSuccess: "#000000",
  warning: "#FFC107",
  onWarning: "#000000",
  error: "#F44336",
  onError: "#FFFFFF",
  info: "#2196F3",
  onInfo: "#FFFFFF",

  border: "#2C3B56",
  borderStrong: "#475673",
  divider: "#1F2C44",
  scrim: "rgba(13,21,35,0.92)",
};

export type ThemeColors = typeof dark;

export const defaultScheme = "dark" satisfies ColorScheme;

export const themes: { light?: ThemeColors; dark: ThemeColors } = { dark };

export const colors = dark;

export const fonts = {
  display: "UnitedSansCond-Bold",
  displaySemi: "UnitedSansCond-Bold",
  displayHeavy: "UnitedSansCond-Black",
  body: "Gotham-Book",
  bodyBold: "Gotham-Medium",
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

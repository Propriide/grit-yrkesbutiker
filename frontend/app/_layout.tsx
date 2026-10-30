import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { LogBox, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider } from "@/src/auth";
import { CartProvider } from "@/src/cart";
import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";
import { colors } from "@/src/theme";
import { ToastProvider } from "@/src/toast";

LogBox.ignoreAllLogs(true);

export default function RootLayout() {
  // Prewarm brand fonts + icon font so icons render in Expo Go on Android.
  const [loaded, error] = useFonts({
    "UnitedSansCond-Bold": require("../assets/fonts/UnitedSansCond-Bold.otf"),
    "UnitedSansCond-Black": require("../assets/fonts/UnitedSansCond-Black.otf"),
    "Gotham-Book": require("../assets/fonts/Gotham-Book.otf"),
    "Gotham-Medium": require("../assets/fonts/Gotham-Medium.otf"),
    MaterialDesignIcons: require("@react-native-vector-icons/material-design-icons/fonts/MaterialDesignIcons.ttf"),
  });

  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={styles.root}>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <KeyboardProvider>
            <AuthProvider>
              <CartProvider>
                <ToastProvider>
                  <StatusBar style="light" />
                  <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />
                </ToastProvider>
              </CartProvider>
            </AuthProvider>
          </KeyboardProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
});

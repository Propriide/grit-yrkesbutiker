import AsyncStorage from "@react-native-async-storage/async-storage";
import { QueryClientProvider } from "@tanstack/react-query";
import * as Linking from "expo-linking";
import * as Notifications from "expo-notifications";
import { useFonts } from "expo-font";
import { Stack, useRouter } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { Alert, LogBox, Platform, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider } from "@/src/auth";
import { CartProvider } from "@/src/cart";
import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";
import { colors } from "@/src/theme";
import { ToastProvider } from "@/src/toast";
import { registerServiceWorker } from "@/src/webpush";

LogBox.ignoreAllLogs(true);

// Push: foreground display + Android channel must exist before any push arrives (module scope).
if (Platform.OS !== "web") {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({ shouldShowAlert: true, shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
  });
}
if (Platform.OS === "android") {
  Notifications.setNotificationChannelAsync("default", { name: "Default", importance: 7 /* AndroidImportance.MAX */, sound: "default" });
}
registerServiceWorker();

function usePushTaps() {
  const router = useRouter();
  useEffect(() => {
    if (Platform.OS === "web") return;
    const open = (data: Record<string, any>) => {
      const url = data?.deeplink || data?.action_url;
      if (!url) return;
      if (String(url).startsWith("http")) Linking.openURL(url);
      else router.push(url);
    };
    const tapSub = Notifications.addNotificationResponseReceivedListener((r) => open(r.notification.request.content.data || {}));
    Notifications.getLastNotificationResponseAsync().then((r) => r && open(r.notification.request.content.data || {}));

    // Weekly nudge for users who blocked notifications.
    (async () => {
      const { status, canAskAgain } = await Notifications.getPermissionsAsync();
      if (status !== "denied" || canAskAgain) return;
      const last = await AsyncStorage.getItem("pushNudgeAt");
      if (last && Date.now() - Number(last) <= 7 * 24 * 60 * 60 * 1000) return;
      const stamp = () => AsyncStorage.setItem("pushNudgeAt", String(Date.now()));
      Alert.alert("Missa inga orderbesked", "Slå på notiser så får du veta direkt när din order är bekräftad eller klar.", [
        { text: "Senare", style: "cancel", onPress: stamp },
        {
          text: "Öppna inställningar",
          onPress: () => {
            stamp();
            Linking.openSettings();
          },
        },
      ]);
    })();
    return () => tapSub.remove();
  }, [router]);
}

export default function RootLayout() {
  usePushTaps();
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

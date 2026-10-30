import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { api } from "@/src/api";
import { subscribeWebPush, webPushPermission } from "@/src/webpush";

/** Ask for permission (only once the user is logged in) and register the native device token. Re-run on every app open. */
export async function registerForPush(userId: string) {
  if (Platform.OS === "web") {
    // Web/PWA: silently refresh an existing permission; asking requires a tap (Notiser screen).
    if (webPushPermission() === "granted") subscribeWebPush(false).catch(() => {});
    return;
  }
  try {
    const current = await Notifications.getPermissionsAsync();
    let status = current.status;
    if (status !== "granted" && current.canAskAgain) status = (await Notifications.requestPermissionsAsync()).status;
    if (status !== "granted") return;
    const token = await Notifications.getDevicePushTokenAsync();
    await api("/register-push", { method: "POST", body: { user_id: userId, platform: Platform.OS, device_token: String(token.data) } });
  } catch (e) {
    console.log("Push registration skipped", e);
  }
}

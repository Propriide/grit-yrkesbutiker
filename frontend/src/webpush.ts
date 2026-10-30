import { Platform } from "react-native";

import { api } from "@/src/api";

const web = Platform.OS === "web" && typeof window !== "undefined";

export const isIOSWeb = () => web && /iphone|ipad|ipod/i.test(navigator.userAgent);
export const isStandalone = () => web && (window.matchMedia?.("(display-mode: standalone)").matches || (navigator as any).standalone === true);
export const webPushSupported = () => web && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
export const webPushPermission = (): NotificationPermission | "unsupported" => (webPushSupported() ? Notification.permission : "unsupported");

/** Register the service worker (installable PWA + automatic updates). New versions reload the app once when activated. */
export function registerServiceWorker() {
  if (!web || !("serviceWorker" in navigator)) return;
  const hadController = !!navigator.serviceWorker.controller;
  let reloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hadController && !reloaded) {
      reloaded = true;
      window.location.reload();
    }
  });
  navigator.serviceWorker
    .register("/sw.js")
    .then((reg) => {
      // Check for a new release whenever the app comes back to the foreground.
      document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && reg.update().catch(() => {}));
    })
    .catch((e) => console.log("SW registration failed", e));
}

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/** Ask permission (must be called from a tap) and subscribe this browser/PWA to web push. */
export async function subscribeWebPush(askPermission = true): Promise<boolean> {
  if (!webPushSupported()) return false;
  let perm = Notification.permission;
  if (perm === "default" && askPermission) perm = await Notification.requestPermission();
  if (perm !== "granted") return false;
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    const { public_key } = await api<{ public_key: string }>("/webpush/public-key");
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(public_key) });
  }
  const json = sub.toJSON();
  await api("/webpush/subscribe", { method: "POST", body: { endpoint: json.endpoint, keys: json.keys } });
  return true;
}

export async function unsubscribeWebPush() {
  if (!webPushSupported()) return;
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg && (await reg.pushManager.getSubscription());
  if (!sub) return;
  await api("/webpush/unsubscribe", { method: "POST", body: { endpoint: sub.endpoint } }).catch(() => {});
  await sub.unsubscribe();
}

export async function hasWebPushSubscription() {
  if (!webPushSupported()) return false;
  const reg = await navigator.serviceWorker.getRegistration();
  return !!(reg && (await reg.pushManager.getSubscription()));
}

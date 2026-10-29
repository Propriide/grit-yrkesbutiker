import { Platform } from "react-native";

export const usesNativeTabs = Platform.OS === "ios" && parseInt(String(Platform.Version), 10) >= 26;

/** Last visited tab, so the header home button returns to where the user started. */
const TABS = { "/": "/(tabs)", "/shop": "/(tabs)/shop", "/cart": "/(tabs)/cart", "/profile": "/(tabs)/profile" } as const;
let lastTab: string = "/(tabs)/profile";
export function rememberTab(pathname: string) {
  const t = TABS[pathname as keyof typeof TABS];
  if (t) lastTab = t;
}
export const getLastTab = () => lastTab;

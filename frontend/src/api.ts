import { Platform } from "react-native";
import { storage } from "@/src/utils/storage";

// Web (PWA) talks to the backend on its own address, so the same build works on any domain.
const BASE = Platform.OS === "web" ? "/api" : `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;
export const TOKEN_KEY = "auth_token";

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, init: { method?: string; body?: any } = {}): Promise<T> {
  const token = await storage.secureGet(TOKEN_KEY, null);
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError("Ingen anslutning. Kontrollera ditt nätverk.", 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized?.();
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = "Kontrollera att alla fält är korrekt ifyllda.";
    throw new ApiError(msg || `Serverfel (${res.status}). Försök igen om en stund.`, res.status);
  }
  return data as T;
}

export type Color = { code: string; name: string; image_url?: string; base?: string[] };
export type Product = {
  part_no: string;
  name: string;
  description?: string;
  image_url?: string;
  colors: Color[];
  sizes: string[];
  groups?: string[];
  categories?: string[];
  hidden_city_ids?: string[];
  purchased?: boolean;
  purchased_color?: string | null;
};
export type FilterDef = { code: string; name: string; values: { value: string; count: number }[] };
export type AppNotification = {
  id: string;
  kind: "new" | "confirmed" | "declined" | "broadcast" | "ready";
  order_id: string | null;
  order_number: string | null;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
};
export type StoreInfo = { title: string; text: string; address: string; phone: string; email: string; hours: string };
export type CategoryGroup = {
  slug: string;
  name: string;
  count: number;
  children: { slug: string; name: string; count: number }[];
};
export type User = {
  id: string;
  email: string;
  role: "admin" | "customer";
  name?: string;
  phone: string;
  company: string;
  org_number: string;
  city_id: string | null;
  city_name: string | null;
  disabled: boolean;
  created_at?: string;
  order_count?: number;
  credits_enabled?: boolean;
  credits?: number;
};
export type City = { id: string; name: string };
export type Favorite = { id: string; part_no: string; name: string; color_code: string | null; color_name: string | null; image_url?: string; created_at: string };
export type Company = { key: string; name: string; count: number; spellings: string[]; credits_enabled?: boolean };
export type DeliveryMethod = "store" | "parcel_box" | "ship";
export type Delivery = { method: DeliveryMethod; name?: string; address?: string; postal_code?: string; city?: string };
export const DELIVERY_LABELS: Record<DeliveryMethod, string> = { store: "Hämtas i butik", parcel_box: "Hämtas i paketbox", ship: "Skickas" };
export const deliveryText = (d?: Delivery) =>
  !d ? "" : d.method !== "ship" ? DELIVERY_LABELS[d.method] : [DELIVERY_LABELS.ship + ":", d.name, d.address, `${d.postal_code ?? ""} ${d.city ?? ""}`.trim()].filter(Boolean).join(" ");
export type OrderItem = {
  part_no: string;
  name: string;
  size: string;
  quantity: number;
  color_code?: string | null;
  color_name?: string | null;
  image_url?: string;
};
export type Order = {
  id: string;
  order_number: string;
  user_id?: string;
  items: OrderItem[];
  comment: string;
  delivery?: Delivery;
  credits_earned?: number;
  created_at: string;
  email_status: string;
  status?: "new" | "confirmed" | "declined" | "ready";
  ready_at?: string;
  replies?: { message: string; created_at: string; action?: "confirm" | "decline" }[];
  customer: { company: string; email: string };
};

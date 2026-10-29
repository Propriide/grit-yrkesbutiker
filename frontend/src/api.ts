import { storage } from "@/src/utils/storage";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;
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
    throw new ApiError(msg || `Fel ${res.status}`, res.status);
  }
  return data as T;
}

export type Color = { code: string; name: string; image_url?: string };
export type Product = {
  part_no: string;
  name: string;
  description?: string;
  price?: number;
  image_url?: string;
  colors: Color[];
  sizes: string[];
  category: string;
};
export type User = {
  id: string;
  email: string;
  role: "admin" | "customer";
  phone: string;
  company: string;
  org_number: string;
  city_id: string | null;
  city_name: string | null;
  disabled: boolean;
  created_at?: string;
  order_count?: number;
};
export type City = { id: string; name: string };
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
  items: OrderItem[];
  comment: string;
  created_at: string;
  email_status: string;
  customer: { company: string; email: string };
};

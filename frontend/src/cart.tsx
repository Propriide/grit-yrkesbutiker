import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { storage } from "@/src/utils/storage";

export type CartItem = {
  key: string;
  part_no: string;
  name: string;
  image_url?: string;
  color_code?: string | null;
  color_name?: string | null;
  size: string;
  quantity: number;
};

type CartCtx = {
  items: CartItem[];
  count: number;
  add: (item: Omit<CartItem, "key">) => void;
  setQuantity: (key: string, q: number) => void;
  remove: (key: string) => void;
  clear: () => void;
};

const Ctx = createContext<CartCtx | null>(null);
const KEY = "cart_v1";

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    storage.getItem(KEY, null).then((raw) => {
      if (typeof raw === "string") {
        try {
          setItems(JSON.parse(raw));
        } catch {}
      }
      setReady(true);
    });
  }, []);

  useEffect(() => {
    if (ready) storage.setItem(KEY, JSON.stringify(items));
  }, [items, ready]);

  const value = useMemo<CartCtx>(
    () => ({
      items,
      count: items.reduce((s, i) => s + i.quantity, 0),
      add: (item) => {
        const key = `${item.part_no}|${item.color_code ?? ""}|${item.size}`;
        setItems((prev) => {
          const ex = prev.find((p) => p.key === key);
          if (ex) return prev.map((p) => (p.key === key ? { ...p, quantity: p.quantity + item.quantity } : p));
          return [...prev, { ...item, key }];
        });
      },
      setQuantity: (key, q) =>
        setItems((prev) => prev.map((p) => (p.key === key ? { ...p, quantity: Math.max(1, Math.min(9999, q)) } : p))),
      remove: (key) => setItems((prev) => prev.filter((p) => p.key !== key)),
      clear: () => setItems([]),
    }),
    [items],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCart outside provider");
  return c;
}

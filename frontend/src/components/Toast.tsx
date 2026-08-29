import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

/* A minimal toast: a module-level store + a portal-less viewport pinned
   bottom-right. No dependency, no context boilerplate. */

interface Toast {
  id: number;
  text: string;
  tone: "good" | "critical";
}

type Listener = (toasts: Toast[]) => void;

let toasts: Toast[] = [];
const listeners = new Set<Listener>();
let nextId = 1;

function emit() {
  for (const l of listeners) l([...toasts]);
}

export function toast(text: string, tone: Toast["tone"] = "good") {
  const t = { id: nextId++, text, tone };
  toasts = [...toasts, t];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((x) => x.id !== t.id);
    emit();
  }, 4200);
}

export function Toaster() {
  const [items, setItems] = useState<Toast[]>([]);

  useEffect(() => {
    listeners.add(setItems);
    return () => {
      listeners.delete(setItems);
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          role="status"
          className="animate-in flex items-center gap-2 rounded-lg border border-border bg-surface
                     px-3.5 py-2.5 text-xs font-medium text-ink shadow-xl"
        >
          {t.tone === "good" ? (
            <CheckCircle2 className="size-4 shrink-0 text-good" />
          ) : (
            <XCircle className="size-4 shrink-0 text-critical" />
          )}
          {t.text}
        </div>
      ))}
    </div>
  );
}

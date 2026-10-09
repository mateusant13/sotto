import { useLayoutEffect, useRef, useState } from "react";

export function useMeasureHeight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [height, setHeight] = useState(0);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setHeight(el.clientHeight));
    ro.observe(el);
    setHeight(el.clientHeight);
    return () => ro.disconnect();
  }, []);

  return [ref, height] as const;
}

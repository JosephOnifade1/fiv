import { useEffect, useRef } from "react";

/**
 * useInterval — calls `callback` every `delay` ms.
 * Pass delay=null to pause. Safely captures latest callback (no stale closures).
 */
export const useInterval = (callback, delay) => {
  const saved = useRef(callback);

  useEffect(() => { saved.current = callback; }, [callback]);

  useEffect(() => {
    if (delay === null || delay === undefined) return;
    const id = setInterval(() => saved.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
};

import { useEffect, useState } from "react";

/**
 * Returns a debounced version of `value` that only updates
 * after `delay` ms of inactivity.
 *
 * Usage:
 * ```
 * const [search, setSearch] = useState("");
 * const debouncedSearch = useDebounce(search, 300);
 * // filter / fetch based on debouncedSearch
 * ```
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debounced;
}

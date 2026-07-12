import { Search } from "lucide-react";

export function SearchInput({ label = "Search papers", disabled = false, placeholder = "Search" }: { label?: string; disabled?: boolean; placeholder?: string }) {
  return (
    <label className="search-shell">
      <span className="sr-only">{label}</span>
      <Search aria-hidden="true" size={16} />
      <input disabled={disabled} type="search" placeholder={placeholder} aria-label={label} />
    </label>
  );
}

import type { SortState } from "@/lib/sort";

type SortHeaderProps<K extends string> = {
  sortKey: K;
  sort: SortState<K>;
  onSort: (key: K) => void;
  /** Visible header text, often abbreviated ("Gls"). */
  label: string;
  /** Full name for tooltips and screen readers ("Goals"). Defaults to label. */
  title?: string;
  className?: string;
};

/**
 * A sortable column header for `.data-table`. Use inside a Client Component
 * that owns the sort state. The arrow comes from the `aria-sort` CSS.
 */
export function SortHeader<K extends string>({
  sortKey,
  sort,
  onSort,
  label,
  title,
  className,
}: SortHeaderProps<K>) {
  const active = sort.key === sortKey;
  return (
    <th scope="col" className={className} aria-sort={active ? sort.dir : undefined}>
      <button
        type="button"
        className="sort-btn"
        onClick={() => onSort(sortKey)}
        title={title ? `Sort by ${title.toLowerCase()}` : undefined}
      >
        {title && title !== label ? (
          <>
            <span aria-hidden="true">{label}</span>
            <span className="sr-only">{title}</span>
          </>
        ) : (
          label
        )}
      </button>
    </th>
  );
}

import Link from "next/link";

type BreadcrumbItem = {
  label: string;
  href?: string;
};

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((item, index) => {
          const current = index === items.length - 1;
          return (
            <li key={`${item.href ?? "current"}-${item.label}`}>
              {index > 0 ? <span className="breadcrumbs__separator" aria-hidden="true">/</span> : null}
              {item.href && !current ? (
                <Link href={item.href} className="breadcrumbs__link" title={item.label}>{item.label}</Link>
              ) : (
                <span className="breadcrumbs__current" aria-current="page" title={item.label}>{item.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

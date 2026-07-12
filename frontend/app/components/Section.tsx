import type { ReactNode } from "react";

export function Section({ title, description, children, actions }: { title: string; description?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="section-block">
      <div className="section-heading">
        <div><h2>{title}</h2>{description ? <p>{description}</p> : null}</div>
        {actions ? <div>{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

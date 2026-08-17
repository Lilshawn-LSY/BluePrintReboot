"use client";

import { useState } from "react";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";

const CATEGORIES = [
  "field", "organism", "method", "assay", "gene_or_protein", "cell_line_or_sample",
  "tissue_or_cell_type", "concept", "model_or_algorithm", "paper_type", "dataset", "other",
];

export function TagsView() {
  const resource = useApiResource("tags", async () => {
    const [tags, summary, governance] = await Promise.all([
      apiClient.getAllTags(),
      apiClient.getTagSummary(),
      apiClient.getTagGovernance(),
    ]);
    return { tags, summary, governance };
  });
  const [selectedKey, setSelectedKey] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newCategory, setNewCategory] = useState("other");
  const [newDescription, setNewDescription] = useState("");
  const [alias, setAlias] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<unknown>, success: string) => {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await action();
      setNotice(success);
      resource.retry();
    } catch (error) {
      setNotice(error instanceof ApiClientError ? error.message : "The canonical Tag Book command could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const selected = resource.status === "success"
    ? resource.data.governance.items.find((tag) => tag.canonical_key === selectedKey) ?? resource.data.governance.items[0]
    : undefined;

  return (
    <div className="page-stack">
      <PageHeader title="Tags" description="Manage your tag book and review tag candidates." />
      {resource.status === "loading" ? <LoadingState label="Loading canonical Tags" /> : null}
      {resource.status === "unavailable" ? <UnavailableState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "error" ? <ErrorState title="Tag Book unavailable" description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "not-found" ? <ErrorState description={resource.message} onRetry={resource.retry} /> : null}
      {resource.status === "success" ? (
        <>
          <Section title="Candidate quality summary" description="Measured counts from existing local evidence. They are not Paper tags and no values are fabricated when the source is unavailable.">
            {resource.data.summary.availability === "unavailable" ? (
              <EmptyState title="Candidate summary unavailable" description="No paper index is available to review candidates." />
            ) : resource.data.summary.state === "empty" ? (
              <EmptyState title="No candidate evidence" description={`The real source was evaluated across ${resource.data.summary.evaluated_paper_count} paper records and produced no candidates.`} />
            ) : (
              <div className="summary-strip summary-strip--six">
                <div><span>Candidates</span><strong>{resource.data.summary.candidate_count}</strong></div>
                <div><span>Known matches</span><strong>{resource.data.summary.known_canonical_match_count}</strong></div>
                <div><span>High</span><strong>{resource.data.summary.quality_counts.high}</strong></div>
                <div><span>Medium</span><strong>{resource.data.summary.quality_counts.medium}</strong></div>
                <div><span>Weak</span><strong>{resource.data.summary.quality_counts.weak}</strong></div>
                <div><span>Rejected</span><strong>{resource.data.summary.quality_counts.rejected}</strong></div>
              </div>
            )}
          </Section>

          <Section title="Create canonical tag" description="Canonical keys are stable identities derived from the label. Creation changes the registry only; existing Paper references remain untouched.">
            <form className="project-command-panel" onSubmit={(event) => {
              event.preventDefault();
              void run(async () => {
                await apiClient.createCanonicalTag({
                  label: newLabel,
                  category: newCategory,
                  description: newDescription,
                  suggestionStrength: 1,
                  expectedRevision: resource.data.governance.registry_revision,
                });
                setNewLabel("");
                setNewDescription("");
              }, "Canonical tag created. No Paper tags were changed.");
            }}>
              <div className="project-form-grid">
                <label className="reader-field"><span>Label</span><input value={newLabel} onChange={(event) => setNewLabel(event.target.value)} required maxLength={200} /></label>
                <label className="reader-field"><span>Category</span><select value={newCategory} onChange={(event) => setNewCategory(event.target.value)}>{CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
                <label className="reader-field project-form-wide"><span>Description (optional)</span><textarea value={newDescription} onChange={(event) => setNewDescription(event.target.value)} maxLength={2000} rows={2} /></label>
              </div>
              <div className="reader-editor__actions"><button className="reader-action" type="submit" disabled={busy || !newLabel.trim()}>Create canonical tag</button></div>
            </form>
          </Section>

          <Section title="Canonical registry" description={`${resource.data.tags.length} canonical Tag${resource.data.tags.length === 1 ? "" : "s"}; deprecated entries remain inspectable and are excluded from new candidate application.`}>
            {resource.data.governance.items.length === 0 ? (
              <EmptyState title="Tag Book is empty" description="Create an explicit canonical tag to begin managing the registry." />
            ) : (
              <DataTableShell label="Canonical Tag Book">
                <table>
                  <thead><tr><th>Label</th><th>Canonical key</th><th>Category</th><th>Aliases</th><th>Status</th><th /></tr></thead>
                  <tbody>{resource.data.governance.items.map((tag) => (
                    <tr key={tag.canonical_key}>
                      <td><strong>{tag.label}</strong></td><td className="mono-id">{tag.canonical_key}</td><td>{tag.category}</td>
                      <td><div className="tag-list">{tag.aliases.length ? tag.aliases.map((value) => <StatusBadge key={value}>{value}</StatusBadge>) : <span className="muted-text">None stored</span>}</div></td>
                      <td><StatusBadge tone={tag.status === "active" ? "healthy" : "warning"}>{tag.status}</StatusBadge></td>
                      <td><button className="reader-control reader-control--secondary" type="button" onClick={() => setSelectedKey(tag.canonical_key)}>Manage</button></td>
                    </tr>
                  ))}</tbody>
                </table>
              </DataTableShell>
            )}
          </Section>

          {selected ? <Section title={`Manage ${selected.label}`} description="Edits and aliases are revision-checked. Removing an alias or deprecating a tag never deletes or rewrites historical Paper tag values.">
            <form className="project-command-panel" onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              void run(() => apiClient.updateCanonicalTag(selected.canonical_key, {
                label: String(form.get("label") || ""),
                category: String(form.get("category") || ""),
                description: String(form.get("description") || ""),
                suggestionStrength: Number(form.get("strength") || 0),
              }, resource.data.governance.registry_revision), "Canonical tag metadata saved.");
            }}>
              <div className="project-form-grid">
                <label className="reader-field"><span>Label</span><input name="label" defaultValue={selected.label} required /></label>
                <label className="reader-field"><span>Category</span><select name="category" defaultValue={selected.category}>{CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
                <label className="reader-field"><span>Suggestion strength</span><input name="strength" type="number" min="0" max="100" defaultValue={selected.suggestion_strength} required /></label>
                <label className="reader-field project-form-wide"><span>Description</span><textarea name="description" defaultValue={selected.description} rows={2} maxLength={2000} /></label>
              </div>
              <div className="reader-editor__actions"><button className="reader-action" type="submit" disabled={busy}>Save metadata</button></div>
            </form>
            <div className="project-command-panel">
              <div className="reader-note__heading"><div><p className="eyebrow">Alias management</p><h3>Aliases</h3></div><StatusBadge>{selected.aliases.length}</StatusBadge></div>
              <div className="reader-editor__actions">{selected.aliases.map((value) => <button key={value} className="reader-control reader-control--secondary" type="button" disabled={busy} onClick={() => void run(() => apiClient.removeCanonicalTagAlias(selected.canonical_key, value, resource.data.governance.registry_revision), `Alias “${value}” removed from the registry only.`)}>Remove {value}</button>)}</div>
              <div className="project-link-form"><label className="reader-field"><span>New alias</span><input value={alias} onChange={(event) => setAlias(event.target.value)} maxLength={200} /></label><button className="reader-control" type="button" disabled={busy || !alias.trim()} onClick={() => void run(async () => { await apiClient.addCanonicalTagAlias(selected.canonical_key, alias, resource.data.governance.registry_revision); setAlias(""); }, "Alias saved. Existing Paper tags were not rewritten.")}>Add alias</button></div>
              {selected.status === "active" ? <button className="reader-control reader-control--danger" type="button" disabled={busy} onClick={() => { if (window.confirm(`Deprecate ${selected.label}? Historical Paper references will remain.`)) void run(() => apiClient.deprecateCanonicalTag(selected.canonical_key, resource.data.governance.registry_revision), "Canonical tag deprecated. Historical references remain visible."); }}>Deprecate canonical tag</button> : <p className="muted-text">This canonical tag is deprecated and remains available for historical inspection.</p>}
            </div>
          </Section> : null}
          {notice ? <p className="reader-editor__status">{notice}</p> : null}
        </>
      ) : null}
    </div>
  );
}

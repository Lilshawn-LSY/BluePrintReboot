"use client";

import { useEffect, useState } from "react";
import { DataTableShell } from "../components/DataTableShell";
import { EmptyState, ErrorState, LoadingState, UnavailableState } from "../components/AsyncStates";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { StatusBadge } from "../components/StatusBadge";
import { SaveStatus } from "../components/SaveStatus";
import { useApiResource } from "../hooks/useApiResource";
import { ApiClientError, apiClient } from "../lib/api/client";
import {
  applyLatestRevisionDraft,
  beginRevisionSave,
  completeRevisionSave,
  createRevisionDraftState,
  draftStorageKey,
  editRevisionDraft,
  failRevisionSave,
  keepMyRevisionDraft,
  persistRevisionDraft,
  readPersistentRevisionDraft,
  receiveRemoteRevision,
} from "../lib/drafts/revision-draft.mjs";
import type { RevisionDraftState } from "../lib/drafts/revision-draft.mjs";

const CATEGORIES = [
  "field", "organism", "method", "assay", "gene_or_protein", "cell_line_or_sample",
  "tissue_or_cell_type", "concept", "model_or_algorithm", "paper_type", "dataset", "other",
];

type CreateTagDraft = { label: string; category: string; description: string };
type TagEditDraft = { label: string; category: string; description: string; strength: number; aliasText: string };
type TagEditor = { target: string; state: RevisionDraftState<TagEditDraft> };

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

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
  const createDraftKey = draftStorageKey("canonical-tag-create", "new");
  const [createDraft, setCreateDraft] = useState(() => createRevisionDraftState<CreateTagDraft>({
    draft: { label: "", category: "other", description: "" },
    revision: "",
    record: readPersistentRevisionDraft(browserStorage(), draftStorageKey("canonical-tag-create", "new")),
  }));
  const [draftStorageReady, setDraftStorageReady] = useState(false);
  const [tagEditor, setTagEditor] = useState<TagEditor | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const selected = resource.status === "success"
    ? resource.data.governance.items.find((tag) => tag.canonical_key === selectedKey) ?? resource.data.governance.items[0]
    : undefined;
  const selectedEditor = tagEditor && tagEditor.target === selected?.canonical_key ? tagEditor.state : null;

  useEffect(() => {
    setCreateDraft(createRevisionDraftState<CreateTagDraft>({
      draft: { label: "", category: "other", description: "" },
      revision: "",
      record: readPersistentRevisionDraft(browserStorage(), createDraftKey),
    }));
    setDraftStorageReady(true);
  }, [createDraftKey]);

  useEffect(() => {
    if (!draftStorageReady) return;
    persistRevisionDraft(browserStorage(), createDraftKey, createDraft);
  }, [createDraft, createDraftKey, draftStorageReady]);

  const updateCreateDraft = (update: (state: typeof createDraft) => typeof createDraft) => {
    setCreateDraft((current) => {
      const next = update(current);
      if (draftStorageReady) persistRevisionDraft(browserStorage(), createDraftKey, next);
      return next;
    });
  };

  useEffect(() => {
    if (!selected) return;
    setTagEditor((current) => {
      if (current?.target === selected.canonical_key) return current;
      const key = draftStorageKey("canonical-tag-edit", selected.canonical_key);
      return {
        target: selected.canonical_key,
        state: createRevisionDraftState<TagEditDraft>({
          draft: {
            label: selected.label,
            category: selected.category,
            description: selected.description,
            strength: selected.suggestion_strength,
            aliasText: "",
          },
          revision: resource.status === "success" ? resource.data.governance.registry_revision : "",
          record: readPersistentRevisionDraft(browserStorage(), key),
        }),
      };
    });
  }, [resource, selected]);

  useEffect(() => {
    if (!tagEditor) return;
    if (!draftStorageReady) return;
    persistRevisionDraft(
      browserStorage(),
      draftStorageKey("canonical-tag-edit", tagEditor.target),
      tagEditor.state,
    );
  }, [draftStorageReady, tagEditor]);

  const updateTagEditor = (update: (state: RevisionDraftState<TagEditDraft>) => RevisionDraftState<TagEditDraft>) => {
    setTagEditor((current) => {
      if (!current) return current;
      const state = update(current.state);
      if (draftStorageReady) persistRevisionDraft(browserStorage(), draftStorageKey("canonical-tag-edit", current.target), state);
      return { ...current, state };
    });
  };

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

  const createCanonicalTag = async () => {
    if (resource.status !== "success" || busy) return;
    const started = beginRevisionSave({
      ...createDraft,
      revision: resource.data.governance.registry_revision,
      remoteRevision: resource.data.governance.registry_revision,
    });
    if (!started.request) return;
    const request = started.request;
    updateCreateDraft(() => started.state);
    setBusy(true);
    try {
      const response = await apiClient.createCanonicalTag({
        label: request.draft.label,
        category: request.draft.category,
        description: request.draft.description,
        suggestionStrength: 1,
        expectedRevision: request.revision,
      });
      updateCreateDraft((current) => {
        const saved = completeRevisionSave(current, request.token, {
          value: request.draft,
          revision: response.registry_revision,
        });
        if (saved.saveState !== "saved") return saved;
        return createRevisionDraftState({
          draft: { label: "", category: "other", description: "" },
          revision: response.registry_revision,
        });
      });
      setNotice("Canonical tag created. No Paper tags were changed.");
      resource.retry();
    } catch (error) {
      let latestRevision = "";
      if (error instanceof ApiClientError && error.kind === "conflict") {
        try {
          latestRevision = (await apiClient.getTagGovernance()).registry_revision;
        } catch { /* preserve the draft until the Tag Book is reachable */ }
      }
      updateCreateDraft((current) => {
        const failed = failRevisionSave(current, request.token, error instanceof ApiClientError ? error.kind : "error");
        return {
          ...failed,
          revision: latestRevision || failed.revision,
          remoteRevision: latestRevision || failed.remoteRevision,
          lastError: failed.saveState === "changed_elsewhere"
            ? "The Tag Book changed elsewhere. Your new-tag draft is preserved; refresh it before retrying."
            : error instanceof ApiClientError ? error.message : "The canonical Tag Book command could not be completed.",
        };
      });
    } finally {
      setBusy(false);
    }
  };

  const saveCanonicalTagMetadata = async () => {
    if (!selected || !tagEditor || tagEditor.target !== selected.canonical_key || resource.status !== "success" || busy) return;
    const started = beginRevisionSave({
      ...tagEditor.state,
      revision: resource.data.governance.registry_revision,
      remoteRevision: resource.data.governance.registry_revision,
    });
    if (!started.request) return;
    const request = started.request;
    updateTagEditor(() => started.state);
    setBusy(true);
    try {
      const response = await apiClient.updateCanonicalTag(selected.canonical_key, {
        label: request.draft.label,
        category: request.draft.category,
        description: request.draft.description,
        suggestionStrength: request.draft.strength,
      }, request.revision);
      updateTagEditor((current) => completeRevisionSave(current, request.token, {
        value: {
          label: response.tag.label,
          category: response.tag.category,
          description: response.tag.description,
          strength: response.tag.suggestion_strength,
          aliasText: request.draft.aliasText,
        },
        revision: response.registry_revision,
      }));
      setNotice("Canonical tag metadata saved.");
      resource.retry();
    } catch (error) {
      let remote: { value: TagEditDraft; revision: string } | null = null;
      if (error instanceof ApiClientError && error.kind === "conflict") {
        try {
          const latest = await apiClient.getTagGovernance();
          const tag = latest.items.find((item) => item.canonical_key === selected.canonical_key);
          if (tag) remote = {
            value: { label: tag.label, category: tag.category, description: tag.description, strength: tag.suggestion_strength, aliasText: tagEditor.state.draft.aliasText },
            revision: latest.registry_revision,
          };
        } catch { /* retain local metadata until the registry is reachable */ }
      }
      updateTagEditor((current) => {
        let failed = failRevisionSave(current, request.token, error instanceof ApiClientError ? error.kind : "error");
        if (remote) failed = receiveRemoteRevision(failed, { ...remote, changedElsewhere: true });
        return { ...failed, lastError: failed.saveState === "changed_elsewhere" ? "This canonical tag changed elsewhere. Your draft and latest saved value are both preserved." : error instanceof ApiClientError ? error.message : "Save failed. Your draft is preserved locally." };
      });
    } finally {
      setBusy(false);
    }
  };

  const addCanonicalAlias = async () => {
    if (!selected || !tagEditor || tagEditor.target !== selected.canonical_key || resource.status !== "success" || busy || !tagEditor.state.draft.aliasText.trim()) return;
    const started = beginRevisionSave({
      ...tagEditor.state,
      revision: resource.data.governance.registry_revision,
      remoteRevision: resource.data.governance.registry_revision,
    });
    if (!started.request) return;
    const request = started.request;
    updateTagEditor(() => started.state);
    setBusy(true);
    try {
      const response = await apiClient.addCanonicalTagAlias(selected.canonical_key, request.draft.aliasText, request.revision);
      updateTagEditor((current) => completeRevisionSave(current, request.token, {
        value: {
          label: response.tag.label,
          category: response.tag.category,
          description: response.tag.description,
          strength: response.tag.suggestion_strength,
          aliasText: "",
        },
        revision: response.registry_revision,
      }));
      setNotice("Alias saved. Existing Paper tags were not rewritten.");
      resource.retry();
    } catch (error) {
      let remote: { value: TagEditDraft; revision: string } | null = null;
      if (error instanceof ApiClientError && error.kind === "conflict") {
        try {
          const latest = await apiClient.getTagGovernance();
          const tag = latest.items.find((item) => item.canonical_key === selected.canonical_key);
          if (tag) remote = {
            value: { label: tag.label, category: tag.category, description: tag.description, strength: tag.suggestion_strength, aliasText: "" },
            revision: latest.registry_revision,
          };
        } catch { /* retain the alias draft until the registry is reachable */ }
      }
      updateTagEditor((current) => {
        let failed = failRevisionSave(current, request.token, error instanceof ApiClientError ? error.kind : "error");
        if (remote) failed = receiveRemoteRevision(failed, { ...remote, changedElsewhere: true });
        return {
          ...failed,
          lastError: failed.saveState === "changed_elsewhere"
            ? "This canonical tag changed elsewhere. Your alias draft and latest saved value are both preserved."
            : error instanceof ApiClientError ? error.message : "Save failed. Your alias draft is preserved locally.",
        };
      });
    } finally {
      setBusy(false);
    }
  };

  const refreshCreateDraftAfterConflict = async () => {
    try {
      const latest = await apiClient.getTagGovernance();
      updateCreateDraft((current) => ({
        ...current,
        revision: latest.registry_revision,
        remoteRevision: latest.registry_revision,
        saveState: "unsaved",
        lastError: "",
      }));
      resource.retry();
    } catch (error) {
      updateCreateDraft((current) => ({
        ...current,
        lastError: error instanceof ApiClientError ? error.message : "The Tag Book is unavailable. Your draft remains preserved locally.",
      }));
    }
  };

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
              void createCanonicalTag();
            }}>
              <div className="project-form-grid">
                <label className="reader-field"><span>Label</span><input value={createDraft.draft.label} onChange={(event) => updateCreateDraft((current) => editRevisionDraft(current, { ...current.draft, label: event.target.value }))} required maxLength={200} /></label>
                <label className="reader-field"><span>Category</span><select value={createDraft.draft.category} onChange={(event) => updateCreateDraft((current) => editRevisionDraft(current, { ...current.draft, category: event.target.value }))}>{CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
                <label className="reader-field project-form-wide"><span>Description (optional)</span><textarea value={createDraft.draft.description} onChange={(event) => updateCreateDraft((current) => editRevisionDraft(current, { ...current.draft, description: event.target.value }))} maxLength={2000} rows={2} /></label>
              </div>
              <div className="reader-editor__actions"><SaveStatus state={createDraft.saveState} /><button className="reader-action" type="submit" disabled={busy || Boolean(createDraft.activeSave) || !createDraft.draft.label.trim()}>Create canonical tag</button></div>
              {createDraft.lastError ? <p className="reader-editor__status" role="status">{createDraft.lastError} Your draft remains preserved locally.</p> : null}
              {createDraft.saveState === "changed_elsewhere" ? <div className="reader-editor__actions"><button className="reader-control reader-control--secondary" type="button" onClick={() => void refreshCreateDraftAfterConflict()}>Refresh Tag Book and keep my draft</button></div> : null}
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
                      <td><button className="reader-control reader-control--secondary" type="button" disabled={busy || Boolean(tagEditor?.state.activeSave)} onClick={() => setSelectedKey(tag.canonical_key)}>Manage</button></td>
                    </tr>
                  ))}</tbody>
                </table>
              </DataTableShell>
            )}
          </Section>

          {selected ? <Section title={`Manage ${selected.label}`} description="Edits and aliases are revision-checked. Removing an alias or deprecating a tag never deletes or rewrites historical Paper tag values.">
            {!selectedEditor ? <p className="muted-text">Loading the locally preserved tag draft…</p> : <>
              <form className="project-command-panel" onSubmit={(event) => {
                event.preventDefault();
                void saveCanonicalTagMetadata();
              }}>
                <div className="project-form-grid">
                  <label className="reader-field"><span>Label</span><input value={selectedEditor.draft.label} onChange={(event) => updateTagEditor((current) => editRevisionDraft(current, { ...current.draft, label: event.target.value }))} required maxLength={200} /></label>
                  <label className="reader-field"><span>Category</span><select value={selectedEditor.draft.category} onChange={(event) => updateTagEditor((current) => editRevisionDraft(current, { ...current.draft, category: event.target.value }))}>{CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
                  <label className="reader-field"><span>Suggestion strength</span><input value={selectedEditor.draft.strength} onChange={(event) => updateTagEditor((current) => editRevisionDraft(current, { ...current.draft, strength: Number(event.target.value) }))} type="number" min="0" max="100" required /></label>
                  <label className="reader-field project-form-wide"><span>Description</span><textarea value={selectedEditor.draft.description} onChange={(event) => updateTagEditor((current) => editRevisionDraft(current, { ...current.draft, description: event.target.value }))} rows={2} maxLength={2000} /></label>
                </div>
                <div className="reader-editor__actions"><SaveStatus state={selectedEditor.saveState} /><button className="reader-action" type="submit" disabled={busy || Boolean(selectedEditor.activeSave) || selectedEditor.saveState === "changed_elsewhere" || !selectedEditor.draft.label.trim()}>Save metadata</button></div>
                {selectedEditor.lastError ? <p className="reader-editor__status" role="status">{selectedEditor.lastError}</p> : null}
                {selectedEditor.saveState === "changed_elsewhere" ? <div className="reader-editor__actions">
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => updateTagEditor(keepMyRevisionDraft)}>Keep my draft</button>
                  <button className="reader-control reader-control--secondary" type="button" onClick={() => updateTagEditor(applyLatestRevisionDraft)}>Use latest server value</button>
                </div> : null}
                {selectedEditor.saveState === "changed_elsewhere" ? <details className="reader-conflict-review"><summary>Review local and latest server values</summary><p><strong>My draft:</strong> {selectedEditor.draft.label} · {selectedEditor.draft.category}</p><p><strong>Latest server value:</strong> {selectedEditor.remote.label} · {selectedEditor.remote.category}</p></details> : null}
              </form>
              <div className="project-command-panel">
                <div className="reader-note__heading"><div><p className="eyebrow">Alias management</p><h3>Aliases</h3></div><StatusBadge>{selected.aliases.length}</StatusBadge></div>
                <div className="reader-editor__actions">{selected.aliases.map((value) => <button key={value} className="reader-control reader-control--secondary" type="button" disabled={busy} onClick={() => void run(() => apiClient.removeCanonicalTagAlias(selected.canonical_key, value, resource.data.governance.registry_revision), `Alias “${value}” removed from the registry only.`)}>Remove {value}</button>)}</div>
                <div className="project-link-form"><label className="reader-field"><span>New alias</span><input value={selectedEditor.draft.aliasText} onChange={(event) => updateTagEditor((current) => editRevisionDraft(current, { ...current.draft, aliasText: event.target.value }))} maxLength={200} /></label><button className="reader-control" type="button" disabled={busy || Boolean(selectedEditor.activeSave) || selectedEditor.saveState === "changed_elsewhere" || !selectedEditor.draft.aliasText.trim()} onClick={() => void addCanonicalAlias()}>Add alias</button></div>
                {selected.status === "active" ? <button className="reader-control reader-control--danger" type="button" disabled={busy} onClick={() => { if (window.confirm(`Deprecate ${selected.label}? Historical Paper references will remain.`)) void run(() => apiClient.deprecateCanonicalTag(selected.canonical_key, resource.data.governance.registry_revision), "Canonical tag deprecated. Historical references remain visible."); }}>Deprecate canonical tag</button> : <p className="muted-text">This canonical tag is deprecated and remains available for historical inspection.</p>}
              </div>
            </>}
          </Section> : null}
          {notice ? <p className="reader-editor__status">{notice}</p> : null}
        </>
      ) : null}
    </div>
  );
}

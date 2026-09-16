"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { apiFetch, InvestigationDocument } from "@/lib/api";

const allowedTypes = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "image/jpeg",
  "image/png",
  "image/tiff",
];

const readableSize = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(bytes < 1024 * 1024 ? 2 : 1)} MB`;

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<InvestigationDocument[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("Loading authorized documents…");
  const [submitting, setSubmitting] = useState(false);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [retrying, setRetrying] = useState<string | null>(null);
  const requestId = useRef(0);

  const loadDocuments = useCallback(async () => {
    const id = ++requestId.current;
    try {
      const response = await apiFetch(`/documents${query ? `?query=${encodeURIComponent(query)}` : ""}`);
      if (id !== requestId.current) return;
      if (!response.ok) { setMessage("Documents are currently unavailable."); return; }
      const records: InvestigationDocument[] = await response.json();
      if (id !== requestId.current) return;
      setDocuments(records);
      setMessage(records.length ? "" : query ? "No matching documents." : "No documents have been submitted in your workspace.");
    } catch {
      if (id === requestId.current) setMessage("Could not reach the document service. Try refreshing shortly.");
    }
  }, [query]);

  useEffect(() => {
    void loadDocuments();
    const timer = setInterval(() => { void loadDocuments(); }, 5000);
    return () => { clearInterval(timer); requestId.current++; };
  }, [loadDocuments]);

  async function retry(documentId: string) {
    setRetrying(documentId);
    try {
      const response = await apiFetch(`/documents/${documentId}/retry`, { method: "POST" });
      if (!response.ok) { setMessage("Retry was not accepted. Refresh and try again."); return; }
      await loadDocuments();
    } catch {
      setMessage("Could not confirm the retry. Refresh status before trying again.");
    } finally { setRetrying(null); }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    if (!selected) { setFile(null); return; }
    if (!allowedTypes.includes(selected.type) || selected.size > 25 * 1024 * 1024) {
      setFile(null);
      setMessage("Choose a PDF, DOCX, JPEG, PNG, or TIFF up to 25 MB.");
      return;
    }
    setFile(selected);
    setMessage("");
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) { setMessage("Choose a document before starting the protected intake."); return; }
    setSubmitting(true);
    setMessage("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await apiFetch("/documents", { method: "POST", body: formData });
      if (!response.ok) {
        const payload: { detail?: string } = await response.json().catch(() => ({}));
        setMessage(payload.detail ?? "The document could not be submitted.");
      } else {
        const document: InvestigationDocument = await response.json();
        setDocuments((current) => [document, ...current]);
        setFile(null);
        setMessage("Document accepted into protected processing. Status updates after scanning and extraction.");
        form.reset();
        setQuery("");
        setSearch("");
      }
    } catch {
      setMessage("Could not confirm the upload. Refresh the list before trying again.");
    } finally {
      setSubmitting(false);
    }
  }

  return <section className="dashboard documents-page" aria-labelledby="documents-title">
    <header className="workspace-header"><div><p className="eyebrow">Evidence intake</p><h1 id="documents-title">Documents</h1><p>Files are quarantined, malware-scanned, extracted, and indexed before they become searchable in your workspace.</p></div><span className="secure-pill"><i /> Private intake</span></header>
    <div className="document-grid">
      <form className="upload-panel" onSubmit={upload}>
        <p className="card-kicker">Protected upload</p><h2>Submit source material</h2><p>PDF, DOCX, JPEG, PNG, or TIFF. Maximum 25 MB. The original file stays private while the processing worker verifies it.</p>
        <label className="file-field"><span>Document file</span><input type="file" accept=".pdf,.docx,.jpg,.jpeg,.png,.tif,.tiff,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png,image/tiff" onChange={selectFile} /><strong>{file ? `${file.name} · ${readableSize(file.size)}` : "No file selected"}</strong></label>
        <button className="button" disabled={submitting}>{submitting ? "Submitting…" : "Start protected intake"}</button>
      </form>
      <aside className="ingestion-rail" aria-label="Document processing stages"><p className="card-kicker">Processing path</p><ol><li>Quarantine storage</li><li>Malware scan</li><li>Text or OCR extraction</li><li>Metadata and search index</li></ol><p>Failed scans never promote a file to the searchable store.</p></aside>
    </div>
    <section className="documents-list" aria-labelledby="document-list-title">
      <div className="section-title"><div><p className="card-kicker">Your submitted records</p><h2 id="document-list-title">Ingestion queue</h2></div><button className="text-button refresh-documents" onClick={loadDocuments}>Refresh status</button></div>
      <form className="document-search" onSubmit={(event) => {
        event.preventDefault();
        if (search.trim().length === 1) { setMessage("Enter at least two characters to search."); return; }
        setQuery(search.trim());
      }}>
        <label htmlFor="document-query">Search extracted text</label>
        <input id="document-query" type="search" value={search} maxLength={200} onChange={(event) => setSearch(event.target.value)} />
        <button className="button" type="submit">Search</button>
        <button className="text-button" type="button" onClick={() => { setSearch(""); setQuery(""); }}>Clear search</button>
      </form>
      {message && <p className="empty-message" role="status">{message}</p>}
      {documents.map((document) => <article className="document-row" key={document.id}>
        <div><strong>{document.original_filename}</strong><small>{document.content_type} · {readableSize(document.byte_size)} · {new Date(document.created_at).toLocaleString()}</small></div>
        <span className={`document-status ${document.status}`} role="status">{document.status}</span>
        <div className="entity-summary">{document.status === "ready" ? `${document.entities.length} searchable entities` : document.failure_reason ?? "Awaiting protected processing"}
          {document.status === "failed" && <button className="text-button" disabled={retrying !== null} onClick={() => retry(document.id)} aria-label={`Retry ${document.original_filename}`}>{retrying === document.id ? "Retrying…" : "Retry processing"}</button>}
        </div>
      </article>)}
    </section>
  </section>;
}

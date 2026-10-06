import { useEffect, useState } from "react";
import { api, IngestResult } from "../../api/client";
import { FileDropzone, PipelineSteps, INGEST_STEPS, ErrorBox, useToast, Card } from "..";
import { useApp } from "../../context/AppContext";
import { FileText } from "lucide-react";

/** Dropzone + animated ingest pipeline. Calls onDone with the ingest result. */
export function DocumentUploader({ compact, onDone }: { compact?: boolean; onDone?: (r: IngestResult) => void }) {
  const { apiKey, setDoc } = useApp();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!busy) return;
    setStep(0);
    const t = setInterval(() => setStep((s) => Math.min(s + 1, INGEST_STEPS.length - 1)), 1100);
    return () => clearInterval(t);
  }, [busy]);

  const upload = async (f: File) => {
    setFile(f);
    setError(null);
    setBusy(true);
    try {
      const r = await api.ingest(f, apiKey || undefined);
      setStep(INGEST_STEPS.length);
      setDoc(r);
      toast("success", r.from_cache ? "Loaded from cache" : "Document embedded", `${r.filename} - ${r.n_chunks} chunks in ${Math.round(r.duration_ms)} ms`);
      onDone?.(r);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast("error", "Upload failed", msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      {busy ? (
        <Card glow>
          <div className="row" style={{ marginBottom: 8 }}>
            <FileText size={18} style={{ color: "var(--cyan)" }} />
            <b>{file?.name}</b>
            <span className="faint small">{file ? `${(file.size / 1024).toFixed(1)} KB` : ""}</span>
          </div>
          <PipelineSteps steps={INGEST_STEPS} current={step} />
          <div className="faint small" style={{ textAlign: "center" }}>First-time embedding can take 10-30 seconds. Re-uploads are instant (hash cache).</div>
        </Card>
      ) : (
        <FileDropzone compact={compact} onFile={upload} />
      )}
      {error && <ErrorBox error={error} onRetry={file ? () => upload(file) : undefined} />}
    </div>
  );
}

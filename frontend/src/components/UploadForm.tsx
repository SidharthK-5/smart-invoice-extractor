import { useRef, useState } from "react";
import { UploadCloud, X, FileText, Image as ImageIcon, Sparkles } from "lucide-react";

interface Props {
  onSubmit: (files: File[]) => Promise<void> | void;
  busy: boolean;
  status: string;
}

const ACCEPT = "application/pdf,image/png,image/jpeg";
const ACCEPTED_EXT = /\.(pdf|png|jpe?g)$/i;

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function fileIcon(f: File) {
  if (f.type === "application/pdf" || /\.pdf$/i.test(f.name)) {
    return <FileText size={16} />;
  }
  return <ImageIcon size={16} />;
}

export default function UploadForm({ onSubmit, busy, status }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(incoming: FileList | File[]) {
    const accepted = Array.from(incoming).filter((f) => ACCEPTED_EXT.test(f.name));
    // Dedupe by name+size so re-adding the same file doesn't create duplicates.
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const merged = [...prev];
      for (const f of accepted) {
        const key = `${f.name}:${f.size}`;
        if (!seen.has(key)) {
          merged.push(f);
          seen.add(key);
        }
      }
      return merged;
    });
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) addFiles(e.target.files);
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!files.length) return;
    await onSubmit(files);
  }

  function handleClear() {
    setFiles([]);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div
        className={`dropzone${isDragging ? " dropzone--active" : ""}${busy ? " dropzone--disabled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !busy && inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <UploadCloud size={28} className="dropzone__icon" />
        <div className="dropzone__title">
          Drop invoices here, or <span className="dropzone__link">browse</span>
        </div>
        <div className="dropzone__subtitle">PDF, PNG, or JPG · up to 10 MB each</div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          onChange={handleInputChange}
          disabled={busy}
          style={{ display: "none" }}
        />
      </div>

      {files.length > 0 && (
        <ul className="file-chips">
          {files.map((f, i) => (
            <li key={`${f.name}-${f.size}-${i}`} className="file-chip">
              <span className="file-chip__icon">{fileIcon(f)}</span>
              <span className="file-chip__name" title={f.name}>{f.name}</span>
              <span className="file-chip__size">{formatBytes(f.size)}</span>
              {!busy && (
                <button
                  type="button"
                  className="file-chip__remove"
                  onClick={() => removeFile(i)}
                  aria-label={`Remove ${f.name}`}
                >
                  <X size={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {busy && (
        <div className="progress" role="progressbar" aria-label="Processing invoices">
          <div className="progress__bar" />
          <div className="progress__label">{status || "Processing…"}</div>
        </div>
      )}

      <div className="actions">
        <button type="submit" className="btn" disabled={busy || files.length === 0}>
          <Sparkles size={16} style={{ marginRight: 6 }} />
          {busy ? "Processing…" : "Extract Data"}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={handleClear}
          disabled={busy || files.length === 0}
        >
          Clear
        </button>
        {!busy && status && <span className="status">{status}</span>}
      </div>
    </form>
  );
}

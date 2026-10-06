import { useRef, useState, DragEvent } from "react";
import { UploadCloud, FileText } from "lucide-react";

export const FILE_TYPES = [".pdf", ".docx", ".txt", ".md", ".html", ".csv"];

export function FileDropzone({ onFile, disabled, compact }: { onFile: (f: File) => void; disabled?: boolean; compact?: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f && !disabled) onFile(f);
  };

  return (
    <div
      className={`dropzone ${over ? "over" : ""}`}
      style={compact ? { padding: "20px 16px" } : undefined}
      onClick={() => !disabled && ref.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && ref.current?.click()}
    >
      <input
        ref={ref}
        type="file"
        hidden
        accept={FILE_TYPES.join(",")}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      {!compact && <div className="dz-icon">{over ? <FileText size={30} /> : <UploadCloud size={30} />}</div>}
      <h3>{over ? "Drop it right here" : compact ? "Upload a different document" : "Drag and drop a document"}</h3>
      <p className="muted small" style={{ margin: 0 }}>
        or <span className="gradient-text" style={{ fontWeight: 700 }}>browse your files</span> - any text-bearing document works
      </p>
      <div className="filetypes">
        {FILE_TYPES.map((t) => (
          <span className="ftype" key={t}>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

import { ReactNode } from "react";
import { ChevronRight } from "lucide-react";

export function Collapse({ title, children, open }: { title: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details className="collapse" open={open}>
      <summary>
        <ChevronRight size={16} className="chev" />
        {title}
      </summary>
      <div className="cbody">{children}</div>
    </details>
  );
}

export function Json({ data }: { data: unknown }) {
  return <pre className="json">{typeof data === "string" ? data : JSON.stringify(data, null, 2)}</pre>;
}

import { ReactNode } from "react";
import { cell } from "../lib/format";

export function DataTable({ rows, columns, render, empty = "No rows." }: {
  rows: Record<string, any>[];
  columns?: string[];
  render?: Record<string, (v: any, row: Record<string, any>) => ReactNode>;
  empty?: string;
}) {
  if (!rows.length) return <div className="faint small" style={{ padding: 8 }}>{empty}</div>;
  const cols = columns ?? Object.keys(rows[0]);
  return (
    <div className="table-wrap">
      <table className="tbl">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c.replace(/_/g, " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c} title={typeof r[c] === "string" ? r[c] : undefined}>
                  {render?.[c] ? render[c](r[c], r) : cell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import type { AnomalyItem } from '../types';

const SEVERITY_COLORS: Record<string, string> = {
  HIGH: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300',
  MEDIUM: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300',
  LOW: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
};

export default function AnomalyList({ anomalies }: { anomalies: AnomalyItem[] }) {
  if (!anomalies.length) {
    return <p className="text-sm text-zinc-500">No anomalies detected this period.</p>;
  }
  return (
    <ul className="space-y-3">
      {anomalies.map((a, i) => (
        <li
          key={i}
          className="flex items-start gap-3 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4"
        >
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${SEVERITY_COLORS[a.severity]}`}>
            {a.severity}
          </span>
          <div>
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{a.category}</p>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{a.reason}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

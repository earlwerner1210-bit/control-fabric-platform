import { format } from "date-fns";
import type { AuditEvent } from "@/lib/types";
import { Clock } from "lucide-react";

interface AuditTimelineProps {
  events: AuditEvent[];
}

export default function AuditTimeline({ events }: AuditTimelineProps) {
  if (events.length === 0) {
    return <p className="py-8 text-center text-sm text-neutral-400">No audit events recorded.</p>;
  }

  return (
    <div className="flow-root">
      <ul className="-mb-8">
        {events.map((event, idx) => (
          <li key={event.id}>
            <div className="relative pb-8">
              {idx < events.length - 1 && (
                <span
                  className="absolute left-4 top-8 -ml-px h-full w-0.5 bg-neutral-200"
                  aria-hidden="true"
                />
              )}
              <div className="relative flex items-start space-x-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-neutral-100 ring-4 ring-white">
                  <Clock className="h-4 w-4 text-neutral-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-neutral-900">
                      {event.action}
                    </p>
                    <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-500">
                      {event.event_type}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-neutral-500">
                    {event.resource_type} / {event.resource_id.slice(0, 8)}
                    {event.actor_id && <> by {event.actor_id.slice(0, 8)}</>}
                  </p>
                  <p className="mt-0.5 text-xs text-neutral-400">
                    {format(new Date(event.created_at), "MMM d, yyyy HH:mm:ss")}
                  </p>
                  {Object.keys(event.detail).length > 0 && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-neutral-400 hover:text-neutral-600">
                        Details
                      </summary>
                      <pre className="mt-1 rounded bg-neutral-50 p-2 text-xs text-neutral-600 overflow-x-auto">
                        {JSON.stringify(event.detail, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

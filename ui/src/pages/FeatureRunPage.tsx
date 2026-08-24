import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, TimelineEntry } from "../api/client";
import { useEventStream } from "../hooks/useEventStream";

export default function FeatureRunPage() {
  const { projectId, featureId } = useParams<{
    projectId: string;
    featureId: string;
  }>();
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const events = useEventStream(projectId ?? "");

  useEffect(() => {
    if (!projectId || !featureId) return;
    api
      .timeline(projectId, featureId)
      .then(setTimeline)
      .catch((e: Error) => setError(e.message));
  }, [projectId, featureId]);

  if (error) return <p className="error">{error}</p>;

  return (
    <>
      <p>
        <Link to={`/projects/${projectId}`}>← {projectId}</Link>
      </p>
      <h2>{featureId} — state machine timeline</h2>
      <table>
        <thead>
          <tr>
            <th>Transition</th>
            <th>Agent</th>
            <th>Skill</th>
            <th>Retry</th>
            <th>Human</th>
            <th>Duration</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {timeline.map((entry, index) => (
            <tr key={index}>
              <td>
                {entry.from_state} → <strong>{entry.to_state}</strong>
              </td>
              <td>{entry.agent}</td>
              <td className="muted">{entry.skill ?? "—"}</td>
              <td>{entry.retry_number}</td>
              <td>{entry.human_intervention ? "yes" : "no"}</td>
              <td>
                {entry.duration_seconds !== null
                  ? `${entry.duration_seconds.toFixed(2)}s`
                  : "—"}
              </td>
              <td className="muted">{entry.timestamp}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Live event stream</h2>
      <div className="log">
        {events.length === 0 && <span className="muted">Waiting for events…</span>}
        {events
          .filter((event) => !featureId || event.feature_id === featureId)
          .map((event) => (
            <div key={event.event_id}>
              [{event.timestamp}] {event.event_type} stage={event.stage ?? "—"}{" "}
              agent={event.agent ?? "—"} status={event.status ?? "—"}
            </div>
          ))}
      </div>
    </>
  );
}

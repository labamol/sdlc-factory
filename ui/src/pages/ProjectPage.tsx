import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, HealingView, ProjectOverview, QualityView } from "../api/client";

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [quality, setQuality] = useState<QualityView | null>(null);
  const [healing, setHealing] = useState<HealingView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    Promise.all([
      api.overview(projectId),
      api.quality(projectId),
      api.healing(projectId),
    ])
      .then(([o, q, h]) => {
        setOverview(o);
        setQuality(q);
        setHealing(h);
      })
      .catch((e: Error) => setError(e.message));
  }, [projectId]);

  if (error) return <p className="error">{error}</p>;
  if (!overview || !projectId) return <p className="muted">Loading…</p>;

  return (
    <>
      <h2>
        {projectId} <span className="muted">— {overview.executions} executions,</span>{" "}
        <span className={overview.failed_executions > 0 ? "error" : "muted"}>
          {overview.failed_executions} failed
        </span>
      </h2>
      <table>
        <thead>
          <tr>
            <th>Feature</th>
            <th>State</th>
            <th>PR</th>
            <th>Coverage</th>
            <th>Unit</th>
            <th>Functional</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {overview.features.map((feature) => (
            <tr key={feature.feature_id}>
              <td>
                <Link
                  to={`/projects/${projectId}/features/${feature.feature_id}`}
                >
                  {feature.feature_id}
                </Link>{" "}
                <span className="muted">{feature.title}</span>
              </td>
              <td>
                <span className="badge">{feature.current_state}</span>
              </td>
              <td>{feature.pull_request ?? "—"}</td>
              <td>{feature.coverage !== null ? `${feature.coverage}%` : "—"}</td>
              <td>{feature.unit_test_status}</td>
              <td>{feature.functional_test_status}</td>
              <td>{feature.evidence_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Quality gate</h2>
      {quality?.merge_decision ? (
        <>
          <p>
            Decision:{" "}
            <span
              className={`badge ${
                quality.merge_decision.decision === "PASS" ? "pass" : "fail"
              }`}
            >
              {quality.merge_decision.decision}
            </span>
          </p>
          <table>
            <thead>
              <tr>
                <th>Check</th>
                <th>Threshold</th>
                <th>Actual</th>
                <th>Result</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {quality.merge_decision.checks.map((check) => (
                <tr key={check.name}>
                  <td>{check.name}</td>
                  <td>{check.threshold}</td>
                  <td>{check.actual}</td>
                  <td>
                    <span className={`badge ${check.passed ? "pass" : "fail"}`}>
                      {check.passed ? "PASS" : "FAIL"}
                    </span>
                  </td>
                  <td className="muted">{check.evidence_ref}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="muted">No merge decision recorded yet.</p>
      )}

      <h2>Acceptance criteria</h2>
      {quality?.validation_report ? (
        <table>
          <thead>
            <tr>
              <th>AC</th>
              <th>Story</th>
              <th>Mandatory</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {quality.validation_report.results.map((result) => (
              <tr key={result.ac_id}>
                <td>{result.ac_id}</td>
                <td className="muted">{result.story_id}</td>
                <td>{result.mandatory ? "yes" : "no"}</td>
                <td>
                  <span className={`badge ${result.passed ? "pass" : "fail"}`}>
                    {result.test_outcome}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">No AC validation report yet.</p>
      )}

      <h2>Self-healing episodes</h2>
      {healing && healing.episodes.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Episode</th>
              <th>Stage</th>
              <th>Failure class</th>
              <th>Repair</th>
              <th>Attempt</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {healing.episodes.map((episode) => (
              <tr key={episode.episode_id}>
                <td>{episode.episode_id}</td>
                <td className="muted">{episode.stage}</td>
                <td>{episode.failure_class}</td>
                <td className="muted">{episode.repair_action}</td>
                <td>{episode.attempt}</td>
                <td>
                  <span
                    className={`badge ${
                      episode.outcome === "REPAIRED" ? "pass" : "fail"
                    }`}
                  >
                    {episode.outcome}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">No self-healing episodes recorded.</p>
      )}
    </>
  );
}

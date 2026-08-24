import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, EngineeringMetrics, ProjectSummary } from "../api/client";

function kpi(value: number | null): string {
  return value === null ? "n/a" : `${value}%`;
}

export default function OverviewPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [metrics, setMetrics] = useState<EngineeringMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.projects(), api.metrics()])
      .then(([p, m]) => {
        setProjects(p);
        setMetrics(m);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;

  return (
    <>
      <h2>Engineering KPIs</h2>
      {metrics && (
        <div className="cards">
          <div className="card">
            <div className="label">Autonomous completion</div>
            <div className="value">{kpi(metrics.autonomous_completion_pct)}</div>
          </div>
          <div className="card">
            <div className="label">AC-to-test coverage</div>
            <div className="value">{kpi(metrics.ac_to_test_coverage_pct)}</div>
          </div>
          <div className="card">
            <div className="label">PR first-pass</div>
            <div className="value">{kpi(metrics.pr_first_pass_pct)}</div>
          </div>
          <div className="card">
            <div className="label">Self-heal success</div>
            <div className="value">{kpi(metrics.self_heal_success_pct)}</div>
          </div>
          <div className="card">
            <div className="label">Features completed</div>
            <div className="value">
              {metrics.features_completed}/{metrics.features_total}
            </div>
          </div>
          <div className="card">
            <div className="label">Human interventions</div>
            <div className="value">{metrics.human_interventions}</div>
          </div>
        </div>
      )}
      <h2>Projects</h2>
      <table>
        <thead>
          <tr>
            <th>Project</th>
            <th>Features</th>
            <th>States</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.project_id}>
              <td>
                <Link to={`/projects/${project.project_id}`}>
                  {project.project_id}
                </Link>
              </td>
              <td>{project.features}</td>
              <td className="muted">{project.states.join(", ")}</td>
            </tr>
          ))}
          {projects.length === 0 && (
            <tr>
              <td colSpan={3} className="muted">
                No projects found under this base directory.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  );
}

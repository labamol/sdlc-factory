import { NavLink, Route, Routes } from "react-router-dom";
import OverviewPage from "../pages/OverviewPage";
import ProjectPage from "../pages/ProjectPage";
import FeatureRunPage from "../pages/FeatureRunPage";

export default function App() {
  return (
    <div className="layout">
      <div className="topbar">
        <h1>SDLC Factory</h1>
        <NavLink to="/" end>
          Overview
        </NavLink>
      </div>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/projects/:projectId" element={<ProjectPage />} />
        <Route
          path="/projects/:projectId/features/:featureId"
          element={<FeatureRunPage />}
        />
      </Routes>
    </div>
  );
}

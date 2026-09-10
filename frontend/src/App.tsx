import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./state/auth";
import { WorkspaceProvider } from "./state/workspace";
import Landing from "./pages/Landing";
import SignIn from "./pages/SignIn";
import Projects from "./pages/Projects";
import NewProject from "./pages/NewProject";
import ProjectLayout from "./pages/ProjectLayout";
import ThisWeek from "./pages/ThisWeek";
import Interview from "./pages/Interview";
import Analysis from "./pages/Analysis";
import Rubric from "./pages/Rubric";
import Novelty from "./pages/Novelty";
import Refine from "./pages/Refine";
import Plan from "./pages/Plan";
import TimelinePage from "./pages/Timeline";
import Poster from "./pages/Poster";
import JudgePrep from "./pages/JudgePrep";
import Notebook from "./pages/Notebook";
import WorkspaceLayout from "./pages/WorkspaceLayout";
import WorkspaceDashboard from "./pages/WorkspaceDashboard";
import WorkspaceProjects from "./pages/WorkspaceProjects";
import WorkspaceProjectDetail from "./pages/WorkspaceProjectDetail";
import WorkspaceMembers from "./pages/WorkspaceMembers";
import WorkspaceActivity from "./pages/WorkspaceActivity";
import WorkspaceSettings from "./pages/WorkspaceSettings";
import WorkspaceNew from "./pages/WorkspaceNew";
import WorkspaceJoin from "./pages/WorkspaceJoin";
import WorkspaceTeams from "./pages/WorkspaceTeams";
import TeamDashboard from "./pages/TeamDashboard";
import ResearchLibrary, { GuideDetailPage } from "./pages/ResearchLibrary";
import WinningProjects, { WinningProjectDetail } from "./pages/WinningProjects";
import ResearchOutreach from "./pages/ResearchOutreach";
import ResearchAssistant from "./pages/ResearchAssistant";

/** Signed-out visitors get the marketing site; everything else requires auth. */
function PublicApp() {
  const location = useLocation();
  if (location.pathname === "/sign-in") return <SignIn />;
  if (location.pathname === "/") return <Landing />;
  // Any other path while signed out: send through the landing page rather
  // than silently failing on a route that assumes a logged-in user.
  return <Navigate to="/" replace />;
}

export default function App() {
  const { user, ready } = useAuth();

  if (!ready)
    return (
      <div className="main">
        <p className="muted">Starting up…</p>
      </div>
    );

  if (!user) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/sign-in" element={<SignIn />} />
        <Route path="*" element={<PublicApp />} />
      </Routes>
    );
  }

  return (
    <WorkspaceProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/sign-in" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/new" element={<NewProject />} />

        <Route path="/workspaces/new" element={<WorkspaceNew />} />
        <Route path="/workspaces/join" element={<WorkspaceJoin />} />
        <Route path="/workspaces/:workspaceId" element={<WorkspaceLayout />}>
          <Route index element={<WorkspaceDashboard />} />
          <Route path="projects" element={<WorkspaceProjects />} />
          <Route path="projects/:projectId" element={<WorkspaceProjectDetail />} />
          <Route path="teams" element={<WorkspaceTeams />} />
          <Route path="teams/:teamId" element={<TeamDashboard />} />
          <Route path="members" element={<WorkspaceMembers />} />
          <Route path="activity" element={<WorkspaceActivity />} />
          <Route path="settings" element={<WorkspaceSettings />} />
        </Route>

        {/* Reference material: not scoped to a workspace or a project. */}
        <Route path="/library" element={<ResearchLibrary />} />
        <Route path="/library/:guideId" element={<GuideDetailPage />} />
        <Route path="/winning-projects" element={<WinningProjects />} />
        <Route path="/winning-projects/:winnerId" element={<WinningProjectDetail />} />
        <Route path="/outreach" element={<ResearchOutreach />} />
        <Route path="/assistant" element={<ResearchAssistant />} />

        <Route path="/projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<ThisWeek />} />
          <Route path="interview" element={<Interview />} />
          <Route path="analysis" element={<Analysis />} />
          <Route path="rubric" element={<Rubric />} />
          <Route path="novelty" element={<Novelty />} />
          <Route path="refine" element={<Refine />} />
          <Route path="plan" element={<Plan />} />
          <Route path="timeline" element={<TimelinePage />} />
          <Route path="poster" element={<Poster />} />
          <Route path="judging" element={<JudgePrep />} />
          <Route path="notebook" element={<Notebook />} />
          <Route path="assistant" element={<ResearchAssistant />} />
        </Route>

        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </WorkspaceProvider>
  );
}

import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { ErrorBoundary, FullPageLoading, FullPageMessage } from "./components/AppStates";
import { useAuth } from "./state/auth";
import { WorkspaceProvider } from "./state/workspace";
import Landing from "./pages/Landing";
import SignIn, { safeNext } from "./pages/SignIn";
// Pages load on demand: a visitor on the landing page should not download the
// timeline planner. Landing and sign-in stay in the main bundle for first paint.
const Projects = lazy(() => import("./pages/Projects"));
const Home = lazy(() => import("./pages/Home"));
const NewProject = lazy(() => import("./pages/NewProject"));
const ProjectLayout = lazy(() => import("./pages/ProjectLayout"));
const ThisWeek = lazy(() => import("./pages/ThisWeek"));
const Interview = lazy(() => import("./pages/Interview"));
const Analysis = lazy(() => import("./pages/Analysis"));
const Rubric = lazy(() => import("./pages/Rubric"));
const Novelty = lazy(() => import("./pages/Novelty"));
const Refine = lazy(() => import("./pages/Refine"));
const Plan = lazy(() => import("./pages/Plan"));
const TimelinePage = lazy(() => import("./pages/Timeline"));
const Poster = lazy(() => import("./pages/Poster"));
const JudgePrep = lazy(() => import("./pages/JudgePrep"));
const Notebook = lazy(() => import("./pages/Notebook"));
const WorkspaceLayout = lazy(() => import("./pages/WorkspaceLayout"));
const WorkspaceDashboard = lazy(() => import("./pages/WorkspaceDashboard"));
const WorkspaceProjects = lazy(() => import("./pages/WorkspaceProjects"));
const WorkspaceProjectDetail = lazy(() => import("./pages/WorkspaceProjectDetail"));
const WorkspaceMembers = lazy(() => import("./pages/WorkspaceMembers"));
const WorkspaceActivity = lazy(() => import("./pages/WorkspaceActivity"));
const WorkspaceSettings = lazy(() => import("./pages/WorkspaceSettings"));
const WorkspaceNew = lazy(() => import("./pages/WorkspaceNew"));
const WorkspaceJoin = lazy(() => import("./pages/WorkspaceJoin"));
const WorkspaceTeams = lazy(() => import("./pages/WorkspaceTeams"));
const TeamDashboard = lazy(() => import("./pages/TeamDashboard"));
const ResearchLibrary = lazy(() => import("./pages/ResearchLibrary"));
const GuideDetailPage = lazy(() => import("./pages/ResearchLibrary").then((m) => ({ default: m.GuideDetailPage })));
const WinningProjects = lazy(() => import("./pages/WinningProjects"));
const WinningProjectDetail = lazy(() => import("./pages/WinningProjects").then((m) => ({ default: m.WinningProjectDetail })));
const ResearchOutreach = lazy(() => import("./pages/ResearchOutreach"));
const ResearchAssistant = lazy(() => import("./pages/ResearchAssistant"));
const IsefExplorer = lazy(() => import("./pages/IsefExplorer"));
const IsefProjectDetail = lazy(() => import("./pages/IsefExplorer").then((m) => ({ default: m.IsefProjectDetail })));
const IsefImport = lazy(() => import("./pages/IsefImport"));

/** Just signed in: continue to the page that sent them to sign in. */
function AfterSignIn() {
  const [params] = useSearchParams();
  return <Navigate to={safeNext(params.get("next"))} replace />;
}

/** Signed-out visitors get the marketing site; everything else requires auth. */
function PublicApp() {
  const location = useLocation();
  if (location.pathname === "/sign-in") return <SignIn />;
  if (location.pathname === "/") return <Landing />;
  // Any other path while signed out (an emailed link, a bookmark, an expired
  // session): sign in, then land back where they were going.
  const next = encodeURIComponent(location.pathname + location.search);
  return <Navigate to={`/sign-in?next=${next}`} replace />;
}

export default function App() {
  const { user, ready, bootError, retryBoot, signOut } = useAuth();
  const location = useLocation();

  if (!ready) return <FullPageLoading label="Starting up…" />;

  if (bootError)
    return (
      <FullPageMessage
        title="Can't reach Research Coach right now"
        actions={
          <>
            <button className="btn" onClick={retryBoot}>
              Try again
            </button>
            <button className="btn btn--quiet" onClick={signOut}>
              Sign out
            </button>
          </>
        }
      >
        {bootError} You are still signed in.
      </FullPageMessage>
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
      <ErrorBoundary key={location.pathname}>
      <Suspense fallback={<FullPageLoading />}>
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<Home />} />
        <Route path="/sign-in" element={<AfterSignIn />} />
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
        <Route path="/isef" element={<IsefExplorer />} />
        <Route path="/isef/import" element={<IsefImport />} />
        <Route path="/isef/:historicalId" element={<IsefProjectDetail />} />

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

        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
      </Suspense>
      </ErrorBoundary>
    </WorkspaceProvider>
  );
}

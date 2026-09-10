// Single place that knows how to talk to the API: base URL, auth header,
// error shape. Components call named functions, never fetch directly.

import type * as T from "./types";

// Deployed default; point VITE_API_BASE at http://127.0.0.1:8000 to run locally.
const BASE = import.meta.env.VITE_API_BASE ?? "https://research-coach-il9g.onrender.com";
const TOKEN_KEY = "research-coach-token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<R>(path: string, init: RequestInit = {}): Promise<R> {
  const token = getToken();
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: any) => d.msg).join("; ");
    } catch {
      /* keep the default message */
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as R;
  return (await response.json()) as R;
}

const get = <R,>(path: string) => request<R>(path);
const post = <R,>(path: string, body?: unknown) =>
  request<R>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = <R,>(path: string, body: unknown) =>
  request<R>(path, { method: "PATCH", body: JSON.stringify(body) });
const put = <R,>(path: string, body: unknown) =>
  request<R>(path, { method: "PUT", body: JSON.stringify(body) });

interface TokenResponse {
  access_token: string;
  user_id: number;
  name: string;
  role: "student" | "mentor";
}

export const api = {
  login: (email: string, password: string) => post<TokenResponse>("/auth/login", { email, password }),
  register: (payload: Record<string, unknown>) => post<TokenResponse>("/auth/register", payload),
  me: () => get<T.User>("/auth/me"),

  listProjects: (workspaceId?: number) =>
    get<T.Project[]>(`/projects${workspaceId ? `?workspace_id=${workspaceId}` : ""}`),
  createProject: (payload: Record<string, unknown>) => post<T.Project>("/projects", payload),
  // legacy mentor roster route is gone; workspaceProjects replaces it
  getProject: (id: number) => get<T.Project>(`/projects/${id}`),
  updateProject: (id: number, payload: Record<string, unknown>) => patch<T.Project>(`/projects/${id}`, payload),

  interview: (id: number, answers: { question_key: string; answer: string }[], maxQuestions = 3) =>
    post<T.InterviewStep>(`/projects/${id}/interview`, { answers, max_questions: maxQuestions }),

  evaluate: (id: number) => post<T.EvaluationResult>(`/projects/${id}/evaluate`),
  latestEvaluation: (id: number) => get<T.StoredEvaluation>(`/projects/${id}/evaluation`),
  scoreHistory: (id: number) =>
    get<{ created_at: string; overall_score: number; dimensions: Record<string, number> }[]>(
      `/projects/${id}/score-history`,
    ),

  refine: (id: number) => post<T.RefinementResult>(`/projects/${id}/refine`),
  selectQuestion: (id: number, payload: Record<string, unknown>) => post<T.Project>(`/projects/${id}/question`, payload),

  createPlan: (id: number) => post<T.ResearchPlan>(`/projects/${id}/research-plan`),
  getPlan: (id: number) => get<T.ResearchPlan>(`/projects/${id}/research-plan`),

  comments: (id: number) => get<T.MentorComment[]>(`/projects/${id}/mentor-comments`),
  addComment: (id: number, payload: Record<string, unknown>) =>
    post<T.MentorComment>(`/projects/${id}/mentor-comments`, payload),
  resolveComment: (id: number, commentId: number) =>
    post<T.MentorComment>(`/projects/${id}/mentor-comments/${commentId}/resolve`),

  competitions: () => get<{ key: string; name: string; official_source_loaded: boolean; notice: string }[]>("/competitions"),
  competition: (key: string) =>
    get<{ key: string; name: string; notice: string; items: { key: string; label: string; source: T.RequirementSource; days_before_fair: number | null; note: string }[] }>(
      `/competitions/${key}`,
    ),

  generateTimeline: (id: number, payload: Record<string, unknown>) => post<T.Timeline>(`/projects/${id}/timeline`, payload),
  getTimeline: (id: number) => get<T.Timeline>(`/projects/${id}/timeline`),
  updateTask: (id: number, taskId: number, payload: Record<string, unknown>) =>
    patch<T.TimelineTask>(`/projects/${id}/tasks/${taskId}`, payload),
  readiness: (id: number) => get<T.Readiness>(`/projects/${id}/readiness`),
  thisWeek: (id: number) => get<T.WeeklyPlan>(`/projects/${id}/this-week`),
  checklist: (id: number) =>
    get<{ groups: Record<string, { key: string; label: string; done: boolean; source: T.RequirementSource; due_date: string | null }[]> }>(
      `/projects/${id}/checklist`,
    ),

  posterPlan: (id: number) => get<T.PosterPlan>(`/projects/${id}/poster/plan`),
  getPoster: (id: number) => get<{ layout_key: string | null; sections: Record<string, string> }>(`/projects/${id}/poster`),
  savePoster: (id: number, payload: { layout_key?: string | null; sections: Record<string, string> }) =>
    put<{ layout_key: string | null; sections: Record<string, string> }>(`/projects/${id}/poster`, payload),
  critiquePoster: (id: number) => post<T.PosterCritique>(`/projects/${id}/poster/critique`),

  interviewPrep: (id: number) => get<T.InterviewPrepSet>(`/projects/${id}/interview-prep`),
  mockJudge: (id: number, payload: { answer?: string; finish?: boolean }) =>
    post<T.MockJudgeReply>(`/projects/${id}/mock-judge`, payload),
  mockReport: (id: number) => get<T.MockJudgeReport>(`/projects/${id}/mock-judge/report`),

  notebook: (id: number) => get<T.NotebookEntry[]>(`/projects/${id}/notebook`),
  addNotebookEntry: (id: number, payload: Record<string, unknown>) =>
    post<T.NotebookEntry>(`/projects/${id}/notebook`, payload),
  templates: (id: number) => get<Record<string, { title: string; columns: string[] }>>(`/projects/${id}/templates`),

  /* --------------------------------------------------------- workspaces -- */

  myWorkspaces: () => get<T.WorkspaceSummary[]>("/workspaces"),
  createWorkspace: (payload: Record<string, unknown>) =>
    post<T.WorkspaceDetail>("/workspaces", payload),
  joinWorkspace: (join_code: string) => post<T.WorkspaceDetail>("/workspaces/join", { join_code }),
  acceptInvite: (token: string) =>
    post<T.WorkspaceDetail>("/workspaces/invitations/accept", { token }),
  workspace: (id: number) => get<T.WorkspaceDetail>(`/workspaces/${id}`),
  updateWorkspace: (id: number, payload: Record<string, unknown>) =>
    patch<T.WorkspaceDetail>(`/workspaces/${id}`, payload),
  archiveWorkspace: (id: number) => post<T.WorkspaceDetail>(`/workspaces/${id}/archive`),

  workspaceDashboard: (id: number) => get<T.WorkspaceDashboardData>(`/workspaces/${id}/dashboard`),
  workspaceProjects: (id: number, query: Record<string, string> = {}) => {
    const search = new URLSearchParams(
      Object.entries(query).filter(([, v]) => v),
    ).toString();
    return get<T.WorkspaceProjectRow[]>(
      `/workspaces/${id}/projects${search ? `?${search}` : ""}`,
    );
  },
  workspaceAttention: (id: number) => get<T.AttentionGroup[]>(`/workspaces/${id}/attention`),
  workspaceActivity: (id: number, kind?: string) =>
    get<T.ActivityEntry[]>(`/workspaces/${id}/activity${kind ? `?kind=${kind}` : ""}`),

  members: (id: number) => get<T.WorkspaceMember[]>(`/workspaces/${id}/members`),
  changeMemberRole: (id: number, userId: number, role: T.WorkspaceRole) =>
    patch<T.WorkspaceMember>(`/workspaces/${id}/members/${userId}`, { role }),
  removeMember: (id: number, userId: number) =>
    request<void>(`/workspaces/${id}/members/${userId}`, { method: "DELETE" }),
  invitations: (id: number) => get<T.Invitation[]>(`/workspaces/${id}/invitations`),
  invite: (id: number, payload: Record<string, unknown>) =>
    post<T.Invitation>(`/workspaces/${id}/invitations`, payload),

  projectProgress: (wsId: number, projectId: number) =>
    get<T.StudentProgress>(`/workspaces/${wsId}/projects/${projectId}/progress`),
  assignMentor: (wsId: number, projectId: number, mentor_id: number | null) =>
    patch<T.WorkspaceProjectRow>(`/workspaces/${wsId}/projects/${projectId}/mentor`, {
      mentor_id,
    }),
  setVisibility: (wsId: number, projectId: number, visibility: T.ProjectVisibility) =>
    patch<T.WorkspaceProjectRow>(`/workspaces/${wsId}/projects/${projectId}/visibility`, {
      visibility,
    }),
  workspaceComments: (wsId: number, projectId: number) =>
    get<T.WorkspaceComment[]>(`/workspaces/${wsId}/projects/${projectId}/comments`),
  addWorkspaceComment: (wsId: number, projectId: number, payload: Record<string, unknown>) =>
    post<T.WorkspaceComment>(`/workspaces/${wsId}/projects/${projectId}/comments`, payload),

  /* --------------------------------------------------------------- teams -- */

  teams: (wsId: number) => get<T.TeamSummary[]>(`/workspaces/${wsId}/teams`),
  team: (wsId: number, teamId: number) => get<T.TeamSummary>(`/workspaces/${wsId}/teams/${teamId}`),
  createTeam: (wsId: number, payload: Record<string, unknown>) =>
    post<T.TeamSummary>(`/workspaces/${wsId}/teams`, payload),
  updateTeam: (wsId: number, teamId: number, payload: Record<string, unknown>) =>
    patch<T.TeamSummary>(`/workspaces/${wsId}/teams/${teamId}`, payload),
  archiveTeam: (wsId: number, teamId: number) =>
    post<T.TeamSummary>(`/workspaces/${wsId}/teams/${teamId}/archive`),
  // Deliberately a different field name from the workspace join code: posting
  // one where the other belongs should fail loudly, not join the wrong thing.
  joinTeam: (wsId: number, team_join_code: string) =>
    post<T.TeamSummary>(`/workspaces/${wsId}/teams/join`, { team_join_code }),
  leaveTeam: (wsId: number, teamId: number, userId: number) =>
    request<void>(`/workspaces/${wsId}/teams/${teamId}/members/${userId}`, { method: "DELETE" }),
  setTeamMemberRole: (wsId: number, teamId: number, userId: number, role: T.TeamRole) =>
    patch<T.TeamSummary>(`/workspaces/${wsId}/teams/${teamId}/members/${userId}`, { role }),
  assignTeamMentor: (wsId: number, teamId: number, mentor_id: number | null) =>
    patch<T.TeamSummary>(`/workspaces/${wsId}/teams/${teamId}/mentor`, { mentor_id }),
  setTeamLock: (wsId: number, teamId: number, locked: boolean) =>
    patch<T.TeamSummary>(`/workspaces/${wsId}/teams/${teamId}/lock`, { locked }),
  teamDashboard: (wsId: number, teamId: number) =>
    get<T.TeamDashboardData>(`/workspaces/${wsId}/teams/${teamId}/dashboard`),
  createTeamProject: (wsId: number, teamId: number, payload: Record<string, unknown>) =>
    post<{ project_id: number; title: string; team_id: number }>(
      `/workspaces/${wsId}/teams/${teamId}/project`,
      payload,
    ),
  contributions: (wsId: number, teamId: number) =>
    get<T.Contribution[]>(`/workspaces/${wsId}/teams/${teamId}/contributions`),
  addContribution: (wsId: number, teamId: number, payload: Record<string, unknown>) =>
    post<T.Contribution>(`/workspaces/${wsId}/teams/${teamId}/contributions`, payload),
  updateContribution: (wsId: number, teamId: number, id: number, payload: Record<string, unknown>) =>
    patch<T.Contribution>(`/workspaces/${wsId}/teams/${teamId}/contributions/${id}`, payload),
  deleteContribution: (wsId: number, teamId: number, id: number) =>
    request<void>(`/workspaces/${wsId}/teams/${teamId}/contributions/${id}`, { method: "DELETE" }),

  /* ----------------------------------------------------- research library -- */

  libraryCategories: () =>
    get<{ key: T.GuideCategory; label: string; guide_count: number }[]>("/library/categories"),
  guides: (query: Record<string, string> = {}) => {
    const search = new URLSearchParams(Object.entries(query).filter(([, v]) => v)).toString();
    return get<T.GuideSummary[]>(`/library/guides${search ? `?${search}` : ""}`);
  },
  guide: (id: string) => get<T.GuideDetail>(`/library/guides/${id}`),
  recommendedGuides: (projectId: number) =>
    get<{ guides: T.RecommendedGuide[]; stage_guides: T.RecommendedGuide[]; evaluated: boolean }>(
      `/projects/${projectId}/recommended-guides`,
    ),

  /* ---------------------------------------------------- winning projects -- */

  winningProjects: (query: Record<string, string> = {}) => {
    const search = new URLSearchParams(Object.entries(query).filter(([, v]) => v)).toString();
    return get<T.WinningProjectList>(`/winning-projects${search ? `?${search}` : ""}`);
  },
  winningProject: (id: number) => get<T.WinningProjectBreakdown>(`/winning-projects/${id}`),
  similarWinningProjects: (projectId: number) =>
    get<{ projects: T.WinningProjectSummary[]; warning: string; empty_notice: string | null }>(
      `/projects/${projectId}/similar-winning-projects`,
    ),

  /* ------------------------------------------------------------ outreach -- */

  outreachTemplates: () =>
    get<{ templates: T.OutreachTemplate[]; spam_warning: string; etiquette: string[] }>(
      "/outreach/templates",
    ),
  buildOutreachDraft: (payload: Record<string, unknown>) =>
    post<T.OutreachDraft>("/outreach/draft", payload),
  outreachContacts: () => get<T.OutreachContact[]>("/outreach/contacts"),
  createOutreachContact: (payload: Record<string, unknown>) =>
    post<T.OutreachContact>("/outreach/contacts", payload),
  updateOutreachContact: (id: number, payload: Record<string, unknown>) =>
    patch<T.OutreachContact>(`/outreach/contacts/${id}`, payload),
  deleteOutreachContact: (id: number) =>
    request<void>(`/outreach/contacts/${id}`, { method: "DELETE" }),
  outreachSummary: () => get<T.OutreachSummary>("/outreach/summary"),

  /* --------------------------------------------------- research assistant -- */

  assistantConversations: (projectId?: number) =>
    get<T.AssistantConversationSummary[]>(
      `/assistant/conversations${projectId ? `?project_id=${projectId}` : ""}`,
    ),
  startAssistantConversation: (projectId?: number | null) =>
    post<T.AssistantConversation>("/assistant/conversations", { project_id: projectId ?? null }),
  assistantConversation: (id: number) =>
    get<T.AssistantConversation>(`/assistant/conversations/${id}`),
  sendAssistantMessage: (id: number, content: string) =>
    post<T.AssistantMessage>(`/assistant/conversations/${id}/messages`, { content }),
  shareAssistantConversation: (id: number, shared: boolean) =>
    patch<T.AssistantConversation>(`/assistant/conversations/${id}/share`, {
      shared_with_team: shared,
    }),
  deleteAssistantConversation: (id: number) =>
    request<void>(`/assistant/conversations/${id}`, { method: "DELETE" }),
  assistantProjectContext: (projectId: number) =>
    get<T.AssistantProjectContext>(`/assistant/projects/${projectId}/context`),
  assistantSuggestedActions: () =>
    get<T.AssistantSuggestedAction[]>("/assistant/suggested-actions"),
};

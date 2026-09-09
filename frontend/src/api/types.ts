// Mirrors the backend Pydantic schemas. Kept hand-written and small rather than
// generated, so the shapes the UI actually depends on are visible in one file.

export type EvidenceBasis = "current_evidence" | "projected_potential" | "not_yet_assessable";

export type NoveltyStatus =
  | "likely_common"
  | "incremental"
  | "moderately_differentiated"
  | "potentially_novel"
  | "strong_research_gap_potential"
  | "insufficient_evidence";

export type TaskStatus = "not_started" | "in_progress" | "blocked" | "needs_mentor_review" | "complete";
export type Priority = "low" | "medium" | "high" | "critical";
export type RequirementSource =
  | "verified_competition_requirement"
  | "unverified_competition_item"
  | "recommended_club_milestone";

export interface User {
  id: number;
  name: string;
  email: string;
  role: "student" | "mentor";
  school?: string | null;
}

export interface QuestionRevision {
  id: number;
  version: number;
  text: string;
  source: string;
  variant: string | null;
  rationale: string | null;
  improvements: string[];
  created_at: string;
}

export interface InterviewTurn {
  id: number;
  question_key: string;
  question_text: string;
  dimension: string;
  why_asked: string | null;
  answer_text: string | null;
  followup_note: string | null;
}

export interface Project {
  id: number;
  title: string;
  owner_id: number;
  workspace_id: number;
  mentor_id: number | null;
  visibility: ProjectVisibility;
  status: ProjectStatus;
  grade_level: number;
  project_type: "scientific" | "engineering";
  category: string;
  stage: string;
  current_question: string;
  topic?: string | null;
  background_knowledge?: string | null;
  competition_key?: string | null;
  competition_name?: string | null;
  competition_date?: string | null;
  school_deadline?: string | null;
  hours_per_week?: number | null;
  trials_planned?: number | null;
  minutes_per_trial?: number | null;
  teammates: number;
  already_experimenting: boolean;
  updated_at: string;
  revisions: QuestionRevision[];
  interview_turns: InterviewTurn[];
}

export interface InterviewQuestion {
  key: string;
  dimension: string;
  text: string;
  why_asked: string;
  hint: string | null;
}

export interface AnswerCritique {
  question_key: string;
  accepted: boolean;
  note: string;
  follow_up: string | null;
}

export interface InterviewStep {
  questions: InterviewQuestion[];
  critiques: AnswerCritique[];
  completeness: number;
  ready_to_evaluate: boolean;
  coverage: Record<string, boolean>;
}

export interface DimensionScore {
  key: string;
  label: string;
  score: number;
  basis: EvidenceBasis;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  improvements: string[];
  criteria: Record<string, number>;
}

export interface RubricLine {
  key: string;
  label: string;
  points_possible: number;
  points_projected: number;
  basis: EvidenceBasis;
  strengths: string[];
  weaknesses: string[];
  to_improve: string[];
}

export interface AzsefRubric {
  lines: RubricLine[];
  points_possible: number;
  points_projected: number;
  assessable_points: number;
  disclaimer: string;
}

export interface NoveltyAnalysis {
  status: NoveltyStatus;
  confidence: string;
  headline: string;
  similar_existing_ideas: string[];
  whats_different: string[];
  novelty_risks: string[];
  ways_to_increase: string[];
  literature_search_performed: boolean;
  sources: string[];
  evidence_note: string;
}

export interface SafetyFlag {
  category: string;
  label: string;
  matched_terms: string[];
  why_it_matters: string;
  likely_paperwork: string[];
}

export interface SafetyScreening {
  flags: SafetyFlag[];
  preapproval_possible: boolean;
  determination_made: boolean;
  notice: string;
}

export interface EvaluationResult {
  overall_score: number;
  information_completeness: number;
  dimensions: DimensionScore[];
  rubric: AzsefRubric;
  novelty: NoveltyAnalysis;
  safety: SafetyScreening;
  mentor_summary: string;
  next_actions: string[];
  socratic_questions: string[];
  provider: string;
}

export interface StoredEvaluation {
  id: number;
  created_at: string;
  overall_score: number;
  information_completeness: number;
  dimensions: DimensionScore[];
  rubric: AzsefRubric;
  novelty: NoveltyAnalysis;
  safety: SafetyScreening;
  mentor_summary: string;
  next_actions: string[];
  socratic_questions: string[];
}

export interface QuestionVariant {
  variant: string;
  label: string;
  question: string;
  independent_variable: string;
  dependent_variable: string;
  controls: string[];
  population: string;
  hypothesis: string;
  primary_measurement: string;
  experiment_type: string;
  what_changed: string[];
  trade_offs: string[];
}

export interface RefinementResult {
  original_question: string;
  diagnosis: string[];
  variants: QuestionVariant[];
  note: string;
}

export interface ResearchPlan {
  id: number;
  question: string;
  created_at: string;
  content: Record<string, string | string[]>;
}

export interface TimelineTask {
  id: number;
  key: string;
  phase: string;
  phase_index: number;
  title: string;
  description: string | null;
  start_date: string | null;
  due_date: string | null;
  status: TaskStatus;
  priority: Priority;
  estimated_hours: number;
  depends_on: string[];
  requirement_source: RequirementSource;
  ai_note: string | null;
}

export interface TimelineWarning {
  severity: string;
  message: string;
  recommendation: string;
}

export interface Timeline {
  tasks: TimelineTask[];
  warnings: TimelineWarning[];
  total_estimated_hours: number;
  available_hours: number;
  days_remaining: number;
  competition_name: string | null;
  competition_date: string | null;
  requirement_disclaimer: string;
}

export interface ReadinessArea {
  key: string;
  label: string;
  percent: number;
  note: string;
}

export interface Readiness {
  areas: ReadinessArea[];
  overall: number;
  disclaimer: string;
}

export interface MentorComment {
  id: number;
  author_name: string;
  section: string;
  body: string;
  requires_action: boolean;
  resolved: boolean;
  created_at: string;
}

export interface WeeklyPlan {
  priorities: TimelineTask[];
  upcoming_deadline: string | null;
  days_remaining: number | null;
  completion_percent: number;
  blockers: TimelineTask[];
  mentor_requests: MentorComment[];
  risk_notes: string[];
}

export interface MentorRow {
  project_id: number;
  student_name: string;
  grade_level: number;
  title: string;
  category: string;
  project_type: string;
  current_question: string;
  stage: string;
  readiness: number | null;
  novelty_status: NoveltyStatus | null;
  feasibility: number | null;
  rubric_question_points: number | null;
  safety_flags: string[];
  open_comments: number;
  last_activity: string;
}

export interface PosterSectionGuide {
  key: string;
  title: string;
  purpose: string;
  target_words: number;
  currently_has: string;
  should_add: string[];
  should_remove: string[];
  judge_questions: string[];
}

export interface PosterLayout {
  key: string;
  name: string;
  columns: Record<string, string[]>;
  why_it_fits: string;
  fit_score: number;
}

export interface FigureSuggestion {
  name: string;
  kind: string;
  why: string;
  where_on_poster: string;
}

export interface PosterPlan {
  sections: PosterSectionGuide[];
  layouts: PosterLayout[];
  figures: FigureSuggestion[];
  visual_assets: FigureSuggestion[];
}

export interface PosterCritique {
  score: number;
  basis: EvidenceBasis;
  main_problems: string[];
  text_length_flags: string[];
  strengths: string[];
  disclaimer: string;
}

export interface JudgeQuestion {
  category: string;
  text: string;
  what_theyre_probing: string;
  difficulty: string;
}

export interface InterviewPrepSet {
  questions: JudgeQuestion[];
  pitch_prompts: string[];
}

export interface MockJudgeReply {
  judge_question: string;
  reaction: string | null;
  probing: string;
  turn_index: number;
  finished: boolean;
}

export interface MockJudgeReport {
  readiness: number;
  strong_answers: string[];
  weak_answers: string[];
  concepts_to_review: string[];
  struggled_with: string[];
  communication_problems: string[];
  better_explanations: string[];
}

export interface NotebookEntry {
  id: number;
  entry_date: string;
  what_was_done: string;
  procedure_changes?: string | null;
  observations?: string | null;
  problems?: string | null;
  raw_measurements?: string | null;
  open_questions?: string | null;
  next_steps?: string | null;
}

/* ------------------------------------------------------------ workspaces -- */

export type WorkspaceRole = "owner" | "lead" | "mentor" | "member";
export type WorkspaceType =
  | "school"
  | "research_club"
  | "classroom"
  | "science_fair_team"
  | "independent_group"
  | "personal";
export type ProjectStatus =
  | "on_track"
  | "needs_attention"
  | "at_risk"
  | "blocked"
  | "complete";
export type ProjectVisibility = "private" | "workspace";
export type CommentType = "general" | "needs_action" | "important" | "resolved";
export type ActivityKind = "milestone" | "comment" | "project_change" | "overdue";

export interface WorkspaceSummary {
  id: number;
  name: string;
  organization_name: string | null;
  workspace_type: WorkspaceType;
  description: string | null;
  is_personal: boolean;
  is_archived: boolean;
  my_role: WorkspaceRole;
  member_count: number;
  project_count: number;
}

export interface WorkspaceDetail extends WorkspaceSummary {
  join_code: string | null;
  default_project_visibility: ProjectVisibility;
  leads_can_assign_mentors: boolean;
  created_at: string;
}

export interface WorkspaceMember {
  user_id: number;
  name: string;
  email: string;
  role: WorkspaceRole;
  joined_at: string;
  project_count: number;
  mentoring_count: number;
  last_activity: string | null;
}

export interface WorkspaceProjectRow {
  project_id: number;
  title: string;
  owner_id: number;
  owner_name: string;
  category: string;
  project_type: string;
  stage: string;
  current_question: string;
  competition_name: string | null;
  competition_date: string | null;
  days_to_competition: number | null;
  readiness: number | null;
  research_question_score: number | null;
  methodology_score: number | null;
  feasibility_score: number | null;
  novelty_status: NoveltyStatus | null;
  approval_status: string;
  safety_flags: string[];
  experimentation_percent: number;
  poster_percent: number;
  interview_percent: number;
  methodology_percent: number;
  next_deadline: string | null;
  next_task: string | null;
  last_activity: string | null;
  days_inactive: number;
  mentor_id: number | null;
  mentor_name: string | null;
  status: ProjectStatus;
  reasons: string[];
  blockers: string[];
  open_comments: number;
}

export interface AttentionGroup {
  key: string;
  severity: "high" | "medium" | "low";
  label: string;
  projects: { project_id: number; title: string; owner_name: string; detail: string }[];
}

export interface MentorWorkload {
  user_id: number;
  name: string;
  email: string;
  assigned_projects: number;
  needing_review: number;
  at_risk: number;
}

export interface WorkspaceStats {
  total_projects: number;
  active_projects: number;
  on_track: number;
  needs_attention: number;
  at_risk: number;
  blocked: number;
  complete: number;
  awaiting_approval: number;
  needing_mentor_review: number;
  without_mentor: number;
  near_deadline: number;
  average_readiness: number | null;
  by_stage: Record<string, number>;
  by_category: Record<string, number>;
  average_poster: number;
  average_interview: number;
}

export interface UpcomingDeadline {
  project_id: number;
  title: string;
  owner_name: string;
  label: string;
  due: string;
  days_away: number;
}

export interface ActivityEntry {
  id: number;
  project_id: number | null;
  project_title: string | null;
  actor_name: string;
  kind: ActivityKind;
  action: string;
  summary: string;
  created_at: string;
}

export interface WorkspaceDashboardData {
  workspace: WorkspaceDetail;
  stats: WorkspaceStats;
  attention: AttentionGroup[];
  upcoming_deadlines: UpcomingDeadline[];
  mentors: MentorWorkload[];
  competitions: string[];
  recent_activity: ActivityEntry[];
}

export interface StudentProgress {
  areas: { key: string; label: string; percent: number; note: string }[];
  overall: number;
  current_priority: string | null;
  next_deadline: string | null;
  days_to_next_deadline: number | null;
  current_risk: string | null;
  status: ProjectStatus;
}

export interface WorkspaceComment {
  id: number;
  project_id: number;
  author_id: number | null;
  author_name: string;
  author_role: WorkspaceRole;
  section: string;
  comment_type: CommentType;
  body: string;
  requires_action: boolean;
  resolved: boolean;
  created_at: string;
}

export interface Invitation {
  id: number;
  email: string | null;
  role: WorkspaceRole;
  token: string;
  expires_at: string;
  accepted_at: string | null;
}

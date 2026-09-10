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

export type ProjectOwnerKind = "individual" | "team";

export interface Project {
  id: number;
  title: string;
  // Exactly one of these is set. A team project has owner_id null and every
  // member of owner_team_id edits this same record.
  owner_id: number | null;
  owner_team_id: number | null;
  owner_kind: ProjectOwnerKind;
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
  members_can_create_teams: boolean;
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
  teams: { id: number; name: string }[];
}

export interface WorkspaceProjectRow {
  project_id: number;
  title: string;
  // Null on a team project: owner_name is then the team name and member_names
  // lists who is on it. One catalog, both ownership modes.
  owner_id: number | null;
  owner_name: string;
  owner_kind: ProjectOwnerKind;
  team_id: number | null;
  team_name: string | null;
  member_names: string[];
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

/* ========================================================================== *
 * Teams
 * ========================================================================== */

export type TeamRole = "team_lead" | "member";

export interface CompetitionTeamRules {
  competition_key: string;
  competition_name: string;
  teams_allowed: boolean;
  max_team_size: number;
  min_team_size: number;
  lock_membership_after_registration: boolean;
  divisions: string[];
  source: RequirementSource;
  official_source_loaded: boolean;
  notice: string;
}

export interface TeamCapacity {
  member_count: number;
  max_team_size: number;
  seats_left: number;
  is_full: boolean;
  limit_source: "team_override" | "competition_config";
  membership_locked: boolean;
  rules: CompetitionTeamRules;
  notice: string;
}

export interface TeamSummary {
  id: number;
  workspace_id: number;
  name: string;
  description: string | null;
  join_code: string | null;
  is_discoverable: boolean;
  is_archived: boolean;
  membership_locked: boolean;
  mentor_id: number | null;
  mentor_name: string | null;
  competition_key: string | null;
  member_count: number;
  max_team_size: number;
  seats_left: number;
  member_names: string[];
  project_id: number | null;
  project_title: string | null;
  readiness: number | null;
  stage: string | null;
  status: ProjectStatus | null;
  next_deadline: string | null;
  i_am_member: boolean;
  i_can_edit: boolean;
  created_at: string;
}

export interface TeamMember {
  user_id: number;
  name: string;
  email: string;
  role: TeamRole;
  joined_at: string;
  contribution_count: number;
  completed_count: number;
  hours: number;
}

export interface Contribution {
  id: number;
  project_id: number;
  team_id: number;
  user_id: number;
  user_name: string;
  task: string;
  description: string | null;
  contribution_date: string | null;
  hours: number | null;
  completed: boolean;
  requested_by_id: number | null;
  requested_by_name: string | null;
  created_at: string;
}

export interface TeamDashboardData {
  team: TeamSummary;
  members: TeamMember[];
  capacity: TeamCapacity;
  can_edit_project: boolean;
  can_manage_team: boolean;
  project: {
    id: number;
    title: string;
    current_question: string;
    stage: string;
    status: ProjectStatus;
    readiness: number | null;
    category: string;
    project_type: string;
    competition_name: string | null;
    competition_date: string | null;
    days_to_competition: number | null;
    next_deadline: string | null;
    next_task: string | null;
    mentor_name: string | null;
    visibility: ProjectVisibility;
  } | null;
  tasks: {
    id: number;
    title: string;
    phase: string;
    status: TaskStatus;
    due_date: string | null;
    priority: Priority;
  }[];
  contributions: Contribution[];
  contribution_rollup: { user_id: number; name: string; tasks: number; completed: number; hours: number }[];
  notebook: { id: number; entry_date: string; what_was_done: string; observations: string | null; created_at: string }[];
  comments: {
    id: number;
    author_name: string;
    author_role: string;
    body: string;
    comment_type: string;
    requires_action: boolean;
    resolved: boolean;
    created_at: string;
  }[];
  activity: { id: number; actor_name: string; kind: string; action: string; summary: string; created_at: string }[];
}

/* ========================================================================== *
 * Research Library
 * ========================================================================== */

export type GuideCategory =
  | "research_fundamentals"
  | "experimental_design"
  | "statistics"
  | "research_and_literature"
  | "data"
  | "science_fair";

export interface GuideSummary {
  id: string;
  title: string;
  category: GuideCategory;
  category_label: string;
  summary: string;
  read_minutes: number;
  tags: string[];
  has_comparisons: boolean;
}

export interface GuideDetail extends GuideSummary {
  sections: { heading: string; body: string; points: string[] }[];
  comparisons: { label: string; weak: string; strong: string; why: string }[];
  related: GuideSummary[];
}

export interface RecommendedGuide {
  guide_id: string;
  title: string;
  category: GuideCategory;
  summary: string;
  read_minutes: number;
  reason: string;
}

/* ========================================================================== *
 * Winning Projects
 * ========================================================================== */

export type SourceConfidence = "verified_source" | "unverified" | "ai_analysis" | "not_available";

export interface WinningProjectSummary {
  id: number;
  title: string;
  year: number | null;
  competition_name: string | null;
  category: string;
  project_type: string;
  division: string | null;
  is_team: boolean;
  team_size: number | null;
  award_title: string | null;
  is_illustrative: boolean;
  source_name: string;
  source_url: string | null;
  has_breakdown: boolean;
  notice: string | null;
}

export interface SourcedField {
  value: string | Record<string, string> | null;
  provenance: SourceConfidence;
}

export interface WinningProjectBreakdown extends WinningProjectSummary {
  facts: Record<string, SourcedField>;
  fields_available: string[];
  fields_missing: string[];
  sufficient_for_breakdown: boolean;
  insufficient_notice: string | null;
  judging: { commentary: string | null; provenance: SourceConfidence; notice: string | null };
  lessons: { lesson: string; detail: string; guide_id: string }[];
  lessons_provenance: SourceConfidence;
  analysis_notice: string;
  copying_warning: string;
}

export interface WinningProjectList {
  projects: WinningProjectSummary[];
  filters: {
    years: number[];
    competitions: string[];
    categories: string[];
    project_types: string[];
    total: number;
    verified_total: number;
    illustrative_total: number;
  };
  empty_notice: string | null;
  copying_warning: string;
}

/* ========================================================================== *
 * Research Outreach
 * ========================================================================== */

export type OutreachStatus =
  | "draft"
  | "sent"
  | "replied"
  | "meeting_scheduled"
  | "no_response"
  | "declined";

export interface OutreachTemplate {
  key: string;
  name: string;
  category: string;
  category_label: string;
  when_to_use: string;
  avoid_when: string;
  structure: { section: string; guidance: string }[];
  ask_examples: string[];
  required_personalisation: string[];
  example_subjects: string[];
  why_it_works: string;
  common_mistakes: string[];
  register: string;
}

export interface OutreachTone {
  key: string;
  name: string;
  description: string;
}

export interface OutreachPersonalisation {
  verdict: "too_short" | "generic" | "unclear" | "specific";
  is_specific: boolean;
  message: string;
  word_count: number;
}

export interface OutreachQuality {
  score: number;
  verdict: string;
  strengths: string[];
  improvements: string[];
  word_count: number;
  personalisation: OutreachPersonalisation;
}

export interface OutreachPrefill {
  project_id: number;
  project_title: string;
  research_topic: string | null;
  research_question: string | null;
  category: string;
  competition: string | null;
  timeline: string | null;
  methodology_summary: string | null;
  student_name: string;
  school: string | null;
  grade_level: number | null;
}

export interface OutreachDraft {
  template_key: string;
  subject: string;
  body: string;
  sections: { section: string; content: string }[];
  word_count: number;
  tone: string;
  tones: OutreachTone[];
  quality: OutreachQuality;
  sources_note: string;
  spam_warning: string;
  etiquette: string[];
  before_you_send: string[];
}

export interface OutreachContact {
  id: number;
  researcher_name: string;
  institution: string | null;
  email: string | null;
  their_work: string | null;
  project_id: number | null;
  template_key: string | null;
  subject: string | null;
  body: string | null;
  status: OutreachStatus;
  status_label: string;
  sent_on: string | null;
  follow_up_on: string | null;
  follow_up_done: boolean;
  follow_up_due: boolean;
  notes: string | null;
}

export interface OutreachSummary {
  total: number;
  by_status: { status: OutreachStatus; label: string; count: number }[];
  follow_ups_due: OutreachContact[];
  spam_warning: string;
}

/* ------------------------------------------------- research assistant -- */

export interface AssistantGuideRef {
  guide_id: string;
  title: string;
  category: string;
  summary: string;
  read_minutes: number;
}

export interface AssistantMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  follow_ups: string[];
  provider: string | null;
  created_at: string;
  guides: AssistantGuideRef[];
}

export interface AssistantProjectContext {
  project_id: number;
  title: string;
  question: string;
  project_type: string;
  category: string;
  grade_level: number;
  stage: string;
  competition: string | null;
  readiness: number | null;
  answered_count: number;
  total_questions: number;
  known_fields: string[];
  missing_fields: string[];
  safety_flags: string[];
  next_deadline: string | null;
}

export interface AssistantSuggestedAction {
  key: string;
  label: string;
  prompt: string;
}

export interface AssistantConversationSummary {
  id: number;
  title: string;
  project_id: number | null;
  project_title: string | null;
  shared_with_team: boolean;
  message_count: number;
  last_message_preview: string | null;
  updated_at: string;
}

export interface AssistantConversation {
  id: number;
  title: string;
  project_id: number | null;
  shared_with_team: boolean;
  created_at: string;
  updated_at: string;
  messages: AssistantMessage[];
  context: AssistantProjectContext | null;
  suggested_actions: AssistantSuggestedAction[];
}

/* ------------------------------------------------- ISEF project explorer -- */

export interface HistoricalSourceInformation {
  title: string;
  year: number | null;
  category: string | null;
  subcategory: string | null;
  project_type: string | null;
  team_project: boolean | null;
  abstract: string | null;
  awards: string | null;
  student_display: string | null;
  school_display: string | null;
  country: string | null;
  state: string | null;
  source: string;
  source_url: string | null;
  permission_note: string | null;
}

export interface HistoricalAIAnalysis {
  research_question: string | null;
  why_it_matters: string | null;
  methodology: string | null;
  scientific_depth: string | null;
  novelty: string | null;
  evidence: string | null;
  lessons_for_students: string[];
  model: string;
  generated_at: string;
}

export interface HistoricalProjectCard {
  id: number;
  title: string;
  year: number | null;
  category: string | null;
  team_project: boolean | null;
  awards: string | null;
  has_abstract: boolean;
  source: string;
  derived_tags: string[];
}

export interface HistoricalProjectDetail {
  id: number;
  source_information: HistoricalSourceInformation;
  source_categories: string[];
  derived_tags: string[];
  ai_analysis: HistoricalAIAnalysis | null;
  analysis_unavailable_reason: string | null;
  copying_notice: string;
}

export interface HistoricalFacetValue {
  value: string | number;
  count: number;
}

export interface HistoricalFacets {
  total: number;
  awarded: number;
  categories: HistoricalFacetValue[];
  years: HistoricalFacetValue[];
  sources: HistoricalFacetValue[];
  derived_tags: HistoricalFacetValue[];
}

export interface HistoricalSearchResult {
  results: HistoricalProjectCard[];
  total: number;
  limit: number;
  offset: number;
  copying_notice: string;
}

export interface HistoricalSimilarMatch {
  project: HistoricalProjectCard;
  score: number;
  reasons: string[];
}

export interface HistoricalSimilarResult {
  matches: HistoricalSimilarMatch[];
  matched_on: string[];
  empty_notice: string | null;
  copying_notice: string;
}

export interface HistoricalImportReport {
  created: number;
  updated: number;
  skipped: number;
  total: number;
  errors: string[];
}

/* --------------------------------------------------------- home dashboard -- */

export interface NextActionItem {
  action: string;
  why: string;
  guide_ids: string[];
}

export interface NextActionPlan {
  primary: NextActionItem;
  secondary: NextActionItem[];
  source: string;
}

export interface HomeAttentionItem {
  kind: "safety" | "overdue" | "blocked" | "outreach";
  label: string;
  detail: string;
}

export interface HomeUpcoming {
  title: string;
  due_date: string;
  phase: string;
  days_away: number;
}

export interface HomeProject {
  id: number;
  title: string;
  question: string;
  stage: string;
  status: ProjectStatus;
  readiness: number | null;
  information_completeness: number | null;
  competition: string | null;
  competition_date: string | null;
  is_team_project: boolean;
  workspace_id: number;
}

export interface HomeDashboard {
  has_project: boolean;
  project: HomeProject | null;
  next_action: NextActionPlan;
  attention: HomeAttentionItem[];
  upcoming: HomeUpcoming[];
  suggested_guides: { guide_id: string; title: string; summary: string; read_minutes: number }[];
  similar_historical_count: number;
  other_projects: { id: number; title: string; stage: string; status: ProjectStatus }[];
  follow_ups_due: number;
}

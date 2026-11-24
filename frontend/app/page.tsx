"use client";
import { useEffect, useState, FormEvent, ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  ArrowUpRight,
  BookOpen,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ChevronDown,
  Database,
  FileUp,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  MapPin,
  Menu,
  Network,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  Users,
  X,
} from "lucide-react";

type User = {
  id: number;
  name: string;
  email: string;
  role: "admin" | "applicant" | "company" | "placement";
};
type Skill = {
  id: number;
  canonical_id: string;
  name: string;
  aliases: string[];
  category: string;
  source: string;
  source_version: string;
  related: number[];
  reviewed: boolean;
  listing_count: number;
  listings?: Listing[];
};
type Listing = {
  id: number;
  owner_id: number;
  listing_version: number;
  declared_status: string;
  rolling?: boolean;
  title: string;
  organization: string;
  source_name: string;
  source_url: string;
  application_url?: string;
  source_provider?: string;
  source_verified_at?: string;
  source_closes_at?: string | null;
  academic_fields?: string[];
  location: string | null;
  work_mode: string | null;
  description: string;
  requirements_text: string;
  requirements: { skill_id: number; classification: string; excerpt: string }[];
  mandatory_qualifications: string[];
  stipend: string | null;
  deadline: string | null;
  last_verified: string | null;
  status: string;
  sector: string | null;
};
type Evidence = {
  id: number;
  applicant_id: number;
  document_id: string | null;
  kind: string;
  value: string;
  skill_id: number | null;
  excerpt: string;
  page: number;
  section: string;
  source: string;
  context: string;
  status: string;
};
type Policy = {
  id: number;
  name: string;
  config: Record<string, unknown>;
  document_ids: number[];
  approved_by: number | null;
};
type Round = {
  id: number;
  name: string;
  policy_id: number;
  choices: number[];
  listing_ids: number[];
  choice_listings?: { id: number; title: string; status: string }[];
  scope: string | null;
  frozen: boolean;
  capacities: {
    listing_id: number;
    seats: number;
    confirmation_reference: string;
  }[];
};
type AgentCase = {
  id: string;
  applicant_id: number;
  round_id: number | null;
  policy_id: number | null;
  status: string;
  mode: string;
  next_nodes: string[];
  unresolved: string[];
  activity: {
    id: number;
    tool: string;
    outcome: Record<string, unknown>;
    next_action: string;
    at: string;
  }[];
};
type Match = {
  listing_id: number;
  score: number | null;
  merit_score: number | null;
  evidence_coverage?: number;
  coverage_threshold_met?: boolean;
  unresolved_requirements?: string[];
  eligibility_status?: string;
  utility?: number;
  contributions: Record<string, number | null>;
  matched_skills: number[];
  matched_skill_names?: string[];
  missing_skills: number[];
  related_unverified: number[];
  rank: number | null;
  listing?: Listing;
  explanation?: string;
  reason?: string;
  policy_version?: number;
  solver_status?: string;
  outcome?: string;
};
type EligibilityNote = { reasons: string[] };
type Draft = {
  id: number;
  round_id: number;
  policy_version: number;
  digest: string;
  approved_by: number | null;
  published_at: string | null;
  stale: boolean;
  solver_status: string;
  placement_status: string;
  publishable: boolean;
  placements: Match[];
  unassigned: { applicant_id: number; reason: string }[];
  metrics: Record<string, unknown>;
  baseline_metrics: Record<string, unknown>;
  conflicts: string[];
  deterministic_checks: string[];
  baseline_note: string;
};
type Profile = {
  education?: string | null;
  qualification?: string | null;
  course?: string | null;
  academic_branch?: string | null;
  graduation_status?: string | null;
  preferred_role?: string | null;
  projects?: string[];
  certifications?: string[];
  preferred_work_modes?: string[];
  approved_hosted_resume_processing?: boolean;
  district: string | null;
  home_location: string | null;
  preferred_locations: string[];
  preferred_sectors: string[];
  willing_to_relocate: boolean;
  academic_score: number | null;
  prior_participation: boolean | null;
  groups: string[];
  consent: boolean;
};
const emptyProfile: Profile = {
  district: null,
  home_location: null,
  preferred_locations: [],
  preferred_sectors: [],
  willing_to_relocate: true,
  academic_score: null,
  prior_participation: null,
  groups: [],
  consent: false,
};
async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const token = sessionStorage.getItem("allocateai-v2-token");
  const headers: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  const response = await fetch("/api" + path, {
    method,
    headers,
    body:
      body instanceof FormData
        ? body
        : body === undefined
          ? undefined
          : JSON.stringify(body),
    cache: "no-store",
  });
  const data = await response.json().catch(() => ({
    detail: "The API could not complete this request. Try again or check the server status.",
  }));
  if (!response.ok) {
    if (response.status === 401 && path != "/auth/login")
      window.dispatchEvent(new Event("session-expired"));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail || data),
    );
  }
  return data;
}
function Badge({
  children,
  tone = "green",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Button({
  children,
  onClick,
  disabled = false,
  secondary = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  secondary?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`btn ${secondary ? "secondary" : "primary"}`}
    >
      {children}
    </button>
  );
}
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <Database size={27} />
      <h3>Waiting for real inputs</h3>
      <p>{children}</p>
    </div>
  );
}
function JsonBox({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (s: string) => void;
  label: string;
}) {
  return (
    <Field label={label}>
      <textarea
        className="json-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={10}
        spellCheck={false}
      />
    </Field>
  );
}
const names: Record<string, string> = {
  overview: "Workspace overview",
  listings: "Internship Explorer",
  skills: "Skills Explorer",
  profile: "Applicant Workspace",
  agent: "Agent Activity",
  policy: "Policy Evidence",
  rounds: "Allocation Rounds",
  review: "Evidence & Draft Review",
  imports: "Data Imports",
  results: "Published Outcomes",
};
const icons: Record<string, typeof Network> = {
  overview: LayoutDashboard,
  listings: BriefcaseBusiness,
  skills: Sparkles,
  profile: GraduationCap,
  agent: Activity,
  policy: BookOpen,
  rounds: Network,
  review: ShieldCheck,
  imports: Database,
  results: CheckCircle2,
};
const blankListing = {
  title: "",
  organization: "",
  source_name: "",
  source_url: "",
  location: null,
  work_mode: null,
  sector: null,
  description: "",
  requirements_text: "",
  requirements: [],
  mandatory_qualifications: [],
  stipend: null,
  deadline: null,
  last_verified: null,
  rolling: false,
  status: "unverified",
};

export default function Workspace() {
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [notice, setNotice] = useState<{ error: boolean; text: string } | null>(
    null,
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [register, setRegister] = useState(false);
  const [activationToken, setActivationToken] = useState("");
  const [participantImport, setParticipantImport] = useState(
    '{"authorized":false,"profiles":[]}',
  );
  const [participantImportResult, setParticipantImportResult] =
    useState<unknown>(null);
  const [staffScope, setStaffScope] = useState("");
  const [staffReference, setStaffReference] = useState("");
  const [staffRequests, setStaffRequests] = useState<{user_id:number; scope:string; reference:string}[]>([]);
  const [staffStatus, setStaffStatus] = useState<{requested:boolean; verified:boolean; scope:string|null}>();
  const [roundScope, setRoundScope] = useState("");
  const [roundRoles, setRoundRoles] = useState<number[]>([]);
  const [participantId, setParticipantId] = useState("");
  const [participantReference, setParticipantReference] = useState("");
  const [participantList, setParticipantList] = useState<{applicant_id:number; choices_submitted:boolean}[]>([]);
  const [auditEvents, setAuditEvents] = useState<{id:number; action:string; actor_id:number; entity:string; entity_id:number; at:string}[]>([]);
  const [editSuggestion, setEditSuggestion] = useState<number>();
  const [suggestionValue, setSuggestionValue] = useState("");
  const [suggestionSkill, setSuggestionSkill] = useState<number>(0);
  const [verificationText, setVerificationText] = useState<Record<number,string>>({});
  const [name, setName] = useState("");
  const [summary, setSummary] = useState<{
    counts: Record<string, number>;
    llm_mode: string;
    database?: string;
    fixture_notice: string;
    embedding_status: string;
    missing_inputs: string[];
    responsibilities: string[];
  } | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [occupations, setOccupations] = useState<
    { id: number; canonical_id: string; name: string; source_version: string }[]
  >([]);
  const [skillLimit, setSkillLimit] = useState(50);
  const [neighbors, setNeighbors] = useState<{
    status: string;
    suggestions: {
      skill_id: number;
      name: string;
      similarity: number;
      verified: boolean;
    }[];
  } | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [cases, setCases] = useState<AgentCase[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [loadedApplicantId, setLoadedApplicantId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<
    { id: string; filename: string }[]
  >([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [checkedAt, setCheckedAt] = useState(Date.now);
  const [explanations, setExplanations] = useState<
    Record<number, { text: string; mode: string }>
  >({});
  const [outcomes, setOutcomes] = useState<Match[]>([]);
  const [eligibility, setEligibility] = useState<EligibilityNote[]>([]);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [skillView, setSkillView] = useState("catalog");
  const [selectedRound, setSelectedRound] = useState<number>(0);
  const [choices, setChoices] = useState<number[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState(0);
  const [question, setQuestion] = useState("");
  const [retrievalMode, setRetrievalMode] = useState("hybrid");
  const [policyAnswer, setPolicyAnswer] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [claim, setClaim] = useState({
    kind: "skill",
    value: "",
    skill_id: 0,
    excerpt: "",
    context: "mentioned",
  });
  const [profileSkillQuery, setProfileSkillQuery] = useState("");
  const [importText, setImportText] = useState("[]");
  const [editingListing, setEditingListing] = useState<number | null>(null);
  const [preview, setPreview] = useState<{
    rows: {
      row: number;
      valid: boolean;
      errors: string[];
      warnings: string[];
      record: unknown;
    }[];
    valid_count: number;
    error_count: number;
  } | null>(null);
  const [listingForm, setListingForm] = useState({ ...blankListing });
  const [policyForm, setPolicyForm] = useState({
    name: "",
    config:
      '{"coverage_confirmed":false,"scheme":null,"effective_date":null,"require_noc":false,"exclude_prior_participants":false}',
    document_ids: "",
  });
  const [docForm, setDocForm] = useState({
    title: "",
    scope: "",
    scheme: "",
    publisher: "",
    effective_date: "",
    version: "",
    source_url: "",
    section: "",
    content: "",
  });
  const [policyDocs, setPolicyDocs] = useState<
    {
      id: number;
      title: string;
      passages: { id: number; section: string; content: string }[];
    }[]
  >([]);
  const [roundName, setRoundName] = useState("");
  const activeRound = rounds.find((r) => r.id === selectedRound);
  const [capacity, setCapacity] = useState({
    listing_id: 0,
    seats: "",
    confirmation_reference: "",
  });
  const [evalLabels, setEvalLabels] = useState("[]");
  const [evaluation, setEvaluation] = useState<unknown>(null);
  const [catalogImport, setCatalogImport] = useState({
    source: "ESCO",
    version: "",
    rows: "[]",
  });
  const [skillEdit, setSkillEdit] = useState("");
  const [merge, setMerge] = useState({ source: "", target: "" });
  const [approved, setApproved] = useState<Record<number, boolean>>({});

  async function act(fn: () => Promise<void>, success?: string) {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      if (success) setNotice({ error: false, text: success });
    } catch (e) {
      setNotice({
        error: true,
        text: e instanceof Error ? e.message : "Action failed",
      });
    } finally {
      setBusy(false);
    }
  }
  async function reload(u = user) {
    if (!u) return;
    const [d, s, l, p, r, o] = await Promise.all([
      api<NonNullable<typeof summary>>("/dashboard"),
      api<{
        skills: Skill[];
        categories: string[];
        occupations?: typeof occupations;
      }>("/skills"),
      api<Listing[]>("/listings"),
      api<Policy[]>("/policies"),
      api<Round[]>("/rounds"),
      api<Match[]>("/outcomes"),
    ]);
    setSummary(d);
    setSkills(s.skills);
    setCategories(s.categories);
    setOccupations(s.occupations || []);
    setListings(l);
    setPolicies(p);
    setRounds(r);
    setOutcomes(o);
    setStaffStatus(await api("/staff/status"));
    if (u.role === "admin") {
      setStaffRequests(await api("/admin/staff/requests"));
      setAuditEvents(await api("/admin/audit"));
    }
    if ((u.role === "admin" || u.role === "placement") && selectedRound && r.some((item) => item.id === selectedRound && item.scope)) {
      setParticipantList(await api("/admin/rounds/" + selectedRound + "/participation"));
    }
    if (u.role === "applicant") {
      const [p, c, m] = await Promise.all([
        api<{
          profile: Profile;
          evidence: Evidence[];
          documents: typeof documents;
        }>("/applicant/profile"),
        api<AgentCase[]>("/agent/cases"),
        api<{ recommendations: Match[]; eligibility_notes: EligibilityNote[] }>(
          "/applicant/recommendations",
        ),
      ]);
      setProfile(p.profile);
      setEvidence(p.evidence);
      setDocuments(p.documents);
      setCases(c);
      setMatches(m.recommendations);
      setEligibility(m.eligibility_notes);
      setLoadedApplicantId(u.id);
    }
    if (u.role === "admin") {
      const [c, d, e, docs] = await Promise.all([
        api<AgentCase[]>("/agent/cases"),
        api<Draft[]>("/admin/drafts"),
        api<Evidence[]>("/admin/evidence"),
        api<typeof policyDocs>("/admin/policy-documents"),
      ]);
      setCases(c);
      setDrafts(d);
      setEvidence(e);
      setPolicyDocs(docs);
    }
  }
  useEffect(() => {
    if (sessionStorage.getItem("allocateai-v2-token"))
      api<User>("/auth/me")
        .then(setUser)
        .catch(() => {});
    const expired = () => {
      sessionStorage.removeItem("allocateai-v2-token");
      setUser(null);
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    setEvidence([]); setDocuments([]); setProfile(emptyProfile); setLoadedApplicantId(null); setStaffRequests([]);
    setMatches([]); setEligibility([]); setOutcomes([]); setDrafts([]); setExplanations({}); setCases([]);
    if (user) act(() => reload(user));
  }, [user]);
  useEffect(() => {
    setQ("");
    setCategory("");
  }, [page]);
  useEffect(() => {
    const timer = window.setInterval(() => setCheckedAt(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!mobile) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobile(false);
    };
    window.addEventListener("keydown", dismiss);
    return () => window.removeEventListener("keydown", dismiss);
  }, [mobile]);
  function isOpen(listing: Listing) {
    if (listing.status !== "open") return false;
    const age = checkedAt - Date.parse(listing.source_verified_at ?? "");
    return (!listing.source_verified_at || age <= 8 * 60 * 60 * 1000) &&
      (!listing.source_closes_at || Date.parse(listing.source_closes_at) > checkedAt);
  }
  const currentMatches = matches.filter((match) => !match.listing || isOpen(match.listing));
  const eligibilityReasons = [...new Set(eligibility.flatMap((note) => note.reasons))];
  const explorerListings = user?.role === "applicant" ? listings.filter(isOpen) : listings;
  const listingQuery = q.trim().toLowerCase();
  const filteredListings = explorerListings.filter((listing) =>
    (!listingQuery || [listing.title, listing.organization, listing.location, listing.source_name, listing.description, listing.requirements_text]
      .some((value) => value?.toLowerCase().includes(listingQuery))) &&
    (!category || listing.requirements.some((requirement) => requirement.skill_id === Number(category))),
  );
  function nav(key: string) {
    if (key !== page) window.scrollTo(0, 0);
    setPage(key);
    setMobile(false);
    setNotice(null);
  }
  const skillName = (id: number) =>
    skills.find((s) => s.id === id)?.name || `Skill ${id}`;
  const listingName = (id: number) =>
    listings.find((s) => s.id === id)?.title ||
    rounds.flatMap((round) => round.choice_listings ?? []).find((listing) => listing.id === id)?.title ||
    `Listing ${id}`;
  const selectRound = (id: number) => {
    setSelectedRound(id);
    setChoices(rounds.find((r) => r.id === id)?.choices || []);
    setParticipantList([]);
    if (id && (user?.role === "admin" || user?.role === "placement") && rounds.find(r=>r.id===id)?.scope)
      act(async () => setParticipantList(await api("/admin/rounds/" + id + "/participation")));
  };
  async function signIn(e: FormEvent) {
    e.preventDefault();
    await act(async () => {
      if (register)
        await api("/auth/register", "POST", {
          email,
          password,
          name,
          role: "applicant",
          activation_token: activationToken || null,
        });
      const r = await api<{ access_token: string; user: User }>(
        "/auth/login",
        "POST",
        { email, password },
      );
      sessionStorage.setItem("allocateai-v2-token", r.access_token);
      setUser(r.user);
      setPage("overview");
    });
  }
  async function exportDraft(id: number) {
    const response = await fetch(`/api/admin/drafts/${id}/export`, {
      headers: {
        Authorization: `Bearer ${sessionStorage.getItem("allocateai-v2-token")}`,
      },
    });
    if (!response.ok) throw new Error("Export failed");
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `allocation-${id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
  function scoreDetails(m: Match) {
    if (m.policy_version || m.utility !== undefined) {
      return <p>Submitted choice #{m.rank} · Rank utility {m.utility ?? "Unavailable"}</p>;
    }
    return (
      <div className="match-explanation">
        {user?.role === "applicant" && !m.policy_version && (
          <div className="spaced">
            <Button
              secondary
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const result = await api<{ text: string; mode: string }>(
                    `/applicant/matches/${m.listing_id}/explanation`,
                    "POST",
                  );
                  setExplanations({ ...explanations, [m.listing_id]: result });
                })
              }
            >
              Explain using verified facts
            </Button>
            {explanations[m.listing_id] && (
              <p>
                {explanations[m.listing_id].text}{" "}
                <Badge tone="neutral">{explanations[m.listing_id].mode}</Badge>
              </p>
            )}
          </div>
        )}
        <div className="score-total">
          <span>Match score</span>
          <strong>
            {m.score == null ? "Unknown" : m.score.toFixed(1) + " / 100"}
          </strong>
        </div>
        <p>Evidence coverage {Math.round((m.evidence_coverage ?? 0) * 100)}%
          {m.coverage_threshold_met === false ? " · Limited evidence" : ""}
        </p>
        {m.eligibility_status && <p>Eligibility needs authorized review.</p>}
        {!!m.unresolved_requirements?.length && <p>Unresolved requirements: {m.unresolved_requirements.join(", ")}</p>}
        {Object.entries(m.contributions || {}).map(([k, v]) => (
          <div className="explain-row" key={k}>
            <span>{k.replace("_", " / ")}</span>
            <b>
              {v === null ? "Unavailable · omitted" : `${v.toFixed(1)} pts`}
            </b>
          </div>
        ))}
        <p>
          Matched:{" "}
          {m.matched_skill_names?.join(", ") || m.matched_skills?.map(skillName).join(", ") ||
            "No accepted exact matches"}
        </p>
        <p>
          Skills absent from profile:{" "}
          {m.missing_skills?.map(skillName).join(", ") || "None"}
        </p>
        <p>
          Related, unverified:{" "}
          {m.related_unverified?.map(skillName).join(", ") || "None"}
        </p>
      </div>
    );
  }
  const menus =
    user?.role === "admin"
      ? [
          "overview",
          "listings",
          "skills",
          "imports",
          "policy",
          "agent",
          "rounds",
          "review",
          "results",
        ]
      : user?.role === "applicant"
        ? [
            "overview",
            "profile",
            "listings",
            "skills",
            "agent",
            "rounds",
            "policy",
            "results",
          ]
        : ["overview", "listings", "imports", "skills", "rounds", "results"];

  if (!user)
    return (
      <>
        <div className="login-page">
          <section className="login-story">
            <div className="brand light">
              <span className="brand-mark">
                <Network />
              </span>
              <span>
                Allocate<span className="brand-ai">AI</span>
              </span>
            </div>
            <div className="story-main">
              <h1>Find an internship<br /> that <em>fits.</em></h1>
              <p>Explore verified openings in India that match your field and skills.</p>
            </div>
          </section>
          <section className="login-form-area">
            <form className="login-form" onSubmit={signIn}>
              <span className="login-form-icon" aria-hidden="true"><GraduationCap size={23} /></span>
              <h2>
                {register ? "Create your account" : "Welcome back"}
              </h2>
              <p className="muted">
                {register
                  ? "Create an applicant profile to get internship matches."
                  : "Sign in to your AllocateAI workspace."}
              </p>
              {register && (
                <>
                  <Field label="Full name">
                    <input
                      required
                      value={name}
                      autoComplete="name"
                      onChange={(e) => setName(e.target.value)}
                    />
                  </Field>
                </>
              )}
              <Field label="Email">
                <input
                  type="email"
                  required
                  value={email}
                  autoComplete="email"
                  placeholder="you@example.com"
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              {register && (
                <details className="activation-details">
                  <summary>Have an activation token?</summary>
                  <Field label="Activation token">
                    <input value={activationToken} onChange={(e) => setActivationToken(e.target.value)} autoComplete="off" />
                  </Field>
                </details>
              )}
              <Field label="Password">
                <input
                  type="password"
                  required
                  minLength={register ? 10 : 1}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={register ? "new-password" : "current-password"}
                />
              </Field>
              <Button disabled={busy} type="submit">
                {busy
                  ? "Opening workspace…"
                  : register
                    ? "Create account"
                    : "Enter workspace"}
                <ArrowRight size={17} />
              </Button>
              <button
                type="button"
                className="text-button login-toggle"
                onClick={() => {
                  setRegister(!register);
                  setEmail("");
                  setPassword("");
                }}
              >
                {register
                  ? "Already have an account? Sign in"
                  : "Create an applicant account"}
              </button>
              <p className="login-privacy"><ShieldCheck size={15} /> You apply directly on the employer or portal site.</p>
            </form>
          </section>
        </div>
        {notice && (
          <div
            className={`global-notice ${notice.error ? "error" : ""}`}
            role={notice.error ? "alert" : "status"}
          >
            {notice.text}
            <button
              aria-label="Dismiss notification"
              onClick={() => setNotice(null)}
            >
              <X size={17} />
            </button>
          </div>
        )}
      </>
    );

  return (
    <div className="app-layout">
      <button
        className="mobile-toggle icon-btn"
        aria-label="Toggle navigation"
        aria-expanded={mobile}
        aria-controls="workspace-navigation"
        onClick={() => setMobile(!mobile)}
      >
        {mobile ? <X /> : <Menu />}
      </button>
      {mobile && (
        <div className="sidebar-scrim" onClick={() => setMobile(false)} />
      )}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <div className="brand light">
          <span className="brand-mark">
            <Network size={24} />
          </span>
          <span>
            Allocate<span className="brand-ai">AI</span>
          </span>
        </div>
        <div className="workspace-label">
          {user.role === "admin"
            ? "Placement administrator"
            : (user.role === "company" || user.role === "placement")
              ? "Industry partner"
              : "Applicant workspace"}
        </div>
        <nav id="workspace-navigation" aria-label="Workspace navigation">
          {menus.map((key) => {
            const Icon = icons[key];
            return (
              <button
                key={key}
                className={page === key ? "active" : ""}
                aria-current={page === key ? "page" : undefined}
                onClick={() => nav(key)}
              >
                <Icon size={18} />
                <span>{names[key]}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <button
            className="user-block"
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api("/auth/logout", "POST");
                sessionStorage.removeItem("allocateai-v2-token");
                setUser(null);
                setSummary(null);
              })
            }
          >
            <span className="avatar">{user.name[0]}</span>
            <span>
              <strong>{user.name}</strong>
              <small>Sign out</small>
            </span>
            <LogOut size={16} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            Workspace
            <span aria-hidden="true" className="breadcrumbs-slash">/</span>
            <strong>{names[page]}</strong>
          </div>
          {user.role !== "applicant" && <div>
            <Badge tone={summary?.llm_mode === "live" ? "green" : "amber"}>
              {summary?.llm_mode === "fixture"
                ? "Fixture mode · no live LLM"
                : summary ? "Live LLM configured" : "Loading workspace mode"}
            </Badge>
            <span>{summary?.database === "sqlite" ? "Local · SQLite" : summary?.database === "postgresql" ? "Local · PostgreSQL" : "Local workspace"}</span>
          </div>}
        </header>
        <main>
          <div className="page-heading">
            <div>
              <h1>{names[page]}</h1>
              {page === "overview" && staffStatus?.scope && user.role !== "applicant" && (
                <p>{staffStatus.scope}</p>
              )}
            </div>
            <Button
              secondary
              disabled={busy}
              onClick={() => act(() => reload())}
            >
              {busy ? "Working…" : "Refresh workspace"}
            </Button>
          </div>
          {notice && (
            <div
              className={`inline-notice ${notice.error ? "error" : ""}`}
              role={notice.error ? "alert" : "status"}
            >
              <span>{notice.text}</span>
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice(null)}
              >
                <X size={17} />
              </button>
            </div>
          )}

          {page === "overview" && (
            <>
              <section className="workspace-hero">
                <div className="workspace-hero-content">
                  <h2>{user.role === "applicant" ? <>Find your next<br /> <em>internship.</em></> : <>Manage internships<br /> and <em>allocations.</em></>}</h2>
                  <p>{user.role === "applicant" ? "Browse verified openings across India or get matches based on your profile." : "Review sourced internships and manage confirmed seats in your allocation rounds."}</p>
                  <div className="hero-actions">
                    <Button onClick={() => nav("listings")}>Explore internships <ArrowUpRight size={17} /></Button>
                    <Button secondary onClick={() => nav(user.role === "applicant" ? "profile" : "rounds")}>
                      {user.role === "applicant" ? "Edit my profile" : "View allocation rounds"}
                    </Button>
                  </div>
                </div>
              </section>
              <div className="metrics-grid">
                {(user.role === "applicant" ? [
                  { label: "Verified openings", value: loadedApplicantId === user.id ? explorerListings.length : undefined, icon: BriefcaseBusiness },
                  { label: "Your matches", value: loadedApplicantId === user.id ? currentMatches.length : undefined, icon: Sparkles },
                  { label: "Authorized rounds", value: summary ? rounds.length : undefined, icon: Users },
                  { label: "Published outcomes", value: summary ? outcomes.length : undefined, icon: CheckCircle2 },
                ] : [
                  { label: "Imported listings", value: summary?.counts.listings, icon: BriefcaseBusiness },
                  { label: "Participant profiles", value: summary?.counts.participants, icon: Users },
                  { label: "Canonical skills", value: summary?.counts.skills, icon: BookOpen },
                  { label: "Confirmed seat records", value: summary?.counts.confirmed_capacities, icon: ShieldCheck },
                ]).map(({label, value, icon: Icon}) => (
                  <div className="metric" key={label}>
                    <div className="metric-top">
                      <span>{label}</span>
                      <span className="metric-icon"><Icon size={18} /></span>
                    </div>
                    <strong>{value ?? "—"}</strong>
                  </div>
                ))}
              </div>
              <div className="dashboard-grid">
                {user.role === "applicant" ? <>
                  <section className="panel form-panel overview-panel">
                    <h2>Your internship matches</h2>
                    {loadedApplicantId !== user.id ? <p role="status">Loading internship matches…</p> : currentMatches.length ? (
                      <>
                        <ul className="overview-matches">
                          {currentMatches.slice(0, 3).map((match) => <li key={match.listing_id}>
                            <BriefcaseBusiness size={20} />
                            <span><strong>{match.listing?.title || listingName(match.listing_id)}</strong><small>{match.listing?.organization} · {match.listing?.location}</small></span>
                          </li>)}
                        </ul>
                        <Button secondary onClick={() => nav("listings")}>View all matches <ArrowRight size={16} /></Button>
                      </>
                    ) : <>
                      <p>No currently verified matching internships found.</p>
                      <Button secondary onClick={() => nav("profile")}>Update profile <ArrowRight size={16} /></Button>
                    </>}
                  </section>
                  <section className="panel form-panel overview-panel overview-side">
                    <span className="metric-icon"><ShieldCheck size={20} /></span>
                    <h2>Apply at the source</h2>
                    <p>Every verified opening links to its employer or authorized portal. Review their requirements before applying.</p>
                  </section>
                </> : <>
                  <section className="panel form-panel overview-panel">
                    <h2>Allocation readiness</h2>
                    {summary?.missing_inputs.length ? <ul className="readiness-list">
                      {summary.missing_inputs.map((item) => <li key={item}><ArrowUpRight size={17} /> {item}</li>)}
                    </ul> : <p>{summary ? "Review round eligibility and capacity confirmations before allocation." : "Loading workspace…"}</p>}
                  </section>
                  <section className="panel form-panel overview-panel overview-side">
                    <span className="metric-icon"><Settings2 size={20} /></span>
                    <h2>Workspace status</h2>
                    <p>{summary?.fixture_notice}</p>
                    <p>{summary?.embedding_status}</p>
                  </section>
                </>}
              </div>
              {user.role === "applicant" && <details className="panel form-panel workspace-access">
                <summary>Organization access</summary>
                {staffStatus?.requested && <p>Verification requested for {staffStatus.scope}.</p>}
                <div className="action-row">
                  <input aria-label="Organization name" placeholder="Organization name" value={staffScope} onChange={(e) => setStaffScope(e.target.value)} />
                  <input aria-label="Membership verification reference" placeholder="Verification reference" value={staffReference} onChange={(e) => setStaffReference(e.target.value)} />
                  <Button disabled={busy || staffScope.trim().length < 2 || staffReference.trim().length < 5}
                    onClick={() => act(async () => {await api("/staff/request","POST",{scope:staffScope,evidence_reference:staffReference}); await reload();},"Verification requested")}>Request staff access</Button>
                </div>
              </details>}
              {user.role === "admin" && staffRequests.length > 0 && <section className="panel form-panel spaced">
                <h2>Pending organization verification</h2>
                {staffRequests.map((request) => <div key={request.user_id} className="action-row">
                  <span>Account #{request.user_id} · {request.scope} · {request.reference}</span>
                  {(["company","placement"] as const).map((role)=><Button key={role}
                    onClick={() => act(async () => {
                      await api("/admin/staff/" + request.user_id, "PUT", {role,scope:request.scope,evidence_reference:request.reference}); await reload();
                    },"Access verified. The staff member must sign in again.")}>Verify {role}</Button>)}
                </div>)}
              </section>}
              {user.role === "admin" && auditEvents.length > 0 && <details className="panel form-panel spaced workspace-access">
                <summary>Recent administrative actions</summary>
                <ul>{auditEvents.map(e => <li key={e.id}>
                  {e.action.replaceAll("_"," ")} · {e.entity} #{e.entity_id} · Actor #{e.actor_id} · {new Date(e.at).toLocaleString()}
                </li>)}</ul>
              </details>}
            </>
          )}

          {page === "listings" && (
            <>
              {user.role === "applicant" && (
                <section className="panel form-panel match-panel">
                  <div className="match-panel-heading">
                    <span className="metric-icon"><Sparkles size={22} /></span>
                    <div>
                      <h2>Matching internships</h2>
                      <p className="muted">Based on your education, skills, and preferences.</p>
                    </div>
                    <div className="match-panel-actions">
                      <Button secondary onClick={() => nav("profile")}>Edit profile</Button>
                      <a className="btn secondary" href="#browse-openings">Browse all <ChevronDown size={15} /></a>
                    </div>
                  </div>
                  {loadedApplicantId !== user.id ? (
                    <p role="status">Loading internship matches…</p>
                  ) : currentMatches.length ? (
                    currentMatches.map((m) => (
                      <details className="pair-detail match-row" key={m.listing_id}>
                        <summary>
                          <span className="company-icon"><Building2 size={19} /></span>
                          <span className="match-title">
                            <strong>{m.listing?.title || listingName(m.listing_id)}</strong>
                            {m.listing && <small>{m.listing.organization} · {m.listing.location || "Location not published"}</small>}
                          </span>
                          <span className="match-fit">{m.score == null ? "Fit unknown" : m.score.toFixed(1) + " / 100"}</span>
                          <ChevronDown className="match-chevron" size={17} />
                        </summary>
                        {m.listing && <>
                          <div className="match-details">
                            <div className="action-row match-actions">
                              <a className="btn primary" href={m.listing.application_url || m.listing.source_url} target="_blank" rel="noreferrer">Apply on original site <ArrowUpRight size={15} /></a>
                              <span>{m.listing.source_name}</span>
                              {m.listing.source_verified_at && <span>Checked {new Date(m.listing.source_verified_at).toLocaleString()}</span>}
                              {m.listing.deadline && <span>Closes {m.listing.deadline}</span>}
                            </div>
                            <p className="listing-text">{m.listing.description}</p>
                            {m.listing.requirements_text && <>
                              <h3>Published requirements</h3>
                              <p className="listing-text">{m.listing.requirements_text}</p>
                            </>}
                          </div>
                        </>}
                        {scoreDetails(m)}
                      </details>
                    ))
                  ) : (
                    <Empty>
                      No currently verified matching internships found.
                    </Empty>
                  )}
                  {eligibilityReasons.length > 0 && (
                    <details className="eligibility-notes">
                      <summary>Eligibility and missing-evidence notes</summary>
                      <ul>{eligibilityReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                    </details>
                  )}
                </section>
              )}
              <div className="catalog-heading" id="browse-openings">
                <h2>{user.role === "applicant" ? "Browse verified openings" : "Browse listings"}</h2>
                {summary && <span>{filteredListings.length} {filteredListings.length === 1 ? "listing" : "listings"}</span>}
              </div>
              <div className="table-controls standalone listing-filters">
                <div className="search-box">
                  <Search size={17} />
                  <input
                    aria-label="Search internships"
                    placeholder="Role, employer, or location"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                  />
                </div>
                <select
                  aria-label="Filter by skill"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">All skills</option>
                  {skills.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              {!filteredListings.length ? (
                <section className="panel">
                  <Empty>
                    {explorerListings.length ? "No listings match these filters." : user.role === "applicant" ? "No verified openings are available to browse." : "Import a verified employer or placement-cell listing."}
                  </Empty>
                </section>
              ) : (
                <div className="internship-grid">
                  {filteredListings
                    .map((l) => (
                      <article className="panel internship-card" key={l.id}>
                        <div className="section-head">
                          <span className="company-icon"><Building2 size={22} /></span>
                          <Badge tone={l.status === "open" ? "green" : "amber"}>
                            {l.status === "open" ? <><CheckCircle2 size={13} /> Verified open</> : l.status}
                          </Badge>
                        </div>
                        <span className="eyebrow">
                          {l.organization} · {l.source_name}
                        </span>
                        <h2>{l.title}</h2>
                        <div className="job-meta">
                          <span>
                            <MapPin size={15} />
                            {l.location || "Location unknown"} ·{" "}
                            {l.work_mode || "Mode unknown"}
                          </span>
                          <span>{l.stipend || "Stipend not listed"}</span>
                        </div>
                        <details className="listing-disclosure">
                          <summary>Role details <ChevronDown size={16} /></summary>
                          <p className="listing-text">{l.description}</p>
                          {l.requirements_text && <p className="listing-text">{l.requirements_text}</p>}
                          <div className="chips">
                          {l.requirements.map((r, i) => (
                            <Badge
                              key={i}
                              tone={
                                r.classification === "required"
                                  ? "green"
                                  : "neutral"
                              }
                            >
                              {skillName(r.skill_id)} · {r.classification}
                            </Badge>
                          ))}
                          </div>
                        </details>
                        <p className="muted small">
                          Mandatory qualifications:{" "}
                          {l.mandatory_qualifications.join(", ") ||
                            "None stated"}
                          <br />
                          Verified: {l.last_verified || "Not verified"} ·
                          Deadline: {l.deadline || "Unknown"}
                        </p>
                        <div className="internship-foot">
                          <a
                            href={l.application_url || l.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Original application / source
                            <ArrowUpRight size={13} />
                          </a>
                          {user.role === "admin" && l.status === "unverified" && !l.source_provider && (
                            <div className="action-row">
                              <input aria-label={"Verification reference for " + l.title}
                                value={verificationText[l.id] || ""}
                                onChange={(e) => setVerificationText({...verificationText, [l.id]:e.target.value})}
                                placeholder="Source verification reference" />
                              <Button disabled={busy || (verificationText[l.id] || "").trim().length < 5}
                                onClick={() => act(async () => {
                                  await api("/admin/listings/" + l.id + "/approve", "POST",
                                    {expected_version:l.listing_version, verification_reference: verificationText[l.id]});
                                  await reload();
                                }, "Listing approved")}>Approve open listing</Button>
                            </div>
                          )}
                          {user.role === "applicant" && activeRound?.listing_ids.includes(l.id) && (
                            <Button
                              secondary
                              disabled={
                                choices.includes(l.id) ||
                                choices.length >= 5 ||
                                activeRound.frozen
                              }
                              onClick={() => setChoices([...choices, l.id])}
                            >
                              {choices.includes(l.id)
                                ? `Choice #${choices.indexOf(l.id) + 1}`
                                : "Add ranked choice"}
                            </Button>
                          )}
                          {user.role !== "applicant" && !l.source_provider && (
                            <Button
                              secondary
                              onClick={() => {
                                setEditingListing(l.id);
                                setPreview(null);
                                setImportText(
                                  JSON.stringify(
                                    [
                                      {
                                        ...l,
                                        id: undefined,
                                        owner_id: undefined,
                                        listing_version: undefined,
                                        declared_status: undefined,
                                        status: l.declared_status,
                                      },
                                    ],
                                    null,
                                    2,
                                  ),
                                );
                                nav("imports");
                              }}
                            >
                              Edit source fields
                            </Button>
                          )}
                        </div>
                      </article>
                    ))}
                </div>
              )}
            </>
          )}

          {page === "skills" && (
            <>
              <div className="tab-row">
                {[
                  ["catalog", "Catalog"],
                  ["gaps", "My Skill Gaps"],
                  ["demand", "Demand in Imported Listings"],
                ].map(([key, label]) => (
                  <Button
                    key={key}
                    secondary={skillView !== key}
                    onClick={() => setSkillView(key)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <div className="table-controls standalone">
                <div className="search-box">
                  <Search size={17} />
                  <input
                    aria-label="Search skills"
                    placeholder="Search canonical names or aliases…"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                  />
                </div>
                <select
                  aria-label="Skill category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">All categories</option>
                  {categories.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
              {skillView === "gaps" ? (
                user.role === "applicant" ? (
                  <section className="panel form-panel">
                    <h2>Gaps against imported roles</h2>
                    {matches.map((m) => (
                      <div className="pair-detail" key={m.listing_id}>
                        <strong>{listingName(m.listing_id)}</strong>
                        <p>
                          Missing required:{" "}
                          {m.missing_skills.map(skillName).join(", ") || "None"}
                        </p>
                        <p>
                          Related but unverified:{" "}
                          {m.related_unverified.map(skillName).join(", ") ||
                            "None"}
                        </p>
                      </div>
                    ))}
                    {!matches.length && (
                      <Empty>
                        Verified applicant evidence and real listings are needed
                        to calculate gaps.
                      </Empty>
                    )}
                  </section>
                ) : (
                  <section className="panel">
                    <Empty>
                      This view is personal to signed-in applicants.
                    </Empty>
                  </section>
                )
              ) : (
                <section className="panel">
                  <div className="section-head">
                    <div>
                      <h2>
                        {skillView === "demand"
                          ? "Demand measured from this workspace"
                          : "Canonical skill catalog"}
                      </h2>
                      <p className="muted small">
                        Imported ESCO/O*NET concepts retain their source
                        versions. Project-curated entries are labelled
                        separately. Occupational mappings are not proof of
                        Indian employer demand.
                      </p>
                    </div>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Canonical skill</th>
                          <th>Category / aliases</th>
                          <th>Provenance</th>
                          <th>Imported roles</th>
                          {user.role === "admin" && <th>Manage</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {skills
                          .filter(
                            (s) =>
                              (!q ||
                                [s.name, ...s.aliases]
                                  .join(" ")
                                  .toLowerCase()
                                  .includes(q.toLowerCase())) &&
                              (!category || category === s.category),
                          )
                          .sort((a, b) =>
                            skillView === "demand"
                              ? b.listing_count - a.listing_count
                              : 0,
                          )
                          .slice(0, skillLimit)
                          .map((s) => (
                            <tr key={s.id}>
                              <td>
                                <strong>{s.name}</strong>
                                <small>
                                  ID {s.id} · {s.canonical_id}
                                </small>
                                <button
                                  className="text-button"
                                  disabled={busy}
                                  onClick={() =>
                                    act(async () =>
                                      setNeighbors(
                                        await api(`/skills/${s.id}/related`),
                                      ),
                                    )
                                  }
                                >
                                  Related proposals
                                </button>
                              </td>
                              <td>
                                {s.category}
                                <small>
                                  {s.aliases.join(", ") || "No exact aliases"}
                                </small>
                              </td>
                              <td>
                                {s.source}
                                <small>
                                  v{s.source_version} ·{" "}
                                  {s.reviewed
                                    ? "Reviewed source"
                                    : "Pending review"}
                                </small>
                              </td>
                              <td>
                                {s.listing_count}
                                {s.listings && s.listings.length > 0 && (
                                  <details>
                                    <summary>Relevant roles</summary>
                                    {s.listings.map((l) => (
                                      <p key={l.id}>
                                        <a
                                          href={l.source_url}
                                          rel="noreferrer"
                                          target="_blank"
                                        >
                                          {l.title}
                                        </a>
                                      </p>
                                    ))}
                                  </details>
                                )}
                              </td>
                              {user.role === "admin" && (
                                <td>
                                  <Button
                                    secondary
                                    onClick={() => {
                                      setMerge({
                                        ...merge,
                                        source: String(s.id),
                                      });
                                      setSkillEdit(
                                        JSON.stringify(
                                          Object.fromEntries(
                                            Object.entries(s).filter(
                                              ([k]) =>
                                                ![
                                                  "id",
                                                  "listing_count",
                                                  "listings",
                                                  "merged_into",
                                                ].includes(k),
                                            ),
                                          ),
                                          null,
                                          2,
                                        ) + "\n",
                                      );
                                    }}
                                  >
                                    Edit #{s.id}
                                  </Button>
                                </td>
                              )}
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="panel-foot">
                    <span>
                      Showing up to {skillLimit} matches. Search covers the full
                      source catalog.
                    </span>
                    <Button
                      secondary
                      onClick={() => setSkillLimit(skillLimit + 100)}
                    >
                      Show 100 more
                    </Button>
                  </div>
                </section>
              )}
              {neighbors && (
                <section className="panel form-panel spaced">
                  <h2>Related concepts · unverified proposals</h2>
                  <p>{neighbors.status}</p>
                  <div className="chips">
                    {neighbors.suggestions.map((n) => (
                      <Badge key={n.skill_id} tone="neutral">
                        {n.name} · {n.similarity.toFixed(2)}
                      </Badge>
                    ))}
                  </div>
                  <p className="muted small">
                    Semantic proximity never becomes a verified skill. Supply
                    supporting evidence before adding a claim.
                  </p>
                </section>
              )}
              {occupations.length > 0 && (
                <section className="panel form-panel spaced">
                  <details>
                    <summary>
                      ESCO occupational reference concepts ·{" "}
                      {occupations.length} imported
                    </summary>
                    <p>
                      Source occupational mappings are reference data, not
                      measured Indian employer demand.
                    </p>
                    {occupations.map((o) => (
                      <p key={o.id}>
                        <a
                          href={o.canonical_id}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {o.name}
                        </a>
                        <small> · {o.source_version}</small>
                      </p>
                    ))}
                  </details>
                </section>
              )}
              {user.role === "admin" && (
                <section className="panel form-panel spaced">
                  <h2>Catalog corrections</h2>
                  <p className="muted small">
                    Edit an existing canonical entry by its ID, or add a new
                    reviewed curated concept. Exact merges update evidence and
                    listing references; related skills remain distinct.
                  </p>
                  <JsonBox
                    label="Skill fields (select Edit above or enter a new SkillInput record)"
                    value={skillEdit}
                    onChange={setSkillEdit}
                  />
                  <div className="action-row">
                    <input
                      aria-label="Skill ID to update"
                      placeholder="Skill ID for update"
                      value={merge.source}
                      onChange={(e) =>
                        setMerge({ ...merge, source: e.target.value })
                      }
                    />
                    <Button
                      disabled={busy || !skillEdit}
                      onClick={() =>
                        act(async () => {
                          await api(
                            merge.source
                              ? `/admin/skills/${merge.source}`
                              : "/admin/skills",
                            merge.source ? "PUT" : "POST",
                            JSON.parse(skillEdit),
                          );
                          await reload();
                        }, "Catalog saved")
                      }
                    >
                      Save catalog entry
                    </Button>
                  </div>
                  <div className="action-row spaced">
                    <input
                      aria-label="Merge target ID"
                      placeholder="Merge target skill ID"
                      value={merge.target}
                      onChange={(e) =>
                        setMerge({ ...merge, target: e.target.value })
                      }
                    />
                    <Button
                      secondary
                      disabled={busy || !merge.source || !merge.target}
                      onClick={() =>
                        act(async () => {
                          await api(
                            `/admin/skills/${merge.source}/merge/${merge.target}`,
                            "POST",
                          );
                          await reload();
                        }, "Exact duplicate merged")
                      }
                    >
                      Merge source into target
                    </Button>
                  </div>
                </section>
              )}
            </>
          )}

          {page === "profile" && user.role === "applicant" && loadedApplicantId !== user.id && (
            <section className="panel form-panel"><p role="status">Loading your profile…</p></section>
          )}
          {page === "profile" && user.role === "applicant" && loadedApplicantId === user.id && (
            <>
              <div className="two-columns align-start">
                <form
                  className="panel form-panel applicant-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    act(async () => {
                      await api("/applicant/profile", "PUT", profile);
                      await reload();
                    }, "Profile saved");
                  }}
                >
                  <h2>Your internship profile</h2>
                  <p className="muted">Enter your education and what you’re looking for.</p>
                  <div className="profile-fields">
                    {([['education', 'Education', 'e.g. B.Tech'], ['academic_branch', 'Academic branch', 'e.g. Mechanical Engineering'],
                      ['qualification', 'Qualification', ''], ['course', 'Course or trade', ''],
                      ['graduation_status', 'Graduation status', 'e.g. Final year'], ['preferred_role', 'Preferred internship role', ''] ] as const).map(([key, label, placeholder]) => (
                      <Field label={label} key={key}>
                        <input placeholder={placeholder} value={profile[key] ?? ""} onChange={(e) => setProfile({...profile, [key]: e.target.value || null})} />
                      </Field>
                    ))}
                  </div>
                  <h3 className="profile-section-heading">Location and work preferences</h3>
                  <div className="profile-fields">
                  <Field label="Home district">
                    <input
                      value={profile.district || ""}
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          district: e.target.value || null,
                        })
                      }
                    />
                  </Field>
                  <Field label="Home location">
                    <input
                      value={profile.home_location || ""}
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          home_location: e.target.value || null,
                        })
                      }
                    />
                  </Field>
                  <Field label="Preferred locations (comma separated)">
                    <input
                      value={profile.preferred_locations.join(",")}
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          preferred_locations: e.target.value
                            .split(",")
                            .filter(Boolean),
                        })
                      }
                    />
                  </Field>
                  <Field label="Preferred sectors (comma separated)">
                    <input
                      value={profile.preferred_sectors.join(",")}
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          preferred_sectors: e.target.value
                            .split(",")
                            .filter(Boolean),
                        })
                      }
                    />
                  </Field>
                  </div>
                  <fieldset className="work-modes">
                    <legend>Preferred work modes</legend>
                    {([['remote', 'Remote'], ['hybrid', 'Hybrid'], ['onsite', 'On-site']] as const).map(([mode, label]) => (
                      <label key={mode}>
                        <input type="checkbox" checked={profile.preferred_work_modes?.includes(mode) ?? false} onChange={(event) => {
                          const modes = profile.preferred_work_modes ?? [];
                          setProfile({...profile, preferred_work_modes: event.target.checked ? [...modes, mode] : modes.filter((entry) => entry !== mode)});
                        }} />
                        {label}
                      </label>
                    ))}
                  </fieldset>
                  <h3 className="profile-section-heading">Experience and consent</h3>
                  <div className="profile-fields">
                  {([["projects","Projects"],["certifications","Certifications"]] as const).map(([key,label]) => (
                    <Field label={label + " (comma separated)"} key={key}>
                      <input value={(profile[key] || []).join(",")} onChange={(e) => setProfile({...profile, [key]:e.target.value.split(",")})} />
                    </Field>
                  ))}
                  </div>
                  <Field label="Prior participation">
                    <select
                      value={
                        profile.prior_participation === null
                          ? "unknown"
                          : String(profile.prior_participation)
                      }
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          prior_participation:
                            e.target.value === "unknown"
                              ? null
                              : e.target.value === "true",
                        })
                      }
                    >
                      <option value="unknown">Not confirmed</option>
                      <option value="false">No</option>
                      <option value="true">Yes</option>
                    </select>
                  </Field>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={profile.willing_to_relocate}
                      onChange={(e) =>
                        setProfile({
                          ...profile,
                          willing_to_relocate: e.target.checked,
                        })
                      }
                    />
                    Willing to relocate (preferences alone do not restrict
                    eligibility)
                  </label>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={profile.consent}
                      onChange={(e) =>
                        setProfile({ ...profile, consent: e.target.checked })
                      }
                    />
                    I consent to use of my own authorized records for this
                    academic workspace.
                  </label>
                  <label className="checkbox"><input type="checkbox"
                    checked={profile.approved_hosted_resume_processing ?? false}
                    onChange={(e) => setProfile({...profile, approved_hosted_resume_processing:e.target.checked})} />
                    I authorize transfer of redacted resume text to the configured model provider for extraction.
                  </label>
                  <div className="profile-actions">
                    <Button secondary type="submit" disabled={busy}>Save profile</Button>
                    <Button disabled={busy} onClick={() => act(async () => {
                      await api("/applicant/profile", "PUT", profile);
                      await reload();
                      nav("listings");
                    })}>Find matching internships <ArrowRight size={16} /></Button>
                  </div>
                </form>
                <section className="panel form-panel">
                  <h2>Private résumé evidence</h2>
                  <p>
                    PDF or DOCX, under 10 MB. Unreadable documents support
                    manual entry. Raw documents stay private and out of activity
                    traces.
                  </p>
                  <Field label="Upload your résumé">
                    <input
                      type="file"
                      accept=".pdf,.docx"
                      disabled={busy || !profile.consent}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file)
                          act(async () => {
                            const form = new FormData();
                            form.append("file", file);
                            const result = await api<{
                              notice: string;
                              manual_entry_required: boolean;
                            }>("/applicant/documents", "POST", form);
                            await reload();
                            setNotice({
                              error: false,
                              text: result.manual_entry_required
                                ? "No extractable text. Enter evidence manually below."
                                : result.notice,
                            });
                          });
                      }}
                    />
                  </Field>
                  {documents.map((d) => (
                    <div className="action-row" key={d.id}>
                      <FileUp size={14} /> {d.filename}
                      <Button secondary disabled={busy} onClick={() => {
                        if (window.confirm("Delete this resume and its supported evidence?"))
                          act(async () => { await api("/applicant/documents/" + d.id, "DELETE"); await reload(); }, "Resume deleted");
                      }}>Delete resume</Button>
                    </div>
                  ))}
                  {evidence.filter((item) => item.document_id &&
                    ["suggested","needs_review","verified"].includes(item.status)).map((item) => (
                    <article className="pair-detail" key={item.id}>
                      <strong>{item.value}</strong> · Page {item.page}
                      <blockquote>{item.excerpt}</blockquote>
                      <div className="action-row">
                        {(["accept","reject"] as const).map((action) =>
                          <Button key={action} secondary disabled={busy} onClick={() => act(async () => {
                            await api("/applicant/suggestions/" + item.id, "POST", {action});
                            await reload();
                          }, "Suggestion updated")}>{action === "accept" ? "Accept suggestion" : "Reject suggestion"}</Button>)}
                        <Button secondary onClick={() => {setEditSuggestion(item.id); setSuggestionValue(item.value); setSuggestionSkill(item.skill_id || 0);}}>Edit suggestion</Button>
                      </div>
                      {editSuggestion === item.id && <div className="action-row">
                        {item.kind === "skill" ? <select aria-label="Corrected skill" value={suggestionSkill} onChange={(e) => setSuggestionSkill(Number(e.target.value))}>
                          <option value={0}>Select a skill</option>{skills.map((skill) => <option value={skill.id} key={skill.id}>{skill.name}</option>)}
                        </select> : <input aria-label="Corrected value" value={suggestionValue} onChange={(e) => setSuggestionValue(e.target.value)} />}
                        <Button disabled={busy || (item.kind === "skill" ? !suggestionSkill : !suggestionValue)}
                          onClick={() => act(async () => {
                            await api("/applicant/suggestions/" + item.id, "POST",
                              {action:"edit",value:suggestionValue,skill_id:item.kind === "skill" ? suggestionSkill : null});
                            setEditSuggestion(undefined);
                            await reload();
                          }, "Saved as self-reported evidence")}>Save correction</Button>
                      </div>}
                    </article>
                  ))}
                  <h3 className="spaced-title">
                    Manual confirmation / unreadable résumé
                  </h3>
                  <Field label="Evidence type">
                    <select
                      value={claim.kind}
                      onChange={(e) =>
                        setClaim({ ...claim, kind: e.target.value })
                      }
                    >
                      {[
                        "skill",
                        "qualification",
                        "project",
                        "certification",
                        "experience",
                        "participation",
                      ].map((k) => (
                        <option key={k}>{k}</option>
                      ))}
                    </select>
                  </Field>
                  {claim.kind === "skill" ? (
                    <>
                    <Field label="Search profile skills">
                      <input value={profileSkillQuery} onChange={(event) => setProfileSkillQuery(event.target.value)}
                        placeholder="Search skills or known aliases" />
                    </Field>
                    <Field label="Canonical skill">
                      <select
                        aria-label="Canonical skill"
                        value={claim.skill_id}
                        onChange={(e) =>
                          setClaim({
                            ...claim,
                            skill_id: Number(e.target.value),
                            value: skillName(Number(e.target.value)),
                          })
                        }
                      >
                        <option value={0}>Select a skill</option>
                        {skills.filter((s) => s.id === claim.skill_id ||
                          [s.name, ...s.aliases].some((term) => term.toLowerCase().includes(profileSkillQuery.toLowerCase().trim()))
                        ).slice(0, 150).map((s) => (
                          <option value={s.id} key={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    </>
                  ) : (
                    <Field label="Claim / held qualification">
                      <input
                        value={claim.value}
                        onChange={(e) =>
                          setClaim({ ...claim, value: e.target.value })
                        }
                      />
                    </Field>
                  )}
                  <Field label="Exact supporting statement">
                    <textarea
                      rows={3}
                      value={claim.excerpt}
                      onChange={(e) =>
                        setClaim({ ...claim, excerpt: e.target.value })
                      }
                      placeholder="Use a statement that actually supports this claim; a team mention does not establish a qualification."
                    />
                  </Field>
                  <Button
                    disabled={busy || !claim.value || (claim.kind !== "skill" && !claim.excerpt)}
                    onClick={() =>
                      act(async () => {
                        await api("/applicant/evidence", "POST", {
                          ...claim,
                          excerpt: claim.excerpt || "I report this skill in my profile.",
                          skill_id:
                            claim.kind === "skill" ? claim.skill_id : null,
                        });
                        await reload();
                      }, "Self-reported evidence saved")
                    }
                  >
                    Save to profile
                  </Button>
                  <div className="danger-zone">
                    <h3>Delete my uploaded and derived data</h3>
                    <p>
                      Removes documents, evidence, choices, agent checkpoints
                      and affected allocation drafts. Your login account
                      remains.
                    </p>
                    <Button
                      secondary
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Delete your uploaded documents and all derived applicant data?",
                          )
                        )
                          act(async () => {
                            await api("/applicant/data", "DELETE");
                            await reload();
                          }, "Private applicant data deleted");
                      }}
                    >
                      <Trash2 size={15} />
                      Delete my data
                    </Button>
                  </div>
                </section>
              </div>
              <section className="panel form-panel spaced">
                <h2>Evidence-backed profile</h2>
                {evidence.length ? (
                  evidence.map((e) => (
                    <div key={e.id} className="evidence-card">
                      <div className="section-head">
                        <h3>
                          {e.value} <small>· {e.kind}</small>
                        </h3>
                        <Badge
                          tone={e.status === "verified" ? "green" : "amber"}
                        >
                          {e.status}
                        </Badge>
                      </div>
                      <blockquote>{e.excerpt}</blockquote>
                      <small>
                        Page {e.page} · {e.source} · {e.context} · Evidence #
                        {e.id}
                      </small>
                    </div>
                  ))
                ) : (
                  <Empty>
                    Upload your résumé or enter a candidate confirmation. No
                    proficiency is inferred from a mention.
                  </Empty>
                )}
              </section>
            </>
          )}

          {page === "agent" && (
            <>
              <section className="panel form-panel">
                <h2>Evidence triage, with a durable place to pause</h2>
                <p>
                  The agent chooses from four approved tools. The deterministic
                  gate blocks unverified required evidence. No tool can assign
                  seats, alter policy or publish.
                </p>
                {user.role === "applicant" && (
                  <div className="action-row spaced">
                    <select
                      aria-label="Agent round"
                      value={selectedRound}
                      onChange={(e) => selectRound(Number(e.target.value))}
                    >
                      <option value={0}>
                        Recommendation triage (no allocation round)
                      </option>
                      {rounds.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label="Agent policy question"
                      placeholder="Optional policy question"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                    />
                    <select
                      aria-label="Agent policy version"
                      value={selectedPolicy}
                      onChange={(e) =>
                        setSelectedPolicy(Number(e.target.value))
                      }
                    >
                      <option value={0}>No policy question context</option>
                      {policies.map((p) => (
                        <option key={p.id} value={p.id}>
                          v{p.id} · {p.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          await api("/agent/cases", "POST", {
                            round_id: selectedRound || null,
                            policy_id: selectedPolicy || null,
                            policy_question: question,
                          });
                          await reload();
                        }, "Agent triage checkpoint saved")
                      }
                    >
                      Start evidence triage
                    </Button>
                  </div>
                )}
              </section>
              {cases.map((c) => (
                <section className="panel form-panel spaced" key={c.id}>
                  <div className="section-head">
                    <div>
                      <h2>Case {c.id.slice(0, 8)}</h2>
                      <small>
                        Participant #{c.applicant_id} · {c.mode} · Durable
                        thread {c.id}
                      </small>
                    </div>
                    <Badge tone={c.status === "ready" ? "green" : "amber"}>
                      {c.status}
                    </Badge>
                  </div>
                  {c.unresolved.map((u) => (
                    <p className="review-warning" key={u}>
                      {u}
                    </p>
                  ))}
                  <div className="timeline">
                    {c.activity.map((a) => (
                      <div key={a.id}>
                        <span className="timeline-dot" />
                        <div>
                          <strong>{a.tool}</strong>
                          <p>
                            {Object.entries(a.outcome)
                              .map(
                                ([k, v]) =>
                                  `${k.replaceAll("_", " ")}: ${JSON.stringify(v)}`,
                              )
                              .join(" · ")}
                          </p>
                          <small>Next: {a.next_action}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="muted small">
                    Next graph node: {c.next_nodes.join(", ") || "Completed"} ·
                    Hidden model reasoning and raw private inputs are not shown.
                  </p>
                  {user.role === "admin" && c.next_nodes.length > 0 && (
                    <Button
                      disabled={busy || c.unresolved.length > 0}
                      onClick={() =>
                        act(async () => {
                          await api(
                            `/admin/agent/cases/${c.id}/resume`,
                            "POST",
                          );
                          await reload();
                        }, "Same checkpoint resumed after authorized review")
                      }
                    >
                      Resume reviewed case
                    </Button>
                  )}
                </section>
              ))}
              {!cases.length && (
                <section className="panel spaced">
                  <Empty>
                    Start triage from an applicant account after entering
                    authorized evidence. Paused cases remain available after API
                    restart.
                  </Empty>
                </section>
              )}
            </>
          )}

          {page === "policy" && (
            <>
              <section className="panel form-panel">
                <div className="section-head">
                  <div>
                    <h2>Ask the evidence, keep the rules explicit</h2>
                    <p className="muted">
                      Retrieved policy passages explain. Only the versioned
                      admin-approved configuration constrains the solver.
                    </p>
                  </div>
                  <BookOpen size={24} />
                </div>
                <div className="action-row">
                  <select
                    aria-label="Policy search version"
                    value={selectedPolicy}
                    onChange={(e) => setSelectedPolicy(Number(e.target.value))}
                  >
                    <option value={0}>Select policy version</option>
                    {policies.map((p) => (
                      <option value={p.id} key={p.id}>
                        v{p.id} · {p.name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Retrieval method"
                    value={retrievalMode}
                    onChange={(e) => setRetrievalMode(e.target.value)}
                  >
                    <option value="keyword">Keyword only</option>
                    <option value="vector">Vector only</option>
                    <option value="hybrid">
                      Hybrid · reciprocal rank fusion
                    </option>
                  </select>
                </div>
                <Field label="Policy question">
                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="Ask a question supported by the imported policy version"
                  />
                </Field>
                <Button
                  disabled={busy || !selectedPolicy || question.length < 3}
                  onClick={() =>
                    act(async () =>
                      setPolicyAnswer(
                        await api("/policy/search", "POST", {
                          question,
                          policy_id: selectedPolicy,
                          mode: retrievalMode,
                        }),
                      ),
                    )
                  }
                >
                  Search policy evidence
                </Button>
                {policyAnswer && (
                  <div className="policy-answer">
                    <Badge tone={policyAnswer.supported ? "green" : "amber"}>
                      {policyAnswer.supported
                        ? "Extractive supporting passage"
                        : "Insufficient policy evidence"}
                    </Badge>
                    <p>{String(policyAnswer.answer)}</p>
                    <p className="muted small">
                      Actual mode: {String(policyAnswer.mode)} ·{" "}
                      {String(
                        policyAnswer.support_method || "No supported answer",
                      )}
                    </p>
                    {Array.isArray(policyAnswer.citations) &&
                      (
                        policyAnswer.citations as {
                          title: string;
                          section: string;
                          version: string;
                          effective_date: string;
                          url: string;
                          quote: string;
                        }[]
                      ).map((c, i) => (
                        <blockquote key={i}>
                          <p>{c.quote}</p>
                          <a target="_blank" rel="noreferrer" href={c.url}>
                            {c.title} · {c.section} · v{c.version} ·{" "}
                            {c.effective_date}
                          </a>
                        </blockquote>
                      ))}
                  </div>
                )}
              </section>
              <section className="panel form-panel spaced">
                <h2>Versioned allocation configurations</h2>
                {policies.map((p) => (
                  <details className="pair-detail" key={p.id}>
                    <summary>
                      v{p.id} · {p.name}
                      <Badge tone={p.approved_by ? "green" : "amber"}>
                        {p.approved_by ? "Admin approved" : "Not approved"}
                      </Badge>
                    </summary>
                    <pre>{JSON.stringify(p.config, null, 2)}</pre>
                    <p>
                      Explanatory documents:{" "}
                      {p.document_ids.join(", ") || "None linked"}
                    </p>
                    {user.role === "admin" && !p.approved_by && (
                      <Button
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            await api(
                              `/admin/policies/${p.id}/approve`,
                              "POST",
                            );
                            await reload();
                          }, "Exact policy configuration approved")
                        }
                      >
                        Approve configuration v{p.id}
                      </Button>
                    )}
                  </details>
                ))}
                {!policies.length && (
                  <Empty>
                    Create a versioned configuration. No official rules or
                    quotas are guessed from the hackathon brief.
                  </Empty>
                )}
              </section>
              {user.role === "admin" && (
                <>
                  <div className="two-columns align-start spaced">
                    <form
                      className="panel form-panel"
                      onSubmit={(e) => {
                        e.preventDefault();
                        act(async () => {
                          await api("/admin/policy-documents", "POST", {
                            title: docForm.title,
                            scope: docForm.scope,
                            scheme: docForm.scheme,
                            publisher: docForm.publisher,
                            effective_date: docForm.effective_date,
                            version: docForm.version,
                            source_url: docForm.source_url,
                            sections: { [docForm.section]: docForm.content },
                          });
                          await reload();
                        }, "Dated policy document imported");
                      }}
                    >
                      <h2>Import dated policy passages</h2>
                      {(
                        [
                          "title",
                          "scope",
                          "scheme",
                          "publisher",
                          "version",
                          "source_url",
                          "effective_date",
                          "section",
                        ] as const
                      ).map((k) => (
                        <Field key={k} label={k.replaceAll("_", " ")}>
                          <input
                            required
                            type={
                              k === "effective_date"
                                ? "date"
                                : k === "source_url"
                                  ? "url"
                                  : "text"
                            }
                            value={docForm[k]}
                            onChange={(e) =>
                              setDocForm({ ...docForm, [k]: e.target.value })
                            }
                          />
                        </Field>
                      ))}
                      <Field label="Exact section text">
                        <textarea
                          required
                          rows={8}
                          value={docForm.content}
                          onChange={(e) =>
                            setDocForm({ ...docForm, content: e.target.value })
                          }
                        />
                      </Field>
                      <Button disabled={busy} type="submit">
                        Import and index passages
                      </Button>
                    </form>
                    <form
                      className="panel form-panel"
                      onSubmit={(e) => {
                        e.preventDefault();
                        act(async () => {
                          await api("/admin/policies", "POST", {
                            name: policyForm.name,
                            config: JSON.parse(policyForm.config),
                            document_ids: policyForm.document_ids
                              .split(",")
                              .filter(Boolean)
                              .map(Number),
                          });
                          await reload();
                        }, "Unapproved policy version created");
                      }}
                    >
                      <h2>Create a new rule version</h2>
                      <p className="muted small">
                        Set a scheme and effective date when confirming rule coverage. Attach official sources for evidence requirements.
                      </p>
                      <Field label="Configuration name">
                        <input
                          required
                          value={policyForm.name}
                          onChange={(e) =>
                            setPolicyForm({
                              ...policyForm,
                              name: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Linked document IDs (comma separated)">
                        <input
                          value={policyForm.document_ids}
                          onChange={(e) =>
                            setPolicyForm({
                              ...policyForm,
                              document_ids: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <JsonBox
                        label="Explicit rule configuration"
                        value={policyForm.config}
                        onChange={(v) =>
                          setPolicyForm({ ...policyForm, config: v })
                        }
                      />
                      <Button disabled={busy} type="submit">
                        Create immutable version
                      </Button>
                      <h3 className="spaced-title">
                        Imported documents and passage IDs
                      </h3>
                      {policyDocs.map((d) => (
                        <details key={d.id}>
                          <summary>
                            #{d.id} {d.title}
                          </summary>
                          {d.passages.map((p) => (
                            <p key={p.id}>
                              Passage #{p.id} · {p.section}
                            </p>
                          ))}
                        </details>
                      ))}
                    </form>
                  </div>
                  <section className="panel form-panel spaced">
                    <h2>Retrieval evaluation · same questions, same corpus</h2>
                    <p>
                      Supply labelled relevant and supporting passage IDs.
                      Recall@5 excludes no-answer questions; abstention and
                      citation support are reported separately. Vector and
                      hybrid results are not claimed if embeddings are
                      unavailable.
                    </p>
                    <JsonBox
                      label="Labelled questions JSON"
                      value={evalLabels}
                      onChange={setEvalLabels}
                    />
                    <Button
                      disabled={busy}
                      onClick={() =>
                        act(async () =>
                          setEvaluation(
                            await api(
                              "/admin/evaluate/retrieval",
                              "POST",
                              JSON.parse(evalLabels),
                            ),
                          ),
                        )
                      }
                    >
                      Compare keyword / vector / hybrid
                    </Button>
                    {evaluation !== null && (
                      <pre className="spaced">
                        {JSON.stringify(evaluation, null, 2)}
                      </pre>
                    )}
                  </section>
                </>
              )}
            </>
          )}

          {page === "rounds" && (
            <>
              <section className="panel form-panel">
                <h2>Confirmed seats, explicitly ranked choices</h2>
                <p>
                  Unknown capacities never become assignments. Recommendation
                  mode remains available without a confirmed round.
                </p>
                <Field label="Active round">
                  <select
                    value={selectedRound}
                    onChange={(e) => selectRound(Number(e.target.value))}
                  >
                    <option value={0}>Select a round</option>
                    {rounds.map((r) => (
                      <option value={r.id} key={r.id}>
                        {r.name} · Policy v{r.policy_id}
                      </option>
                    ))}
                  </select>
                </Field>
                {selectedRound > 0 && (
                  <>
                    <div className="chips">
                      {rounds
                        .find((r) => r.id === selectedRound)
                        ?.capacities.map((c) => (
                          <Badge key={c.listing_id}>
                            {listingName(c.listing_id)} · {c.seats} confirmed
                            seats
                          </Badge>
                        ))}
                    </div>
                    {user.role === "applicant" ? (
                      <div className="spaced">
                        <h3>My top-five choices</h3>
                        {activeRound?.frozen && <p>Choices are closed for this round.</p>}
                        {choices.map((id, n) => (
                          <div className="choice-line" key={id}>
                            <b>{n + 1}</b>
                            <span>{listingName(id)}</span>
                            <button
                              aria-label={`Move choice ${n + 1} up`}
                              disabled={n === 0}
                              onClick={() => {
                                const next = [...choices];
                                [next[n - 1], next[n]] = [next[n], next[n - 1]];
                                setChoices(next);
                              }}
                            >
                              <ArrowUp size={16} />
                            </button>
                            <button
                              aria-label={`Move choice ${n + 1} down`}
                              disabled={n === choices.length - 1}
                              onClick={() => {
                                const next = [...choices];
                                [next[n + 1], next[n]] = [next[n], next[n + 1]];
                                setChoices(next);
                              }}
                            >
                              <ArrowDown size={16} />
                            </button>
                            <button
                              aria-label={`Remove choice ${n + 1}`}
                              onClick={() =>
                                setChoices(choices.filter((x) => x !== id))
                              }
                            >
                              <X size={16} />
                            </button>
                          </div>
                        ))}
                        <div className="action-row">
                          <select
                            aria-label="Add ranked internship"
                            value=""
                            onChange={(e) => {
                              if (e.target.value)
                                setChoices([
                                  ...choices,
                                  Number(e.target.value),
                                ]);
                            }}
                            disabled={choices.length >= 5 || activeRound?.frozen}
                          >
                            <option value="">Add an internship…</option>
                            {activeRound?.choice_listings
                              ?.filter((l) => !choices.includes(l.id) && l.status === "open")
                              .map((l) => (
                                <option key={l.id} value={l.id}>
                                  {l.title}
                                </option>
                              ))}
                          </select>
                          <Button
                            disabled={busy || activeRound?.frozen}
                            onClick={() =>
                              act(async () => {
                                await api(
                                  `/rounds/${selectedRound}/choices`,
                                  "PUT",
                                  { listing_ids: choices },
                                );
                                await reload();
                              }, "Ranked choices saved")
                            }
                          >
                            Save top-five choices
                          </Button>
                        </div>
                        <p className="muted small">
                          Choices are locked at freeze. Staff can review missing evidence before release.
                        </p>
                      </div>
                    ) : user.role === "admin" ? (
                      <p>Verified employer or placement staff must confirm the seats for this round.</p>
                    ) : (
                      <div className="spaced">
                        <h3>Confirm capacity for this specific round</h3>
                        {user.role === "placement" && !activeRound?.frozen && <Button secondary disabled={busy}
                          onClick={() => act(async () => {
                            await api("/admin/rounds/" + selectedRound + "/freeze", "POST"); await reload();
                          }, "Snapshot frozen")}>Freeze choices and seats</Button>}
                        <div className="action-row">
                          <select
                            aria-label="Capacity listing"
                            value={capacity.listing_id}
                            onChange={(e) =>
                              setCapacity({
                                ...capacity,
                                listing_id: Number(e.target.value),
                              })
                            }
                          >
                            <option value={0}>
                              Select owned / authorized listing
                            </option>
                            {listings.filter((l) => activeRound?.listing_ids.includes(l.id)).map((l) => (
                              <option key={l.id} value={l.id}>
                                {l.title}
                              </option>
                            ))}
                          </select>
                          <input
                            type="number"
                            min={0}
                            aria-label="Confirmed seats"
                            placeholder="Confirmed seats (no default)"
                            value={capacity.seats}
                            onChange={(e) =>
                              setCapacity({
                                ...capacity,
                                seats: e.target.value,
                              })
                            }
                          />
                        </div>
                        <Field label="Employer / placement-cell confirmation reference">
                          <input
                            value={capacity.confirmation_reference}
                            onChange={(e) =>
                              setCapacity({
                                ...capacity,
                                confirmation_reference: e.target.value,
                              })
                            }
                          />
                        </Field>
                        <Button
                          disabled={
                            busy ||
                            activeRound?.frozen || !capacity.listing_id ||
                            capacity.seats === "" ||
                            capacity.confirmation_reference.length < 5
                          }
                          onClick={() =>
                            act(async () => {
                              await api(
                                `/rounds/${selectedRound}/capacity`,
                                "PUT",
                                { ...capacity, seats: Number(capacity.seats) },
                              );
                              await reload();
                            }, "Capacity confirmed; prior draft approval is invalidated")
                          }
                        >
                          Confirm supplied seat count
                        </Button>
                      </div>
                    )}
                  </>
                )}
              </section>
              {selectedRound > 0 && activeRound?.scope && (user.role === "admin" || user.role === "placement") && (
                <section className="panel form-panel spaced">
                  <h2>Authorized participation</h2>
                  <p>Use the applicant account ID and the institution’s authorization reference.</p>
                  <div className="action-row">
                    <input aria-label="Applicant account ID" type="number" min={1} value={participantId} onChange={e=>setParticipantId(e.target.value)} />
                    <input aria-label="Participation evidence reference" value={participantReference} onChange={e=>setParticipantReference(e.target.value)} />
                    <Button disabled={busy || activeRound.frozen || !Number(participantId) || participantReference.trim().length < 5}
                      onClick={()=>act(async()=>{
                        await api("/admin/rounds/" + selectedRound + "/participation","PUT",{
                          applicant_id:Number(participantId),evidence_reference:participantReference
                        });
                        await reload();
                      },"Participation authorized")}>Authorize participant</Button>
                  </div>
                  {participantList.map(member=><div className="action-row" key={member.applicant_id}>
                    <span>Applicant #{member.applicant_id} · {member.choices_submitted ? "Choices submitted" : "Awaiting choices"}</span>
                    <Button secondary disabled={busy} onClick={()=>act(async()=>{
                      await api("/admin/rounds/" + selectedRound + "/participation/" + member.applicant_id,"DELETE"); await reload();
                    },"Participation revoked")}>Revoke grant</Button>
                  </div>)}
                </section>
              )}
              {(user.role === "admin" || user.role === "placement") && (
                <section className="panel form-panel spaced">
                  <h2>Create an allocation round</h2>
                  <Field label="Verified organization or institution scope">
                    <input value={user.role === "placement" ? staffStatus?.scope ?? "" : roundScope}
                      readOnly={user.role === "placement"} onChange={(e) => setRoundScope(e.target.value)} />
                  </Field>
                  <Field label="Verified open roles in this round">
                    <select multiple value={roundRoles.map(String)} onChange={(e) => setRoundRoles(Array.from(e.target.selectedOptions, o=>Number(o.value)))}>
                      {listings.filter(l=>l.status==="open").map(l=><option value={l.id} key={l.id}>{l.title} · {l.organization}</option>)}
                    </select>
                  </Field>
                  <div className="action-row">
                    <input
                      aria-label="Round name"
                      placeholder="Employer / placement-cell round name"
                      value={roundName}
                      onChange={(e) => setRoundName(e.target.value)}
                    />
                    <select
                      aria-label="Round policy version"
                      value={selectedPolicy}
                      onChange={(e) =>
                        setSelectedPolicy(Number(e.target.value))
                      }
                    >
                      <option value={0}>Approved policy version</option>
                      {policies
                        .filter((p) => p.approved_by)
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            v{p.id} · {p.name}
                          </option>
                        ))}
                    </select>
                    <Button
                      disabled={busy || !selectedPolicy || !roundName || !(user.role === "placement" ? staffStatus?.scope : roundScope) || !roundRoles.length}
                      onClick={() =>
                        act(async () => {
                          await api("/admin/rounds", "POST", {
                            name: roundName,
                            policy_id: selectedPolicy,
                            scope: user.role === "placement" ? staffStatus?.scope : roundScope,
                            listing_ids: roundRoles,
                          });
                          await reload();
                        }, "Round created")
                      }
                    >
                      Create round
                    </Button>
                  </div>
                  {user.role === "admin" && <div className="save-bar">
                    <p>
                      Allocation requires participant consent, top-five choices,
                      a frozen snapshot and confirmed seats.
                    </p>
                    <Button disabled={busy || !selectedRound} secondary onClick={() => act(async () => {
                      await api("/admin/rounds/" + selectedRound + (activeRound?.frozen ? "/reopen" : "/freeze"), "POST");
                      await reload();
                    }, activeRound?.frozen ? "Round reopened" : "Snapshot frozen")}>
                      {activeRound?.frozen ? "Reopen round" : "Freeze choices and seats"}
                    </Button>
                    <Button
                      disabled={busy || !activeRound?.frozen}
                      onClick={() =>
                        act(async () => {
                          await api(
                            `/admin/rounds/${selectedRound}/allocate`,
                            "POST",
                          );
                          await reload();
                          setPage("review");
                        }, "Draft created and paused for administrator approval")
                      }
                    >
                      Run CP-SAT allocation
                    </Button>
                  </div>}
                </section>
              )}
            </>
          )}

          {page === "review" && user.role === "admin" && (
            <>
              <section className="panel form-panel">
                <h2>Evidence review queue</h2>
                <p>
                  Verify the exact excerpt, not a plausible interpretation. A
                  mention of an ITI team is not an ITI qualification. Missing
                  evidence is unverified, not automatically a failed credential.
                </p>
                {evidence.map((e) => (
                  <div className="evidence-card" key={e.id}>
                    <div className="section-head">
                      <h3>
                        {e.value} · {e.kind}
                      </h3>
                      <Badge tone={e.status === "verified" ? "green" : "amber"}>
                        {e.status}
                      </Badge>
                    </div>
                    <blockquote>{e.excerpt}</blockquote>
                    <p className="muted small">
                      Participant #{e.applicant_id} · Evidence #{e.id} · Page{" "}
                      {e.page} · {e.source} · {e.context}
                    </p>
                    {e.kind === "qualification" && e.status !== "not_held" && (
                      <Button
                        secondary
                        disabled={busy}
                        onClick={() => {
                          const note = window.prompt(
                            "Explain the authorized confirmation that this qualification is not held. Rejecting an unsupported excerpt alone is insufficient.",
                          );
                          if (note)
                            act(async () => {
                              await api(
                                `/admin/evidence/${e.id}/review`,
                                "POST",
                                { status: "not_held", note },
                              );
                              await reload();
                            }, "Qualification confirmed not held, with an audit note");
                        }}
                      >
                        Confirm qualification not held
                      </Button>
                    )}
                    {e.status === "needs_review" && (
                      <div className="action-row">
                        <Button
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              await api(
                                `/admin/evidence/${e.id}/review`,
                                "POST",
                                { status: "verified" },
                              );
                              await reload();
                            }, "Supporting evidence verified")
                          }
                        >
                          Verify supported claim
                        </Button>
                        <Button
                          secondary
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              await api(
                                `/admin/evidence/${e.id}/review`,
                                "POST",
                                { status: "rejected" },
                              );
                              await reload();
                            }, "Unsupported claim rejected")
                          }
                        >
                          Reject claim
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
                {!evidence.length && (
                  <Empty>
                    Participant evidence will appear here. Raw documents remain
                    restricted to their owner and authorized admins.
                  </Empty>
                )}
              </section>
              <section className="spaced">
                <h2>Allocation drafts · independent checks before approval</h2>
                {drafts.map((d) => (
                  <article className="panel form-panel spaced" key={d.id}>
                    <div className="section-head">
                      <div>
                        <h2>
                          Draft #{d.id} · Policy v{d.policy_version}
                        </h2>
                        <small>
                          Round #{d.round_id} · Count stage {d.placement_status}
                        </small>
                      </div>
                      <div className="chips">
                        <Badge tone={d.publishable ? "green" : "amber"}>
                          {d.solver_status}
                        </Badge>
                        {d.stale && (
                          <Badge tone="red">Stale · rerun required</Badge>
                        )}
                        {d.published_at && <Badge>Published</Badge>}
                      </div>
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Measured outcome</th>
                            <th>CP-SAT</th>
                            <th>Greedy baseline</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[
                            "placed",
                            "seats",
                            "fill_rate",
                            "first_choice_rate",
                            "preference_utility",
                            "district_coverage",
                            "violations",
                          ].map((k) => (
                            <tr key={k}>
                              <td>{k.replaceAll("_", " ")}</td>
                              <td>{JSON.stringify(d.metrics[k])}</td>
                              <td>{JSON.stringify(d.baseline_metrics[k])}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="muted small">
                      {d.baseline_note} · No offer-acceptance data is collected.
                    </p>
                    {[...d.conflicts, ...d.deterministic_checks].map((c, i) => (
                      <p className="review-warning" key={i}>
                        {c}
                      </p>
                    ))}
                    <details className="spaced">
                      <summary>Inspect each outcome</summary>
                      {d.placements.map((m, i) => (
                        <details className="pair-detail" key={i}>
                          <summary>
                            {listingName(m.listing_id)} · Choice #{m.rank}
                            <Badge>Utility {m.utility ?? "—"}</Badge>
                          </summary>
                          {scoreDetails(m)}
                        </details>
                      ))}
                      {d.unassigned.map((u) => (
                        <p key={u.applicant_id}>
                          Participant #{u.applicant_id}: {u.reason}
                        </p>
                      ))}
                    </details>
                    <p className="digest">Exact draft digest: {d.digest}</p>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={approved[d.id] || false}
                        onChange={(e) =>
                          setApproved({ ...approved, [d.id]: e.target.checked })
                        }
                      />
                      I reviewed this exact draft, policy version, solver status
                      and deterministic checks.
                    </label>
                    <div className="action-row">
                      <Button
                        disabled={
                          busy ||
                          d.stale ||
                          !d.publishable ||
                          !approved[d.id] ||
                          !!d.approved_by
                        }
                        onClick={() =>
                          act(async () => {
                            await api(`/admin/drafts/${d.id}/approve`, "POST", {
                              approved: true,
                              digest: d.digest,
                            });
                            await reload();
                          }, "Exact draft approved; publication is a separate admin action")
                        }
                      >
                        {d.approved_by ? "Approved" : "Approve exact draft"}
                      </Button>
                      <Button
                        disabled={
                          busy ||
                          d.stale ||
                          !d.approved_by ||
                          !d.publishable ||
                          !!d.published_at
                        }
                        onClick={() =>
                          act(async () => {
                            await api(`/admin/drafts/${d.id}/publish`, "POST");
                            await reload();
                          }, "Internally reviewed results published")
                        }
                      >
                        Publish approved results
                      </Button>
                      <Button
                        secondary
                        onClick={() => act(() => exportDraft(d.id))}
                      >
                        Export permitted CSV
                      </Button>
                    </div>
                  </article>
                ))}
                {!drafts.length && (
                  <section className="panel spaced">
                    <Empty>
                      No confirmed-capacity allocation has been run. Real
                      allocation evaluation remains not run until authorized
                      data is supplied.
                    </Empty>
                  </section>
                )}
              </section>
            </>
          )}

          {page === "imports" && user.role !== "applicant" && (
            <>
              <div className="two-columns align-start">
                <form
                  className="panel form-panel"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setImportText(JSON.stringify([listingForm], null, 2));
                    act(async () =>
                      setPreview(
                        await api("/import/listings/preview", "POST", [
                          listingForm,
                        ]),
                      ),
                    );
                  }}
                >
                  <h2>Add a real source reference</h2>
                  <p>
                    Use a verified company or placement-cell record. Keep
                    unknown fields empty. Never distribute a notice’s total
                    seats across individual roles.
                  </p>
                  {(
                    [
                      "title",
                      "organization",
                      "source_name",
                      "source_url",
                      "location",
                      "sector",
                      "stipend",
                      "deadline",
                      "last_verified",
                    ] as const
                  ).map((k) => (
                    <Field key={k} label={k.replaceAll("_", " ")}>
                      <input
                        required={[
                          "title",
                          "organization",
                          "source_name",
                          "source_url",
                        ].includes(k)}
                        type={
                          k === "source_url"
                            ? "url"
                            : ["deadline", "last_verified"].includes(k)
                              ? "date"
                              : "text"
                        }
                        value={listingForm[k] || ""}
                        onChange={(e) =>
                          setListingForm({
                            ...listingForm,
                            [k]: e.target.value || null,
                          })
                        }
                      />
                    </Field>
                  ))}
                  <Field label="Work mode">
                    <select
                      value={listingForm.work_mode || ""}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          work_mode: (e.target.value || null) as null,
                        })
                      }
                    >
                      <option value="">Unknown</option>
                      {["onsite", "hybrid", "remote"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Listing status">
                    <select
                      value={listingForm.status}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          status: e.target.value,
                        })
                      }
                    >
                      {["unverified", "open", "expired"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  <label className="checkbox"><input type="checkbox" checked={listingForm.rolling}
                    onChange={(e) => setListingForm({...listingForm,rolling:e.target.checked})} />
                    The original source explicitly accepts rolling applications
                  </label>
                  <Field label="Original role description">
                    <textarea
                      required
                      rows={6}
                      value={listingForm.description}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          description: e.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label="Original requirements text">
                    <textarea
                      rows={4}
                      value={listingForm.requirements_text}
                      onChange={(e) =>
                        setListingForm({
                          ...listingForm,
                          requirements_text: e.target.value,
                        })
                      }
                    />
                  </Field>
                  <Button type="submit" disabled={busy}>
                    Preview source reference
                  </Button>
                </form>
                <section className="panel form-panel">
                  <h2>Import preview & provenance</h2>
                  <p>
                    Upload a placement-cell or employer CSV, or paste listing
                    records. Preview warnings and duplicate detection run again
                    at commit.
                  </p>
                  <Field label="Listing CSV">
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file)
                          act(async () => {
                            const f = new FormData();
                            f.append("file", file);
                            const p = await api<NonNullable<typeof preview>>(
                              "/import/listings/csv-preview",
                              "POST",
                              f,
                            );
                            setPreview(p);
                            setImportText(
                              JSON.stringify(
                                p.rows.map((r) => r.record),
                                null,
                                2,
                              ),
                            );
                          });
                      }}
                    />
                  </Field>
                  <JsonBox
                    label="Listing records JSON · required / preferred / mentioned classifications must cite source text"
                    value={importText}
                    onChange={setImportText}
                  />
                  <div className="action-row">
                    {editingListing !== null && (
                      <>
                        <Button
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              const records = JSON.parse(importText);
                              if (records.length !== 1)
                                throw new Error(
                                  "Listing edits require one source record",
                                );
                              await api(
                                `/listings/${editingListing}`,
                                "PUT",
                                records[0],
                              );
                              setEditingListing(null);
                              setPreview(null);
                              await reload();
                            }, "Listing corrections saved; previous allocation approvals are stale")
                          }
                        >
                          Save corrections to listing #{editingListing}
                        </Button>
                        <Button
                          secondary
                          onClick={() => {
                            setEditingListing(null);
                            setPreview(null);
                          }}
                        >
                          Switch to new import
                        </Button>
                      </>
                    )}
                    <Button
                      secondary
                      disabled={busy}
                      onClick={() =>
                        act(async () =>
                          setPreview(
                            await api(
                              "/import/listings/preview",
                              "POST",
                              JSON.parse(importText),
                            ),
                          ),
                        )
                      }
                    >
                      Validate preview
                    </Button>
                    <Button
                      disabled={busy || !preview || preview.error_count > 0}
                      onClick={() =>
                        act(async () => {
                          await api(
                            "/import/listings/commit",
                            "POST",
                            JSON.parse(importText),
                          );
                          setPreview(null);
                          await reload();
                        }, "Real source records imported")
                      }
                    >
                      Commit valid records
                    </Button>
                  </div>
                  {preview && (
                    <div className="import-preview spaced">
                      <Badge tone={preview.error_count ? "red" : "green"}>
                        {preview.valid_count} valid · {preview.error_count}{" "}
                        rejected
                      </Badge>
                      {preview.rows.map((r) => (
                        <div key={r.row}>
                          <h3>Row {r.row}</h3>
                          {r.errors.map((m, i) => (
                            <p className="review-warning" key={i}>
                              {m}
                            </p>
                          ))}
                          {r.warnings.map((m, i) => (
                            <p className="muted small" key={i}>
                              {m}
                            </p>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="muted small spaced">
                    Imports do not scrape login-only portals or submit external
                    applications. Capacity is confirmed separately for each
                    round.
                  </p>
                </section>
              </div>
              {user.role === "admin" && (
                <section className="panel form-panel spaced">
                  <h2>Import real ESCO / O*NET catalog records</h2>
                  <p>
                    Retain the original source version and canonical
                    identifiers. Use the included converter for official CSV/TSV
                    downloads. This catalog is distinct from actual listing
                    demand.
                  </p>
                  <div className="action-row">
                    <select
                      aria-label="Catalog source"
                      value={catalogImport.source}
                      onChange={(e) =>
                        setCatalogImport({
                          ...catalogImport,
                          source: e.target.value,
                        })
                      }
                    >
                      <option>ESCO</option>
                      <option>O*NET</option>
                      <option>curated</option>
                    </select>
                    <input
                      aria-label="Catalog source version"
                      placeholder="Original source version"
                      value={catalogImport.version}
                      onChange={(e) =>
                        setCatalogImport({
                          ...catalogImport,
                          version: e.target.value,
                        })
                      }
                    />
                  </div>
                  <JsonBox
                    label="Original source rows JSON"
                    value={catalogImport.rows}
                    onChange={(v) =>
                      setCatalogImport({ ...catalogImport, rows: v })
                    }
                  />
                  <Button
                    disabled={busy || !catalogImport.version}
                    onClick={() =>
                      act(async () => {
                        await api("/admin/skills/import", "POST", {
                          ...catalogImport,
                          rows: JSON.parse(catalogImport.rows),
                        });
                        await reload();
                      }, "Source-versioned skills imported")
                    }
                  >
                    Import catalog records
                  </Button>
                </section>
              )}
            </>
          )}

          {page === "imports" && user.role === "admin" && (
            <section className="panel form-panel spaced">
              <h2>Authorized participant import</h2>
              <p>
                Use only placement-cell records with participant consent.
                Imported evidence always requires review. One-time activation
                tokens are returned only to this administrator; each participant
                sets their own password.
              </p>
              <JsonBox
                label="Authorized participant profiles JSON"
                value={participantImport}
                onChange={setParticipantImport}
              />
              <Button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    setParticipantImportResult(
                      await api(
                        "/admin/participants/import",
                        "POST",
                        JSON.parse(participantImport),
                      ),
                    );
                    await reload();
                  }, "Authorized participant records imported")
                }
              >
                Import authorized participants
              </Button>
              {participantImportResult !== null && (
                <details className="spaced">
                  <summary>
                    Private import result and one-time activation tokens
                  </summary>
                  <pre>{JSON.stringify(participantImportResult, null, 2)}</pre>
                  <p className="muted small">
                    Share only each participant's own token through an
                    authorized channel. Do not include tokens in screenshots or
                    benchmark exports.
                  </p>
                </details>
              )}
            </section>
          )}
          {page === "results" && (
            <section className="panel form-panel">
              <h2>Published internal outcomes</h2>
              <p>
                Only administrator-approved results are visible. These are
                internal academic allocations, not official offers or external
                applications.
              </p>
              {outcomes.length ? (
                outcomes.map((m, i) => (
                  <details className="pair-detail" key={i}>
                    <summary>
                      {m.listing?.title || "No placement"}
                      <Badge tone={m.outcome === "placed" ? "green" : "amber"}>
                        {m.outcome}
                      </Badge>
                    </summary>
                    <p>
                      Policy v{m.policy_version} · Solver {m.solver_status}
                    </p>
                    <p>{m.explanation || m.reason}</p>
                    {m.outcome === "placed" && scoreDetails(m)}
                  </details>
                ))
              ) : (
                <Empty>
                  No published authorized outcomes. Recommendations are
                  available separately without assigning a seat.
                </Empty>
              )}
            </section>
          )}
        </main>
        <footer className="app-footer">
          <span>AllocateAI · Independent academic project</span>
        </footer>
      </div>
    </div>
  );
}

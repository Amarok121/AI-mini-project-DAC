/**
 * 백엔드 `chart_data`(Report ChartData) → UI용 score / 클레임 / 로드맵 뷰 모델.
 */

type Level = "HIGH" | "MED" | "LOW" | string;

export type ScoreBar = { label: string; value: number; level?: Level };

/** `ScoreSummary.vue`와 동일한 props 형태 */
export type ScoreSummaryView = {
  trl?: string;
  mrl?: string;
  cri?: string;
  trl_level?: Level;
  mrl_level?: Level;
  cri_level?: Level;
  bars?: ScoreBar[];
};

export type RoadmapStepView = { title: string; description?: string; status?: string };

export type ApiScoreItem = {
  value: number | null;
  min: number;
  max: number;
  label: string;
  rationale?: string;
};

export type ApiClaimVerdict = {
  claim_id?: string;
  claim_text: string;
  verdict: string;
  confidence: number;
  scientific_confidence?: number | null;
  industrial_confidence?: number | null;
  regulatory_confidence?: number | null;
};

export type ApiRoadmapStep = {
  step: number;
  phase: string;
  trl_range: string;
  mrl_range: string;
  description: string;
};

export type ApiChartData = {
  score_summary?: {
    trl: ApiScoreItem;
    mrl: ApiScoreItem;
    cri: ApiScoreItem;
  };
  claim_verdicts?: ApiClaimVerdict[];
  roadmap_steps?: ApiRoadmapStep[];
};

type Grade = "HIGH" | "MED" | "LOW" | string;

function pct(value: number | null | undefined, max: number): number {
  if (value == null || !Number.isFinite(value) || max <= 0) return 0;
  return Math.round(Math.max(0, Math.min(100, (value / max) * 100)));
}

function gradeToLevel(g?: string | null): Grade {
  const v = (g ?? "").toUpperCase();
  if (v === "HIGH") return "HIGH";
  if (v === "MED") return "MED";
  if (v === "LOW") return "LOW";
  return "MED";
}

function floatToLevel(x: number): Grade {
  if (x >= 0.66) return "HIGH";
  if (x >= 0.33) return "MED";
  return "LOW";
}

function formatScoreLine(prefix: string, item: ApiScoreItem): string {
  if (item.value != null && Number.isFinite(item.value)) {
    return `${prefix} ${item.value}/${item.max} · ${item.label}`;
  }
  return item.label || "—";
}

type SciLike = { overall_grade?: string; confidence?: string; trl_estimate?: string };
type IndLike = { overall_level?: string; mrl_estimate?: string };
type RegLike = { confidence?: string; cri_estimate?: string };

/**
 * API `chart_data`와 에이전트 요약 문자열을 합쳐 ScoreSummary 카드 + 막대 값을 만든다.
 */
export function scoreSummaryFromChart(
  chart: ApiChartData | null | undefined,
  scientific?: SciLike | null,
  industrial?: IndLike | null,
  regulatory?: RegLike | null
): ScoreSummaryView | undefined {
  const ss = chart?.score_summary;
  if (ss?.trl && ss?.mrl && ss?.cri) {
    const trlLv = gradeToLevel(scientific?.overall_grade ?? scientific?.confidence);
    const mrlLv = gradeToLevel(industrial?.overall_level);
    const criLv = gradeToLevel(regulatory?.confidence);
    return {
      trl: scientific?.trl_estimate?.trim() || formatScoreLine("TRL", ss.trl),
      mrl: industrial?.mrl_estimate?.trim() || formatScoreLine("MRL", ss.mrl),
      cri: regulatory?.cri_estimate?.trim() || formatScoreLine("CRI", ss.cri),
      trl_level: trlLv,
      mrl_level: mrlLv,
      cri_level: criLv,
      bars: [
        { label: "Scientific (TRL)", value: pct(ss.trl.value, ss.trl.max), level: trlLv },
        { label: "Industrial (MRL)", value: pct(ss.mrl.value, ss.mrl.max), level: mrlLv },
        { label: "Regulatory (CRI)", value: pct(ss.cri.value, ss.cri.max), level: criLv }
      ]
    };
  }

  if (!scientific && !industrial && !regulatory) return undefined;

  const trl = scientific?.trl_estimate ?? "—";
  const mrl = industrial?.mrl_estimate ?? "—";
  const cri = regulatory?.cri_estimate ?? "—";
  const trlLv = gradeToLevel(scientific?.overall_grade ?? scientific?.confidence);
  const mrlLv = gradeToLevel(industrial?.overall_level);
  const criLv = gradeToLevel(regulatory?.confidence);

  return {
    trl,
    mrl,
    cri,
    trl_level: trlLv,
    mrl_level: mrlLv,
    cri_level: criLv,
    bars: [
      { label: "Scientific", value: trlLv === "HIGH" ? 72 : trlLv === "MED" ? 48 : 24, level: trlLv },
      { label: "Industrial", value: mrlLv === "HIGH" ? 72 : mrlLv === "MED" ? 48 : 24, level: mrlLv },
      { label: "Regulatory", value: criLv === "HIGH" ? 72 : criLv === "MED" ? 48 : 24, level: criLv }
    ]
  };
}

export type ClaimVerdictRow = {
  claim: string;
  verdict: string;
  credibility?: Grade;
  confidence_pct?: number;
  flags?: string[];
};

export function claimRowsFromChart(chart: ApiChartData | null | undefined): ClaimVerdictRow[] {
  const rows = chart?.claim_verdicts;
  if (!rows?.length) return [];
  return rows.map((cv) => ({
    claim: cv.claim_text || cv.claim_id || "—",
    verdict: cv.verdict || "—",
    credibility: floatToLevel(Number(cv.confidence) || 0),
    confidence_pct: Math.round(Math.max(0, Math.min(100, (cv.confidence ?? 0) * 100))),
    flags: []
  }));
}

function roadmapStatus(i: number, total: number): string {
  if (i === 0) return "DONE";
  if (i === 1) return "NEXT";
  if (i < total - 1) return "MED";
  return "RISK";
}

export function roadmapFromChart(chart: ApiChartData | null | undefined): RoadmapStepView[] {
  const steps = chart?.roadmap_steps;
  if (!steps?.length) return [];
  const n = steps.length;
  return steps.map((s, i) => ({
    title: `${s.phase} · TRL ${s.trl_range} / MRL ${s.mrl_range}`,
    description: s.description,
    status: roadmapStatus(i, n)
  }));
}

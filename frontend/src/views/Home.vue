<template>
  <main class="container">
    <div class="layout">
      <!-- Left Panel -->
      <section class="card">
        <div class="card-header">
          <div>
            <div style="font-weight: 900">검증 요청 입력</div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px">
            <button
              class="btn"
              style="padding: 8px 10px; font-size: 12px"
              @click="toggleDevMode"
              :title="devMode ? 'Dev Preview 끄기' : 'Dev Preview 켜기'"
            >
              {{ devMode ? "Dev: ON" : "Dev: OFF" }}
            </button>
            <span class="badge neutral">Draft</span>
          </div>
        </div>

        <div class="card-body" style="display: flex; flex-direction: column; gap: 14px">
          <div class="tabs">
            <button class="tab" :class="{ active: inputMode === 'text' }" @click="inputMode = 'text'">
              텍스트 입력
            </button>
            <button class="tab" :class="{ active: inputMode === 'pdf' }" @click="inputMode = 'pdf'">
              PDF 업로드
            </button>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
            <div class="field">
              <label>언어</label>
              <select v-model="language">
                <option value="ko">한국어 (Korean)</option>
                <option value="en">English</option>
              </select>
            </div>
            <div class="field">
              <label>도메인</label>
              <select v-model="domain">
                <option value="climate">기후/탄소</option>
                <option value="it">IT / Software</option>
                <option value="bio">Bio / Medical</option>
                <option value="mfg">Manufacturing</option>
              </select>
            </div>
          </div>

          <div v-if="inputMode === 'text'" class="field" style="flex: 1">
            <div class="label-row">
              <label>검증 대상 텍스트</label>
              <span class="hint">{{ text.length.toLocaleString() }} / 20,000</span>
            </div>
            <textarea v-model="text" maxlength="20000" placeholder="여기에 검증할 기술 설명이나 클레임을 입력하세요..." />
          </div>
          <div v-else class="field">
            <label>PDF 업로드</label>
            <input type="file" accept="application/pdf" @change="onPickPdf" />
            <div class="hint" v-if="pdfFile">{{ pdfFile.name }} ({{ Math.round(pdfFile.size / 1024) }}KB)</div>
            <div class="hint" v-else>PDF 워크플로는 다음 단계에서 백엔드 업로드를 붙일 예정입니다.</div>
          </div>

          <div class="error" v-if="errorMsg">{{ errorMsg }}</div>
        </div>

        <div class="actions">
          <button class="btn" @click="clearAll" :disabled="isLoading">Clear</button>
          <button class="btn primary" @click="confirm" :disabled="isLoading || !canSubmit">
            {{ isLoading ? "분석 중..." : "Confirm & Analyze" }}
          </button>
        </div>
      </section>

      <!-- Right Panel -->
      <section style="display: flex; flex-direction: column; gap: 16px; min-width: 0">
        <!-- Executive Summary -->
        <div class="card">
          <div class="card-header">
            <div style="display: flex; align-items: center; gap: 10px">
              <span style="font-weight: 900; color: var(--text-strong)">결과 요약</span>
            </div>
            <div style="display: flex; gap: 8px">
              <button class="icon-btn" title="Download" :disabled="!result">⭳</button>
              <button class="icon-btn" title="Share" :disabled="!result">⤴</button>
            </div>
          </div>
          <div class="card-body">
            <div v-if="!result" class="hint">아직 결과가 없습니다. 왼쪽에서 입력 후 Confirm을 누르세요.</div>
            <div v-else class="split-row">
              <div style="flex: 1; min-width: 0">
                <div style="font-size: 12px; font-weight: 900; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase">
                  최종 판단
                </div>
                <div class="summary-text" style="margin-top: 8px">
                  {{ summaryText }}
                </div>
                <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap">
                  <span class="badge neutral">Verdict: {{ result.cross_validation?.overall_verdict ?? "—" }}</span>
                  <span class="badge" :class="badgeClass(result.scientific?.overall_grade)">Scientific: {{ result.scientific?.overall_grade ?? "—" }}</span>
                  <span class="badge" :class="badgeClass(result.regulatory?.confidence)"
                    >Regulatory: {{ result.regulatory?.verdict ?? "—" }} ({{ result.regulatory?.confidence ?? "—" }})</span
                  >
                </div>
              </div>

              <div class="divider-v" />

              <div style="flex: 0.95; min-width: 0">
                <ScoreSummary :score-summary="result.score_summary" />
              </div>
            </div>
          </div>
        </div>

        <!-- Claim verdicts / Cross validation -->
        <div class="card">
          <div class="card-header" style="justify-content: flex-start; gap: 14px">
            <button class="tab" :class="{ active: rightTab === 'claims' }" style="flex: 0 0 auto" @click="rightTab = 'claims'">
              Cross Validation
            </button>
            <button class="tab" :class="{ active: rightTab === 'report' }" style="flex: 0 0 auto" @click="rightTab = 'report'">
              Detailed Report
            </button>
          </div>
          <div class="card-body">
            <div v-if="!result" class="hint">결과가 생성되면 클레임 판정/보고서가 표시됩니다.</div>
            <div v-else>
              <div v-if="rightTab === 'claims'" style="display: flex; flex-direction: column; gap: 12px">
                <div v-if="result.claim_verdicts?.length" style="display: flex; flex-direction: column; gap: 12px">
                  <div v-for="(cv, i) in result.claim_verdicts" :key="i" class="card" style="border-radius: 10px">
                    <div class="card-body" style="display: grid; grid-template-columns: 1.2fr 0.9fr 0.9fr; gap: 14px">
                      <div>
                        <div class="hint" style="font-weight: 800; letter-spacing: 0.06em">CLAIM</div>
                        <div style="margin-top: 6px; font-weight: 800; color: var(--text)">{{ cv.claim }}</div>
                      </div>
                      <div>
                        <div class="hint" style="font-weight: 800; letter-spacing: 0.06em">VERDICT</div>
                        <div style="margin-top: 6px">{{ cv.verdict }}</div>
                      </div>
                      <div>
                        <div class="hint" style="font-weight: 800; letter-spacing: 0.06em">CONFIDENCE</div>
                        <div style="margin-top: 6px">
                          <ConfidenceGauge :pct="cv.confidence_pct ?? 50" :level="cv.credibility" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else class="hint">claim_verdicts가 아직 없어서, 기존 claims/cross_validation 기반 표시로 대체 예정입니다.</div>
              </div>

              <div v-else>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 10px">
                  <button class="btn" @click="copyReport">Copy</button>
                </div>
                <div class="mono card" style="padding: 12px; border-radius: 10px; max-height: 520px; overflow: auto">
                  {{ result.report_markdown }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Evidence Cards -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
          <div class="card">
            <div class="card-header">
              <div style="font-weight: 900">Scientific Papers</div>
              <span class="hint">{{ result?.scientific?.papers?.length ?? 0 }} Sources</span>
            </div>
            <div class="card-body" style="display: flex; flex-direction: column; gap: 10px">
              <div v-if="!result" class="hint">결과가 생성되면 논문 출처가 표시됩니다.</div>
              <div v-else-if="!result.scientific?.papers?.length" class="hint">논문 항목이 없습니다.</div>
              <div v-else v-for="(p, idx) in result.scientific.papers.slice(0, 6)" :key="idx" class="card" style="border-radius: 10px">
                <div class="card-body" style="display: flex; flex-direction: column; gap: 6px">
                  <div style="display: flex; justify-content: space-between; gap: 10px; align-items: start">
                    <span class="hint" style="font-weight: 800">{{ p.journal || "—" }}<span v-if="p.year">, {{ p.year }}</span></span>
                    <span class="badge" :class="badgeClass(p.grade_level)">GRADE: {{ p.grade_level }}</span>
                  </div>
                  <div style="font-weight: 900">{{ p.title }}</div>
                  <a v-if="p.url" :href="p.url" target="_blank" rel="noreferrer" class="hint">링크 열기</a>
                </div>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-header">
              <div style="font-weight: 900">News & Regulations</div>
              <span class="hint">{{ result?.regulatory?.source_urls?.length ?? 0 }} Sources</span>
            </div>
            <div class="card-body" style="display: flex; flex-direction: column; gap: 10px">
              <div v-if="!result" class="hint">결과가 생성되면 규제 출처가 표시됩니다.</div>
              <div v-else>
                <div class="hint">
                  Verdict: <strong>{{ result.regulatory?.verdict }}</strong> ({{ result.regulatory?.confidence }})
                </div>
                <div v-if="result.regulatory?.evidence_summary" class="hint">{{ result.regulatory.evidence_summary }}</div>
                <ul v-if="result.regulatory?.source_urls?.length" style="margin: 0; padding-left: 18px">
                  <li v-for="(u, i) in result.regulatory.source_urls.slice(0, 6)" :key="i" class="hint">
                    <a :href="u" target="_blank" rel="noreferrer">{{ u }}</a>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Roadmap -->
        <div class="card">
          <div class="card-header">
            <div style="font-weight: 900">Roadmap</div>
          </div>
          <div class="card-body">
            <RoadmapTimeline :steps="result?.roadmap_steps" />
          </div>
        </div>

        <!-- Dev JSON Inspector -->
        <div class="card" v-if="devMode">
          <div class="card-header">
            <div style="font-weight: 900">Dev Inspector</div>
            <span class="hint">UI 확인용 mock 데이터</span>
          </div>
          <div class="card-body">
            <div class="mono card" style="padding: 12px; border-radius: 10px; max-height: 360px; overflow: auto">
              {{ devJson }}
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import ScoreSummary, { type ScoreSummary as ScoreSummaryT } from "../components/ScoreSummary.vue";
import ConfidenceGauge from "../components/ConfidenceGauge.vue";
import RoadmapTimeline, { type RoadmapStep } from "../components/RoadmapTimeline.vue";

type Grade = "HIGH" | "MED" | "LOW" | string;
type Verdict = "해당" | "미해당" | "불명확" | string;

type PaperEvidence = {
  title: string;
  authors: string[];
  year: number;
  journal?: string;
  url: string;
  grade_score: number;
  grade_level: Grade;
  summary: string;
  key_point: string;
  excerpt: string;
  conditions: string[];
  limitations: string[];
  reason: string;
};

type ScientificOut = {
  overall_grade: Grade;
  summary: string;
  error?: string | null;
  papers: PaperEvidence[];
};

type RegulatoryOut = {
  verdict: Verdict;
  confidence: Grade;
  evidence_summary: string;
  source_urls: string[];
};

type VerifyResult = {
  report_markdown: string;
  claims: unknown[];
  scientific: ScientificOut;
  regulatory: RegulatoryOut;
  cross_validation: { overall_verdict: string };
  score_summary?: ScoreSummaryT;
  claim_verdicts?: Array<{
    claim: string;
    verdict: string;
    credibility?: Grade;
    confidence_pct?: number;
    flags?: string[];
  }>;
  roadmap_steps?: RoadmapStep[];
};

const inputMode = ref<"text" | "pdf">("text");
const language = ref<"ko" | "en">("ko");
const domain = ref<string>("climate");
const text = ref<string>("");
const pdfFile = ref<File | null>(null);

const isLoading = ref(false);
const errorMsg = ref<string>("");
const result = ref<VerifyResult | null>(null);
const rightTab = ref<"claims" | "report">("claims");
const devMode = ref(false);

const canSubmit = computed(() => {
  if (inputMode.value === "text") return text.value.trim().length >= 5;
  return !!pdfFile.value;
});

function onPickPdf(e: Event) {
  const input = e.target as HTMLInputElement;
  pdfFile.value = input.files?.[0] ?? null;
}

function clearAll() {
  text.value = "";
  pdfFile.value = null;
  errorMsg.value = "";
  result.value = null;
}

function gradeClass(g?: string) {
  const v = (g ?? "").toUpperCase();
  if (v === "HIGH") return "high";
  if (v === "MED") return "med";
  if (v === "LOW") return "low";
  return "";
}

function badgeClass(level?: string) {
  const v = (level ?? "").toUpperCase();
  if (v === "HIGH") return "high";
  if (v === "MED") return "med";
  if (v === "LOW") return "low";
  return "neutral";
}

const summaryText = computed(() => {
  const md = result.value?.report_markdown ?? "";
  if (!md.trim()) return "근거를 바탕으로 결과를 요약합니다.";
  // Executive Summary 섹션이 있으면 그 주변을 우선 사용
  const idx = md.indexOf("## 1. Executive Summary");
  const slice = idx >= 0 ? md.slice(idx, idx + 700) : md.slice(0, 700);
  // 마크다운을 아주 단순히 정리 (UI용 짧은 요약)
  return slice.replace(/[#*_`>-]/g, "").replace(/\n{2,}/g, "\n").trim().slice(0, 420);
});

async function confirm() {
  errorMsg.value = "";
  result.value = null;

  if (devMode.value) {
    result.value = buildDevMock();
    return;
  }

  if (inputMode.value === "pdf") {
    // 현재 백엔드는 PDF input_type 미지원
    errorMsg.value = "현재 백엔드는 PDF 업로드를 지원하지 않습니다. 텍스트 입력으로 진행해 주세요.";
    return;
  }

  isLoading.value = true;
  try {
    const resp = await fetch("/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_type: "text",
        content: text.value
      })
    });
    if (!resp.ok) {
      const t = await resp.text();
      throw new Error(`요청 실패 (${resp.status}): ${t}`);
    }
    result.value = (await resp.json()) as VerifyResult;
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : "알 수 없는 오류";
  } finally {
    isLoading.value = false;
  }
}

async function copyReport() {
  if (!result.value) return;
  await navigator.clipboard.writeText(result.value.report_markdown ?? "");
}

const devJson = computed(() => {
  if (!devMode.value) return "";
  const v = result.value ?? buildDevMock();
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
});

function setDevMode(on: boolean) {
  devMode.value = on;
  if (on) {
    result.value = buildDevMock();
  } else {
    result.value = null;
  }
}

function toggleDevMode() {
  const next = !devMode.value;
  const url = new URL(window.location.href);
  if (next) url.searchParams.set("dev", "1");
  else url.searchParams.delete("dev");
  window.history.replaceState(null, "", url.toString());
  setDevMode(next);
}

function buildDevMock(): VerifyResult {
  return {
    report_markdown:
      "# 기술 검증·도입 가능성 보고서: DAC 직접공기포집\n\n## 1. Executive Summary\n- 최종 판단: **조건부 가능**\n- 근거: 상위 논문은 실험실/파일럿 근거 중심이며, 보도자료 표현은 조건 누락 가능.\n\n## 2. Agent 요약\n- Scientific: MED\n- Industrial: MED\n- Regulatory: 불명확 (MED)\n",
    claims: [
      {
        technology: "DAC 직접공기포집",
        claim: "1,000시간 연속 운전 성공",
        application: "탄소 저감",
        type: "성능 지표",
        status: "달성"
      }
    ],
    scientific: {
      overall_grade: "MED",
      summary: "초록 기반 evidence pack 예시입니다.",
      papers: [
        {
          title: "The Open DAC 2023 Dataset and Challenges for Sorbent Discovery in Direct Air Capture",
          authors: ["A. Researcher", "B. Author"],
          year: 2023,
          journal: "arXiv (preprint)",
          url: "https://arxiv.org/abs/2301.00000",
          grade_score: 0.72,
          grade_level: "MED",
          summary:
            "이 논문은 DAC 흡착제 후보 탐색을 위한 데이터셋/벤치마크를 제안한다. 초록 기준으로 실험실 수준의 흡착 성능 비교와 데이터셋 구성 방법을 설명한다. 다만 실제 환경·장시간 운전에서의 일반화는 제한적일 수 있다.",
          key_point: "lab-scale 성능 비교/데이터셋",
          excerpt: "…direct air capture (DAC)… sorbent discovery… benchmark…",
          conditions: ["lab-scale", "흡착제 비교", "데이터셋 기반"],
          limitations: ["실환경 미검증", "장시간 운전 조건 제한"],
          reason: "초록 수준 근거만으로 상용화·장시간 운전 성공을 단정하면 과장일 수 있다."
        },
        {
          title: "Commercial Direct Air Capture Design and Operation with Power Market Volatility",
          authors: ["C. Author"],
          year: 2024,
          journal: "Energy Systems",
          url: "https://example.org/paper",
          grade_score: 0.81,
          grade_level: "HIGH",
          summary:
            "DAC 설비 운영을 전력시장 변동성 관점에서 모델링하고 경제성/운영 전략을 평가한다. 시스템 설계 가정과 제약조건에 따라 결과가 달라질 수 있으며, 지역·전력믹스에 대한 의존성이 있다.",
          key_point: "운영·경제성 모델링",
          excerpt: "…design and operation… power market volatility…",
          conditions: ["모델 기반", "전력가격 시나리오"],
          limitations: ["현장 데이터 부족", "가정 의존"],
          reason: "모델 기반 결과를 실증 성과로 서술하면 과장될 수 있다."
        }
      ]
    },
    regulatory: {
      verdict: "불명확",
      confidence: "MED",
      evidence_summary:
        "정부/공공 텍스트와 웹 스니펫을 기반으로 요약한 예시다. 적용 가능 인센티브/규제는 기술 범위·운영지역·보고/측정 기준에 따라 달라질 수 있어 불명확 처리한다. 전문가 검토가 필요하다.",
      source_urls: [
        "https://www.law.go.kr",
        "https://eur-lex.europa.eu",
        "https://federalregister.gov"
      ]
    },
    cross_validation: { overall_verdict: "조건부 가능" },
    score_summary: {
      trl: "TRL 5~6",
      mrl: "MRL 5~6",
      cri: "CRI 3~4",
      trl_level: "MED",
      mrl_level: "MED",
      cri_level: "MED",
      bars: [
        { label: "Scientific", value: 62, level: "MED" },
        { label: "Industrial", value: 58, level: "MED" },
        { label: "Regulatory", value: 42, level: "LOW" }
      ]
    },
    claim_verdicts: [
      {
        claim: "1,000시간 연속 운전 성공",
        verdict: "실증 조건/측정 기준이 불명확하여 추가 근거 필요",
        credibility: "MED",
        confidence_pct: 54,
        flags: ["조건 누락 가능", "근거 부족"]
      },
      {
        claim: "상용화 직전",
        verdict: "초록/스니펫 기준 상용화 단정은 과장 가능",
        credibility: "LOW",
        confidence_pct: 38,
        flags: ["과장 가능"]
      }
    ],
    roadmap_steps: [
      { title: "근거 정리(논문/규제)", description: "evidence pack 품질 점검 및 누락 조건 표기", status: "DONE" },
      { title: "성능 수치 교차검증", description: "운전 조건/측정 기준/재현성 확인", status: "NEXT" },
      { title: "규제 전문가 검토", description: "관할/요건/보고체계 상세 검토", status: "RISK" }
    ]
  };
}

onMounted(() => {
  const url = new URL(window.location.href);
  setDevMode(url.searchParams.get("dev") === "1");
});
</script>


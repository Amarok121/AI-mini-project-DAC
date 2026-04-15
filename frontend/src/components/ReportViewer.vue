<template>
  <div class="report-viewer">
    <div class="report-toolbar">
      <button type="button" class="btn" :disabled="!markdown" @click="emitCopy">Markdown 복사</button>
      <button type="button" class="btn" :disabled="!markdown" @click="downloadMd">.md 다운로드</button>
      <button type="button" class="btn primary" :disabled="!markdown || pdfLoading" @click="downloadPdf">
        {{ pdfLoading ? "PDF 준비 중…" : "PDF 다운로드" }}
      </button>
    </div>
    <p v-if="pdfError" class="hint" style="margin: 0 0 10px">{{ pdfError }}</p>
    <div v-if="html" class="report-md prose" v-html="html" />
    <div v-else class="hint">보고서 Markdown이 없습니다.</div>

    <div v-if="(citations || []).length" class="citation-panel">
      <div class="hint" style="font-weight: 800; letter-spacing: 0.06em; margin-bottom: 8px">출처·각주 (citation_metadata)</div>
      <ol class="citation-list">
        <li v-for="c in citations || []" :key="c.ref_id">
          <span class="citation-id">[{{ c.ref_id }}]</span>
          <span class="citation-meta">{{ c.apa7_citation || "(서지 정보 없음)" }}</span>
          <span v-if="c.source_type" class="hint"> — {{ c.source_type }}</span>
          <div v-if="c.url" class="citation-url">
            <a :href="c.url" target="_blank" rel="noreferrer">{{ c.url }}</a>
          </div>
          <div v-if="c.raw_text" class="citation-snippet">{{ c.raw_text }}</div>
        </li>
      </ol>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch, ref } from "vue";
import { renderMarkdownSafe } from "../utils/renderMarkdown";
import type { CitationMeta } from "../types/citation";

const props = defineProps<{
  markdown: string;
  citations?: CitationMeta[];
}>();

const emit = defineEmits<{
  (e: "copy"): void;
}>();

const html = ref("");
const pdfLoading = ref(false);
const pdfError = ref("");

watch(
  () => props.markdown,
  (md) => {
    html.value = md ? renderMarkdownSafe(md) : "";
  },
  { immediate: true }
);

function emitCopy() {
  emit("copy");
}

async function downloadMd() {
  if (!props.markdown?.trim()) return;
  const resp = await fetch("/report/markdown", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown: props.markdown, title: "기술 검증 보고서" })
  });
  if (!resp.ok) {
    pdfError.value = "Markdown 다운로드에 실패했습니다.";
    return;
  }
  const blob = await resp.blob();
  triggerBlobDownload(blob, "verification_report.md");
  pdfError.value = "";
}

async function downloadPdf() {
  if (!props.markdown?.trim()) return;
  pdfLoading.value = true;
  pdfError.value = "";
  try {
    const resp = await fetch("/report/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: props.markdown, title: "기술 검증 보고서" })
    });
    if (resp.status === 503) {
      const err = await resp.json().catch(() => ({}));
      pdfError.value =
        (err as { detail?: string }).detail ||
        "서버에서 PDF를 생성할 수 없습니다. WeasyPrint 등이 필요할 수 있습니다. .md 다운로드를 이용해 주세요.";
      return;
    }
    if (!resp.ok) {
      pdfError.value = `PDF 요청 실패 (${resp.status})`;
      return;
    }
    const blob = await resp.blob();
    triggerBlobDownload(blob, "verification_report.pdf");
  } catch {
    pdfError.value = "PDF 다운로드 중 네트워크 오류가 발생했습니다.";
  } finally {
    pdfLoading.value = false;
  }
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<style scoped>
.report-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.report-md {
  padding: 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--mono-bg);
  max-height: min(70vh, 640px);
  overflow: auto;
  line-height: 1.55;
  color: var(--text);
  font-size: 14px;
}

.report-md :deep(h1),
.report-md :deep(h2),
.report-md :deep(h3) {
  color: var(--text-strong);
  margin-top: 1.1em;
}

.report-md :deep(a) {
  color: var(--brand);
}

.report-md :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
}

.report-md :deep(th),
.report-md :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 8px;
  vertical-align: top;
}

.citation-panel {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.citation-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.citation-id {
  font-weight: 800;
  margin-right: 6px;
  color: var(--accent);
}

.citation-meta {
  color: var(--text-soft);
}

.citation-url {
  margin-top: 4px;
  word-break: break-all;
  font-size: 12px;
}

.citation-snippet {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
  white-space: pre-wrap;
}
</style>

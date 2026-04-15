import MarkdownIt from "markdown-it";
// @ts-expect-error no types in package
import footnote from "markdown-it-footnote";
// @ts-expect-error no types in package
import texmath from "markdown-it-texmath";
import katex from "katex";
import DOMPurify from "dompurify";

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true
})
  .use(footnote)
  .use(texmath, {
    engine: katex,
    delimiters: "dollars",
    katexOptions: { throwOnError: false }
  });

/**
 * 서버 Markdown: 표·각주·`$…$` 수식(KaTeX) 등을 HTML로 렌더한 뒤 DOMPurify로 정제.
 */
export function renderMarkdownSafe(src: string): string {
  const raw = md.render(src || "");
  return DOMPurify.sanitize(raw, {
    ADD_ATTR: ["id", "class", "style", "target", "rel", "aria-hidden", "role", "xmlns", "viewBox", "width", "height"],
    ADD_TAGS: [
      "svg",
      "path",
      "g",
      "defs",
      "line",
      "rect",
      "marker",
      "use",
      "annotation",
      "semantics",
      "math",
      "mi",
      "mn",
      "mo",
      "ms",
      "mrow",
      "msup",
      "msub",
      "mfrac",
      "mtext"
    ],
    ALLOWED_TAGS: [
      "p",
      "br",
      "strong",
      "em",
      "s",
      "h1",
      "h2",
      "h3",
      "h4",
      "ul",
      "ol",
      "li",
      "blockquote",
      "code",
      "pre",
      "a",
      "img",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "hr",
      "sup",
      "sub",
      "div",
      "span",
      "section"
    ]
  });
}

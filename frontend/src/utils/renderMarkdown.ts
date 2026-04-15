import MarkdownIt from "markdown-it";
// @ts-expect-error no types in package
import footnote from "markdown-it-footnote";
import DOMPurify from "dompurify";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
}).use(footnote);

/**
 * 서버에서 내려온 Markdown(각주 [^n] 포함)을 안전한 HTML로 렌더링합니다.
 */
export function renderMarkdownSafe(src: string): string {
  const raw = md.render(src || "");
  return DOMPurify.sanitize(raw, {
    ADD_ATTR: ["id", "class", "target", "rel"],
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

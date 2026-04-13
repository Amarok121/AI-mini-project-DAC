def clean_text(text: str) -> str:
    # TODO: 광고/관련기사/짧은 노이즈 문장을 제거하는 규칙을 고도화
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 10]
    return '\n'.join(lines[:200])

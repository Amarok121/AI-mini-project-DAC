# TODO: title 입력일 때 검색 API(Tavily/SerpAPI) 연동해 URL/본문으로 변환

async def parse_input(input_type: str, content: str) -> str:
    if input_type == 'text':
        return content
    if input_type == 'url':
        return f'[URL 본문 추출 TODO] {content}'
    if input_type == 'title':
        return f'[제목 검색 TODO] {content}'
    raise ValueError('지원하지 않는 input_type 입니다.')

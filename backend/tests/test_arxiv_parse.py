"""arXiv Atom 파서·쿼리 빌더 단위 테스트 (네트워크 없음)."""

from app.agents.scientific.arxiv import _parse_feed, build_arxiv_search_query


def test_build_arxiv_search_query_uses_and() -> None:
    q = build_arxiv_search_query("direct air capture co2")
    assert "AND" in q
    assert "all:direct" in q
    assert "all:air" in q


def test_parse_feed_minimal() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>  Test  DAC  Paper  </title>
    <summary> Abstract line one. </summary>
    <published>2024-01-15T12:00:00Z</published>
    <author><name>Jane Doe</name></author>
    <arxiv:doi>10.1000/test</arxiv:doi>
    <link rel="alternate" href="https://arxiv.org/abs/2401.00001v1" type="text/html"/>
  </entry>
</feed>"""
    rows = _parse_feed(xml)
    assert len(rows) == 1
    r = rows[0]
    assert r["title"] == "Test DAC Paper"
    assert r["year"] == 2024
    assert r["arxiv_id"] == "2401.00001v1"
    assert r["doi"] == "10.1000/test"
    assert r["abs_url"] == "https://arxiv.org/abs/2401.00001v1"

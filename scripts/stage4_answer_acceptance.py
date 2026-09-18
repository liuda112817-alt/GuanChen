"""Real Stage4 answers and source lineage checks against stored knowledge chunks."""
import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.application.factory import build_retrieval_service
from guanchen_v2.config.settings import Settings
from guanchen_v2.knowledge.persistence.database import create_database_runtime
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow
from guanchen_v2.llm.client import LLMClient

QUERIES = ['什么是八字', '正官是什么意思', '正印是什么意思', '五行相生的顺序是什么', '天干和地支有什么区别',
           '六爻中的世应是什么', '动爻是什么意思', '阴阳是什么', '十神是什么意思', '周易和六爻有什么区别']
OUT = Path('evals/acceptance/stage4_answer_report.json')


async def main():
    settings = Settings()
    db = create_database_runtime(database_url=settings.database_url)
    report = {'timestamp': datetime.now(timezone.utc).isoformat(), 'model': settings.deepseek_model, 'cases': []}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        retrieval = await build_retrieval_service(db.session_factory)
        agent = KnowledgeAgent(retrieval, LLMClient.from_settings(settings))
        for index, query in enumerate(QUERIES):
            response = await agent.answer(query)
            sources = []
            async with db.session_factory() as session:
                for citation in response.citations:
                    row = await session.scalar(select(KnowledgeChunkRow).where(KnowledgeChunkRow.chunk_id == citation.chunk_id))
                    assert row is not None
                    assert row.source_title == citation.source_title and row.section == citation.section
                    sources.append({'chunk_id': row.chunk_id, 'source_title': row.source_title, 'section': row.section, 'text': row.text})
            report['cases'].append({'query': query, 'response': asdict(response), 'sources': sources, 'lineage_passed': True})
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(index+1, 'lineage_passed', len(sources), flush=True)
        report['lineage_passed'] = len(report['cases']) == 10 and all(c['lineage_passed'] for c in report['cases'])
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        await db.dispose()


if __name__ == '__main__':
    asyncio.run(main())

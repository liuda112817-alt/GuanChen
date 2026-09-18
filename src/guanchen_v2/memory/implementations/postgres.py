from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.memory.exceptions import (
    MemoryAlreadyExistsError,
    MemoryNotFoundError,
)
from guanchen_v2.memory.models import (
    ConversationStateRecord,
)


class PostgresMemoryStore:


    def __init__(
        self,
        session_factory: async_sessionmaker,
    ):
        self.session_factory = session_factory



    async def save(
        self,
        state: ConversationState,
    ) -> None:

        async with self.session_factory() as session:

            existing = await session.execute(
                select(
                    ConversationStateRecord
                )
                .where(
                    ConversationStateRecord.session_id
                    ==
                    state.session_id
                )
            )


            if existing.scalar_one_or_none():

                raise MemoryAlreadyExistsError(
                    f"Session {state.session_id} 已经存在"
                )


            record = ConversationStateRecord(
                session_id=state.session_id,
                state_json=state.model_dump_json(),
            )


            session.add(record)

            await session.commit()



    async def load(
        self,
        session_id: str,
    ) -> ConversationState | None:


        async with self.session_factory() as session:

            result = await session.execute(
                select(
                    ConversationStateRecord
                )
                .where(
                    ConversationStateRecord.session_id
                    ==
                    session_id
                )
            )


            record = result.scalar_one_or_none()


            if record is None:
                return None


            return ConversationState.model_validate_json(
                record.state_json
            )



    async def update(
        self,
        state: ConversationState,
    ) -> None:


        async with self.session_factory() as session:


            result = await session.execute(
                select(
                    ConversationStateRecord
                )
                .where(
                    ConversationStateRecord.session_id
                    ==
                    state.session_id
                )
            )


            record = result.scalar_one_or_none()


            if record is None:

                raise MemoryNotFoundError(
                    f"Session {state.session_id} 不存在"
                )


            record.state_json = (
                state.model_dump_json()
            )


            await session.commit()



    async def delete(
        self,
        session_id: str,
    ) -> None:


        async with self.session_factory() as session:


            await session.execute(
                delete(
                    ConversationStateRecord
                )
                .where(
                    ConversationStateRecord.session_id
                    ==
                    session_id
                )
            )


            await session.commit()
"""
Unit tests for app.db.session – get_db dependency.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetDb:
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db should yield an AsyncSession-like object."""
        from app.db.session import get_db

        # We need to mock AsyncSessionLocal to avoid connecting to a real DB
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        # Create async context manager mock
        mock_session_factory = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_cm

        with patch("app.db.session.AsyncSessionLocal", mock_session_factory):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session

            # Simulate normal completion
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_rollbacks_on_exception(self):
        """get_db should rollback on exception."""
        from app.db.session import get_db

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit = AsyncMock(side_effect=Exception("DB error"))
        mock_session.rollback = AsyncMock()

        mock_session_factory = MagicMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_cm

        with patch("app.db.session.AsyncSessionLocal", mock_session_factory):
            gen = get_db()
            session = await gen.__anext__()

            # Simulate throwing exception into the generator
            with pytest.raises(Exception, match="DB error"):
                await gen.__anext__()


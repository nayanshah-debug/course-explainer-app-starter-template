"""Shared pytest fixtures for all tests."""
import pytest
from src.app import create_app
from src.data import fetcher
from src.data.providers.mock_provider import MockProvider


@pytest.fixture(scope="session")
def app():
    """Flask app configured for testing with mock data provider."""
    application = create_app({
        "TESTING": True,
        "DATA_PROVIDER": "mock",
    })
    # Override the fetcher provider to use mock (no network calls)
    fetcher.set_provider(MockProvider())
    return application


@pytest.fixture
def client(app):
    return app.test_client()

# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,unused-argument,protected-access
"""Tests for the Zhipu built-in provider."""
from __future__ import annotations

import pytest

import copaw.providers.provider_manager as provider_manager_module
from copaw.providers.openai_provider import OpenAIProvider
from copaw.providers.provider_manager import (
    PROVIDER_ZHIPU,
    ProviderManager,
    ZHIPU_MODELS,
)


def test_zhipu_provider_is_openai_compatible() -> None:
    """Zhipu provider should use the OpenAI-compatible provider path."""
    assert isinstance(PROVIDER_ZHIPU, OpenAIProvider)


def test_zhipu_provider_defaults() -> None:
    """Verify Zhipu provider configuration defaults."""
    assert PROVIDER_ZHIPU.id == "zhipu"
    assert PROVIDER_ZHIPU.name == "智谱 AI"
    assert PROVIDER_ZHIPU.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert PROVIDER_ZHIPU.freeze_url is True
    assert PROVIDER_ZHIPU.support_connection_check is False


def test_zhipu_models_list() -> None:
    """Verify the built-in Zhipu model definitions."""
    model_ids = [model.id for model in ZHIPU_MODELS]
    assert model_ids == ["glm-4.7-flash", "glm-4.6v-flash"]


@pytest.fixture
def isolated_secret_dir(monkeypatch, tmp_path):
    secret_dir = tmp_path / ".copaw.secret"
    monkeypatch.setattr(provider_manager_module, "SECRET_DIR", secret_dir)
    return secret_dir


def test_zhipu_registered_in_provider_manager(isolated_secret_dir) -> None:
    """Zhipu should be available as a built-in provider."""
    manager = ProviderManager()
    provider = manager.get_provider("zhipu")

    assert provider is not None
    assert isinstance(provider, OpenAIProvider)
    assert provider.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert provider.has_model("glm-4.7-flash")
    assert provider.has_model("glm-4.6v-flash")

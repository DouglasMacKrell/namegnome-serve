"""Factory helpers for constructing fuzzy LLM mappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    pass

from namegnome_serve.core.llm_mapper import (
    FuzzyLLMMapper,
    RunnableProtocol,
    build_tv_fuzzy_chain,
)


def create_fuzzy_tv_mapper(
    *,
    llm: RunnableProtocol | None = None,
    model_name: str = "namegnome",
    **model_kwargs: Any,
) -> FuzzyLLMMapper:
    """Build a FuzzyLLMMapper backed by an Ollama chat model or custom LLM."""

    runnable = llm
    if runnable is None:
        import importlib

        module = importlib.import_module("langchain_ollama")
        chat_cls = module.ChatOllama
        runnable = cast(RunnableProtocol, chat_cls(model=model_name, **model_kwargs))

    chain = build_tv_fuzzy_chain(runnable)
    return FuzzyLLMMapper(chain)

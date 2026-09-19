"""Metadata-only callbacks shared by LLMClient and native LangChain agents."""

from langchain_core.callbacks import BaseCallbackHandler

from guanchen_v2.observability.integration import get_tracer


class ModelTraceCallback(BaseCallbackHandler):
    run_inline = True
    raise_error = True

    def __init__(self):
        self.pending = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        tracer = get_tracer()
        if tracer is not None:
            manager = tracer.span("llm", "LLM")
            state = manager.__enter__()
            self.pending[run_id] = (manager, state)

    def on_llm_end(self, response, *, run_id, **kwargs):
        pair = self.pending.pop(run_id, None)
        if pair is None:
            return
        manager, state = pair
        for generation in response.generations:
            for item in generation:
                usage = getattr(getattr(item, "message", None), "usage_metadata", None)
                if usage:
                    state.metadata["token"] = {k: int(usage[k]) for k in ("input_tokens", "output_tokens", "total_tokens") if k in usage}
        manager.__exit__(None, None, None)

    def on_llm_error(self, error, *, run_id, **kwargs):
        pair = self.pending.pop(run_id, None)
        if pair:
            manager, state = pair
            state.status = "FAILED"
            state.metadata["error"] = type(error).__name__
            manager.__exit__(None, None, None)

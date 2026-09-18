from dataclasses import dataclass

from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.memory.store import MemoryStore
from guanchen_v2.router.core import TwoLayerIntentRouter
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import DualDomainDispatcher
from guanchen_v2.router.synthesizer import AgentSynthesizer


@dataclass
class ConversationContext:
    """
    Application 执行时挂载的 Runtime Context。
    只在单次 Request 内存生命周期内存在，连接持久化状态和底层依赖容器。
    """
    state: ConversationState
    memory_store: MemoryStore
    router: TwoLayerIntentRouter
    single_dispatcher: SingleAgentDispatcher
    dual_dispatcher: DualDomainDispatcher
    synthesizer: AgentSynthesizer


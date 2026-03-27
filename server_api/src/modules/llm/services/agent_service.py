"""공유 운영용 채팅 에이전트 인스턴스 접근용 얇은 래퍼."""

from ..agent import CSAgent, agent_instance


def get_agent() -> CSAgent:
    """FastAPI 프로세스 전체에서 공유하는 싱글톤 에이전트를 반환한다."""
    return agent_instance

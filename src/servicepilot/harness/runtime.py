"""Model-independent Agent Runtime Harness."""

import hashlib

from servicepilot.eval.models import ScenarioSpec, Trajectory
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.checkpoints import InMemoryCheckpointStore
from servicepilot.harness.guardrails import GuardrailPipeline
from servicepilot.harness.models import (
    GuardrailStage,
    HarnessEvent,
    HarnessRunConfig,
    HarnessSession,
    HarnessSessionStatus,
    HarnessTerminationReason,
    ReplayMode,
)
from servicepilot.harness.protocols import AgentPolicy, CheckpointStore
from servicepilot.mcp_gateway.gateway import ReliableToolGateway


class UnsupportedResumeError(RuntimeError):
    """Raised when a checkpoint is not at a safe resumable boundary."""


class AgentRuntimeHarness:
    def __init__(
        self,
        *,
        checkpoint_store: CheckpointStore | None = None,
        guardrails: GuardrailPipeline | None = None,
    ) -> None:
        self.checkpoints = checkpoint_store or InMemoryCheckpointStore()
        self.guardrails = guardrails or GuardrailPipeline()

    @staticmethod
    def session_id(scenario: ScenarioSpec, config: HarnessRunConfig) -> str:
        return f"harness-{scenario.scenario_id}-{config.fingerprint()[:12]}"

    async def run(
        self,
        *,
        scenario: ScenarioSpec,
        agent: AgentPolicy,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
        config: HarnessRunConfig,
        resume: bool = False,
    ) -> HarnessSession:
        session_id = self.session_id(scenario, config)
        existing = self.checkpoints.load(session_id)
        if resume and existing is not None:
            if (
                existing.status is HarnessSessionStatus.COMPLETED
                and existing.trajectory is not None
            ):
                return existing
            raise UnsupportedResumeError(
                "only completed session checkpoints are currently resumable"
            )
        session = HarnessSession(
            session_id=session_id,
            scenario_id=scenario.scenario_id,
            config=config,
        )
        session = self._append(
            session,
            "session_initialized",
            {"scenario_id": scenario.scenario_id},
            status=HarnessSessionStatus.RUNNING,
        )
        self.checkpoints.save(session)
        input_decisions = self.guardrails.evaluate(
            GuardrailStage.INPUT, {"text": scenario.user_utterance}
        )
        if not self.guardrails.allowed(input_decisions):
            stopped = self._append(
                session,
                "guardrail_stop",
                {
                    "decisions": [
                        item.model_dump(mode="json")
                        for item in input_decisions
                    ]
                },
                status=HarnessSessionStatus.FAILED,
                termination=HarnessTerminationReason.GUARDRAIL_STOP,
            )
            self.checkpoints.save(stopped)
            return stopped
        try:
            trajectory = await agent.run(scenario, simulator, gateway)
        except Exception as exc:
            failed = self._append(
                session,
                "runtime_error",
                {"error_type": type(exc).__name__},
                status=HarnessSessionStatus.FAILED,
                termination=HarnessTerminationReason.RUNTIME_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
            self.checkpoints.save(failed)
            raise
        output_decisions = self.guardrails.evaluate(
            GuardrailStage.OUTPUT,
            {"claimed_success": trajectory.claimed_success},
        )
        status = (
            HarnessSessionStatus.COMPLETED
            if self.guardrails.allowed(output_decisions)
            else HarnessSessionStatus.FAILED
        )
        termination = (
            HarnessTerminationReason.COMPLETED
            if status is HarnessSessionStatus.COMPLETED
            else HarnessTerminationReason.GUARDRAIL_STOP
        )
        completed = self._append(
            session,
            "session_finished",
            {
                "trajectory_sha256": hashlib.sha256(
                    trajectory.model_dump_json().encode()
                ).hexdigest(),
                "output_guardrails": [
                    item.model_dump(mode="json")
                    for item in output_decisions
                ],
            },
            status=status,
            termination=termination,
            trajectory=trajectory,
        )
        self.checkpoints.save(completed)
        return completed

    def replay(
        self,
        *,
        trajectory: Trajectory,
        scenario: ScenarioSpec,
        config: HarnessRunConfig,
        mode: ReplayMode = ReplayMode.VERIFY_ONLY,
    ) -> HarnessSession:
        session = HarnessSession(
            session_id=f"replay-{self.session_id(scenario, config)}",
            scenario_id=scenario.scenario_id,
            config=config,
            status=HarnessSessionStatus.REPLAYED,
            termination_reason=HarnessTerminationReason.REPLAY_COMPLETED,
            events=(
                HarnessEvent.create(
                    0,
                    "trajectory_replayed",
                    {
                        "mode": mode.value,
                        "trajectory_sha256": hashlib.sha256(
                            trajectory.model_dump_json().encode()
                        ).hexdigest(),
                    },
                ),
            ),
            trajectory=trajectory,
        )
        self.checkpoints.save(session)
        return session

    @staticmethod
    def _append(
        session: HarnessSession,
        kind: str,
        payload: dict[str, object],
        *,
        status: HarnessSessionStatus,
        termination: HarnessTerminationReason | None = None,
        trajectory: Trajectory | None = None,
        error: str | None = None,
    ) -> HarnessSession:
        event = HarnessEvent.create(len(session.events), kind, payload)
        return session.model_copy(
            update={
                "status": status,
                "termination_reason": termination,
                "events": (*session.events, event),
                "trajectory": trajectory,
                "error": error,
            }
        )


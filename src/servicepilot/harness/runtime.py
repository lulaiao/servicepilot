"""Model-independent Agent Runtime Harness."""

import asyncio
import hashlib

from servicepilot.eval.models import ScenarioSpec, Trajectory
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.checkpoints import InMemoryCheckpointStore
from servicepilot.harness.dispatcher import (
    CheckpointingToolDispatcher,
    HarnessControlStop,
    SimulatedHarnessInterruption,
)
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
        interrupt_after_committed_tool: str | None = None,
    ) -> HarnessSession:
        session_id = self.session_id(scenario, config)
        existing = self.checkpoints.load(session_id)
        if resume and existing is not None:
            if (
                existing.status is HarnessSessionStatus.COMPLETED
                and existing.trajectory is not None
            ):
                return existing
            if existing.status is not HarnessSessionStatus.INTERRUPTED:
                raise UnsupportedResumeError("checkpoint is not at a safe resumable boundary")
            session = self._append(
                existing,
                "session_resumed",
                {"tool_steps": len(existing.tool_steps)},
                status=HarnessSessionStatus.RUNNING,
            )
        else:
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
        session_holder = [session]
        self.checkpoints.save(session_holder[0])

        def persist_step(step: object) -> None:
            from servicepilot.harness.models import ToolStepCheckpoint

            assert isinstance(step, ToolStepCheckpoint)
            current = session_holder[0]
            steps = tuple(old for old in current.tool_steps if old.call_key != step.call_key) + (
                step,
            )
            current = self._append(
                current.model_copy(update={"tool_steps": steps}),
                f"tool_{step.status.value}",
                {"call_key": step.call_key, "tool_name": step.tool_name},
                status=HarnessSessionStatus.RUNNING,
            )
            session_holder[0] = current
            self.checkpoints.save(current)

        dispatcher = CheckpointingToolDispatcher(
            gateway,
            existing_steps=session_holder[0].tool_steps,
            persist=persist_step,
            interrupt_after_committed_tool=interrupt_after_committed_tool,
            guardrails=self.guardrails,
            max_tool_calls=config.budgets.max_tool_calls,
            max_retries=config.budgets.max_retries,
        )
        input_decisions = self.guardrails.evaluate(
            GuardrailStage.INPUT, {"text": scenario.user_utterance}
        )
        if not self.guardrails.allowed(input_decisions):
            stopped = self._append(
                session,
                "guardrail_stop",
                {"decisions": [item.model_dump(mode="json") for item in input_decisions]},
                status=HarnessSessionStatus.FAILED,
                termination=HarnessTerminationReason.GUARDRAIL_STOP,
            )
            self.checkpoints.save(stopped)
            return stopped
        try:
            async with asyncio.timeout(config.budgets.timeout_seconds):
                trajectory = await agent.run(scenario, simulator, dispatcher)  # type: ignore[arg-type]
            session = session_holder[0]
        except TimeoutError:
            return self._stop(
                session_holder[0],
                HarnessTerminationReason.TIME_BUDGET_EXHAUSTED,
                "runtime time budget exhausted",
                dispatcher,
            )
        except HarnessControlStop as exc:
            return self._stop(session_holder[0], exc.reason, str(exc), dispatcher)
        except SimulatedHarnessInterruption as exc:
            interrupted = self._append(
                session_holder[0],
                "session_interrupted",
                {"error_type": type(exc).__name__},
                status=HarnessSessionStatus.INTERRUPTED,
                termination=HarnessTerminationReason.INTERRUPTED,
                error=str(exc),
            )
            self.checkpoints.save(interrupted)
            return interrupted
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
        turns_used = sum(event.role.value in {"user", "assistant"} for event in trajectory.events)
        model_tokens_used = int(getattr(agent, "model_tokens_used", 0))
        session = session.model_copy(
            update={
                "turns_used": turns_used,
                "tool_calls_used": dispatcher.tool_calls_used,
                "retries_used": dispatcher.retries_used,
                "model_tokens_used": model_tokens_used,
            }
        )
        if turns_used > config.budgets.max_turns:
            return self._stop(
                session,
                HarnessTerminationReason.TURN_BUDGET_EXHAUSTED,
                "runtime turn budget exhausted",
                dispatcher,
                trajectory=trajectory,
            )
        if (
            config.budgets.max_model_tokens is not None
            and model_tokens_used > config.budgets.max_model_tokens
        ):
            return self._stop(
                session,
                HarnessTerminationReason.TOKEN_BUDGET_EXHAUSTED,
                "runtime model-token budget exhausted",
                dispatcher,
                trajectory=trajectory,
            )
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
                "output_guardrails": [item.model_dump(mode="json") for item in output_decisions],
            },
            status=status,
            termination=termination,
            trajectory=trajectory,
        )
        self.checkpoints.save(completed)
        return completed

    def _stop(
        self,
        session: HarnessSession,
        reason: HarnessTerminationReason,
        message: str,
        dispatcher: CheckpointingToolDispatcher,
        *,
        trajectory: Trajectory | None = None,
    ) -> HarnessSession:
        stopped = self._append(
            session.model_copy(
                update={
                    "tool_calls_used": dispatcher.tool_calls_used,
                    "retries_used": dispatcher.retries_used,
                }
            ),
            "runtime_stopped",
            {"reason": reason.value, "message": message},
            status=HarnessSessionStatus.FAILED,
            termination=reason,
            trajectory=trajectory,
            error=message,
        )
        self.checkpoints.save(stopped)
        return stopped

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

"""Application commands connecting the operator to OpenPI HG-DAgger."""

import sys
from pathlib import Path

from core.workbench.core.state_machine import Command
from core.workbench.motion.policy_adapter import PolicyRuntimeView


class DaggerBindings:
    def __init__(
        self,
        runtime,
        service,
        readiness,
        *,
        openpi_root,
        config_dir=None,
        dagger_config=None,
        request_lead_steps=6,
        timeout_s=30.0,
    ):
        self.runtime = runtime
        self.service = service
        self.readiness = readiness
        self.openpi_root = Path(openpi_root).resolve()
        deployment = self.openpi_root / "examples/cr3_o6/deploy"
        self.config_dir = Path(config_dir) if config_dir is not None else deployment / "config"
        self.dagger_config = (
            Path(dagger_config) if dagger_config is not None else self.config_dir / "dagger.yaml"
        )
        self.request_lead_steps = request_lead_steps
        self.timeout_s = timeout_s

    def install(self):
        self.service.set_handler(Command.START_DAGGER, self.start)
        self.service.set_handler(Command.STOP_DAGGER, self.stop)
        self.service.set_handler(Command.TOGGLE_INTERVENTION, self.toggle)
        return self

    def start(self, payload):
        engine = self.runtime.teleop_engine
        generation = engine.stop_generation
        if engine.state != "idle":
            raise RuntimeError("请先停止主从跟随，再启动 DAgger")
        recorded = self.runtime.recorder.snapshot()
        if recorded["episode_active"] or recorded["buffered_frames"]:
            raise RuntimeError("请先处理当前 LeRobot Episode")
        ready = self.readiness.snapshot()
        if not (
            ready["master_connected"] and ready["o6_connected"] and ready["camera_frames_ready"]
        ):
            raise RuntimeError("DAgger 需要 GELLO、O6 和新鲜的三路画面：" + ready["camera_error"])
        cfg = self.runtime.store.data
        if cfg["master"]["type"] != "gello" or cfg["gello"]["control_mode"] != "joint":
            raise ValueError("DAgger 需要 GELLO joint 模式")
        task = str(payload["task"]).strip()
        host = str(payload["host"]).strip()
        root = str(Path(str(payload["base_root"]).strip()).expanduser().resolve())
        round_id = str(payload["round_id"]).strip()
        port = int(payload["port"])
        if not all((task, host, root, round_id)) or not 1 <= port <= 65535:
            raise ValueError("模型地址、端口、任务、轮次和存储目录必须有效")
        engine.finish_external_control()
        deployment = self.openpi_root / "examples/cr3_o6/deploy"
        if not (deployment / "dagger_controller.py").is_file():
            raise FileNotFoundError(f"DAgger 部署模块不存在：{deployment}")
        # The existing deploy entry points use sibling imports. Keep that same
        # module boundary; do not import the training environment or its JAX stack.
        if str(deployment) not in sys.path:
            sys.path.insert(0, str(deployment))
        import yaml
        from dagger_controller import DaggerController, DaggerPolicyClient
        from dagger_recorder import DaggerRecorder
        from gello_expert import GelloExpert
        from gello_runtime_interface import GelloRuntimeInterface
        from interface import InterfaceConfig, validate_task_prompt, warmup_policy
        from intervention_input import InterventionInput
        from main_rtc import RTCDeploymentConfig, _validate_server_metadata

        dagger_cfg = yaml.safe_load(self.dagger_config.read_text())
        if (
            dagger_cfg["intervention"]["mode"] != "toggle"
            or dagger_cfg["intervention"]["key"] != "Space"
        ):
            raise ValueError("GELLO 界面 DAgger 使用空格 toggle 模式")
        dataset = cfg["dataset"]
        interface_cfg = InterfaceConfig.from_yaml_dir(
            self.config_dir,
            global_camera_serial=dataset["base_camera_serial"],
            wrist_camera_serial=dataset["wrist_camera_serial"],
            roi_norm=tuple(dataset["base_roi_norm"]),
        )
        motion_view = PolicyRuntimeView(self.runtime)
        robot = GelloRuntimeInterface(motion_view, interface_cfg)
        policy = DaggerPolicyClient(host, port, inference_timeout_s=self.timeout_s)
        recorder = None
        controller = None
        try:
            metadata = policy.get_server_metadata()
            _validate_server_metadata(metadata, robot.ACTION_CONTRACT)
            validate_task_prompt(metadata, task)
            # Initialization actions are discarded before opening the motion channel.
            warmup_policy(policy, robot, task)
            hand_cfg = cfg["o6"]
            expert = GelloExpert(
                self.runtime.gello_controller,
                open_target=hand_cfg["actions"][hand_cfg["open_action"]],
                closed_target=hand_cfg["actions"][hand_cfg["closed_action"]],
                timeout_s=cfg["gello"]["feedback_timeout_s"],
                **dagger_cfg["expert"],
            )
            recorder = DaggerRecorder(
                root,
                round_id=round_id,
                task=task,
                queue_size=dagger_cfg["recording"]["queue_size"],
                prebuffer_frames=dagger_cfg["intervention"]["prebuffer_frames"],
                metadata={
                    "policy": metadata,
                    "policy_endpoint": f"{host}:{port}",
                    "gello_config": cfg,
                    "deployment_config": str(self.config_dir),
                },
            )
            controller = DaggerController(
                robot,
                policy,
                task,
                RTCDeploymentConfig(
                    control_hz=dagger_cfg["control_hz"],
                    request_lead_steps=self.request_lead_steps,
                    inference_timeout_s=self.timeout_s,
                    max_observation_age_s=interface_cfg.action_max_age_s,
                ),
                expert=expert,
                intervention=InterventionInput(),
                recorder=recorder,
            )
            engine.start_external_control(controller, generation, motion_view=motion_view)
        except Exception as exc:
            errors = [exc]
            stop_motion = (
                [robot.emergency_stop]
                if controller is not None and engine.external_control is controller
                else []
            )
            for cleanup in (
                stop_motion + [policy.close] + ([recorder.close] if recorder is not None else [])
            ):
                try:
                    cleanup()
                except Exception as cleanup_error:
                    errors.append(cleanup_error)
            if len(errors) > 1:
                raise ExceptionGroup("DAgger 启动/清理失败", errors) from exc
            engine.external_control = None
            raise

    def toggle(self, _payload):
        engine = self.runtime.teleop_engine
        if engine.external_control is None or engine.state != "dagger":
            raise RuntimeError("请先启动 DAgger 模型控制")
        return engine.external_control.intervention.toggle()

    def stop(self, _payload):
        self.runtime.teleop_engine.stop_follow("停止 DAgger")
        self.close()

    def close(self):
        self.runtime.teleop_engine.finish_external_control()

# 数据格式、采集与恢复

数据路径是 `CaptureSource → CaptureFrame → RecordingSession → DatasetWriter → 独立 Worker`。格式选择不会更改采样契约。正式 HMI 在创建批次时锁定任务、模式和格式；每条 Episode 停止后必须选择 Success、Failure 或丢弃，再开始下一条。

## 状态、动作与时间

`recording/schema.py` 和 `data_contract.py` 定义固定顺序；不要根据字段历史前缀推断机器人型号。TCP 字段沿用 `cr5.*`，joint 字段为 `cr3.*`，本部署硬件 Profile 为 CR3A + O6。

| 模式 | `observation.state` | `action` |
| --- | --- | --- |
| `joint` | 12 维：J1–J6 实测关节（rad）+ O6 六电机位置 | 12 维：J1–J6 已接受并提交的绝对关节目标（rad）+ O6 六电机目标 |
| `tcp` | 18 维：J1–J6（rad）+ TCP XYZ（m）+ RPY（rad）+ O6 六电机位置 | 12 维：当前实测 TCP 到已接受目标的 XYZ 差值（m）+ 最短 RPY 差值（rad）+ O6 六电机目标 |

O6 六维顺序是拇指弯曲、拇指侧摆、食指、中指、无名指、小指；位置和目标是设备原始 0..255 值，不是 rad。SDK 接受命令不表示机器人已执行到位。joint 采集要求有活动控制源及已下发目标；Teleop、回放和走点采集需显式选择对应来源，HOME 不启动 Episode。全局停止会停止采样并保留 Pending，运动自然结束也不会自动判定 Episode 成功。

`CaptureFrame.timestamp` 是主机 monotonic 秒，用于排序和帧间隔；相机时间戳、Age、Skew 同属主机采样质量信息，不构成硬件同步保证。导出的训练时间由 Episode 帧序和 FPS 生成；原始主机时间、命令 Age、相机时间和质量保存在采集元数据中。创建时间采用 UTC ISO 时间，Episode 另保留 Unix 秒，便于跨进程关联。

采样周期由 `dataset.fps` 决定，GUI 使用 `ui.refresh_ms`，相机缓存更新使用 `dataset.camera_poll_hz`。同一相机帧可能被重复采样；Session 分别记录复用帧、迟帧、跳过的采样槽和质量指标，不把它们冒充相机丢帧。开始 Episode 前会拒绝缺失、过期或 Skew 超限的图像。录制中必要图像失联或过期会停止采样并保留 Pending；Skew 等质量问题记录在 `needs_review` 和质量摘要中，不能只看保存按钮是否成功。

## 三路图像

| 固定训练键 | 默认来源（未配置 `camera_streams` 时） |
| --- | --- |
| `observation.images.base_0_rgb` | Base 相机完整 RGB |
| `observation.images.left_wrist_0_rgb` | Wrist 相机完整 RGB |
| `observation.images.right_wrist_0_rgb` | 同一 Base 相机的 ROI |

`camera_streams` 可明确配置三个槽位，每个包含 `name`、`serial`、`mode`（`camera` 或 `roi`）、`roi_norm`。按槽位顺序映射固定键；键名中的 left/right 不强制对应物理左右相机。相同序列号共享一个物理设备。仓库当前部署配置明确指定三台相机，第三路为完整画面；两相机 + ROI 是兼容缺省布局。ROI 为归一化 `[x1,y1,x2,y2]`，输出 `image_size` 为 `[height,width]`。

## 格式与 Worker 环境

| 配置值 | Worker 要求与主要输出 |
| --- | --- |
| `lerobot_v21` | 独立 LeRobot 0.3.3 / `CODEBASE_VERSION=v2.1`；Parquet、RGB 视频和 LeRobot 元数据 |
| `lerobot_v3` | 独立 LeRobot V3，须有 `RGBEncoderConfig` 与 streaming encoding 接口；V3 分块数据、视频及元数据 |
| `hdf5` | 安装 `h5py`；`dataset.hdf5`，可选 `null` / `gzip` / `lzf` 压缩 |

应用环境无需导入 LeRobot 或 h5py。V2.1 和 V3 使用不同解释器，例如：

```json
{
  "dataset": {
    "format": "lerobot_v3",
    "worker_python": "/opt/workbench/hdf5/bin/python",
    "worker_pythons": {
      "lerobot_v21": "/opt/workbench/lerobot-v21/bin/python",
      "lerobot_v3": "/opt/workbench/lerobot-v3/bin/python"
    }
  }
}
```

这些路径是部署示例，须替换为已有环境。先选 `worker_pythons[format]`，缺少对应项才回退到 `worker_python`；`GELLO_CR_DATA_PYTHON` 覆盖的是该回退值。Worker 启动、编码、合并或校验失败必须保留为错误，不能标记数据发布成功。

## Batch / Segment / 发布

批次在 staging 下保存 manifest、Segment、Episode journal 和显式决策。默认 staging 位于 `dataset.root` 的同级 `staging/`；可用 `dataset.staging_root` 指定。journal 是恢复来源，不是已发布训练数据。

“结束数据集”先校验各 Segment 的结构与选择，再在目标文件系统的 `.tmp_<uuid>` 中生成新数据集，重建连续 Episode / Frame 索引并运行对应格式校验。成功后写入 `batch_provenance.json` 并原子重命名到最终目录；原 Segment 和 journal 保留，既有最终目录不会被覆盖。任务名称用于目录，训练任务描述独立保存。

启动扫描只读，跳过被有效锁占用以及已完成或已丢弃批次，不自动续录。恢复时先检查 Partial：有完整可读帧才可明确保留为 Failure，否则丢弃；决策会标记需要复核。恢复创建新 Segment，不能继续写原 Segment。丢弃批次只记 `DISCARDED`，保留 staging 文件。已发布批次不能通过“丢弃批次”删除。

## 校验

数据集页的 UNCHECKED 表示尚未执行本次显式校验；VALID / INVALID 来自对应格式 Worker。CLI 自动识别已完成的本地数据格式，只读检查：

```bash
GELLO_CR_DATA_PYTHON=/path/to/validator/python scripts/validate_dataset.sh /path/to/final_dataset
scripts/validate_dataset.sh --help
```

校验解释器需要该格式的校验依赖。校验失败返回非零状态并报告原因；训练数据结构校验与现场动作成功率、相机安装质量是不同验收项。

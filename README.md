# Robot Learning Workbench（基线模板）

设计约定：

- `module/openpi/` 是唯一随工作台固定版本管理的算法框架，使用 Git Submodule。
- **不单独拉取 LeRobot**。OpenPI 的 `pyproject.toml` / `uv.lock` 已声明它使用的 LeRobot 依赖及版本来源，环境由 OpenPI 自己管理。
- Python 依赖安装到 `module/openpi/.venv/`，不创建工作台根目录 `.venv`，也不使用系统 Python `pip install`。
- 父仓库提交的 Submodule commit 用于固定团队所用的 OpenPI 版本；OpenPI 的锁文件固定 Python 依赖解析结果。
- 数据集、checkpoint、日志不进入 Git。

> 当前脚本面向 Ubuntu 22.04 + NVIDIA GPU 的常见 OpenPI 开发场景。OpenPI 上游声明 Python >= 3.11，并推荐使用 `uv`。具体 GPU、驱动、CUDA 运行时的兼容性仍需要在目标机器上验证。

## 1. 仓库维护者：创建团队基线

### 1.1 解压模板并初始化父仓库

```bash
git init -b main
git add .
git commit -m "chore: add robot learning workbench skeleton"
```

在 GitHub/GitLab 创建空的团队仓库后，关联远程地址并推送：

```bash
git remote add origin <团队仓库 SSH 或 HTTPS 地址>
git push -u origin main
```

如果这个模板本来就是从团队 Git 仓库克隆来的，则跳过本节。

### 1.2 添加 OpenPI Submodule（仅由维护者首次执行）

```bash
./scripts/add_openpi_submodule.sh
```

脚本会把官方 `Physical-Intelligence/openpi` 仓库添加到 `module/openpi/`，并初始化 OpenPI 自己的子模块。默认检出上游默认分支当时的提交。

检查实际使用的版本：

```bash
git -C module/openpi rev-parse HEAD
git -C module/openpi status --short
```

然后提交父仓库里的 `.gitmodules` 和 Submodule commit：

```bash
git add .gitmodules module/openpi
git commit -m "build: pin OpenPI submodule revision"
git push
```

**多人协作的关键是提交父仓库中的 Submodule commit。** 其他成员会获得该固定提交，不应每个人自行执行 `git submodule update --remote`。

如果团队要修改 OpenPI 源码，建议先 Fork OpenPI 到团队组织，再把 Submodule URL 指向团队 Fork；不要把开发者的未提交修改留在本地子模块中。

## 2. 所有开发者：第一次部署

### 2.1 克隆完整团队代码

```bash
git clone --recurse-submodules <团队仓库 SSH 或 HTTPS 地址> robot_learning_workbench
cd robot_learning_workbench
```

如果之前没有递归克隆，执行：

```bash
git submodule update --init --recursive
```

### 2.2 安装系统工具与 uv（可选）

Ubuntu 22.04：

```bash
./scripts/install_system_deps_ubuntu.sh
```

脚本只安装常用的系统工具（Git、Git LFS、curl、编译工具、FFmpeg 等），不会自动安装或修改 NVIDIA 显卡驱动。系统软件安装需要 `sudo`。

如果尚未安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

如果已经安装 `uv`，不必重复安装。

### 2.3 一键创建并验证 OpenPI 专属环境

```bash
./scripts/bootstrap.sh
```

该脚本会初始化 Submodule、安装依赖并运行环境检查。也可以分开执行：

```bash
./scripts/setup_openpi_env.sh
./scripts/verify_openpi_env.sh
```

脚本会：

1. 检查 OpenPI Submodule 和 `uv` 是否存在；
2. 初始化 OpenPI 自身需要的 Git 子模块；
3. 使用 OpenPI 的 `.python-version`、`pyproject.toml` 和 `uv.lock` 建立依赖环境；
4. 把环境固定到 `module/openpi/.venv/`；
5. 以 editable 模式安装 OpenPI 本身。

安装时间和下载量取决于机器、网络、缓存以及 CUDA/JAX/Torch 依赖。首次安装需要网络连接。

### 2.4 验证环境

```bash
./scripts/verify_openpi_env.sh
```

该脚本检查 Python 解释器路径、OpenPI、LeRobot、JAX、PyTorch、OpenCV 的导入情况，并报告 JAX/Torch 是否能看到 GPU。它是环境 smoke test，不代表已经验证真实机械臂、相机或完整训练过程。

如果要进一步检查 NVIDIA 驱动：

```bash
nvidia-smi
```

### 2.5 运行 OpenPI 命令

使用统一包装脚本，确保命令从 OpenPI 项目目录、在 OpenPI 的虚拟环境中运行：

```bash
./scripts/run_openpi.sh python -c \
  "import sys, openpi, lerobot, jax, torch; print(sys.executable); print('OpenPI imports OK'); print('Torch CUDA:', torch.cuda.is_available()); print('JAX devices:', jax.devices())"
```

训练时示例（把 `<config_name>` 和 `<experiment_name>` 替换成所用 OpenPI 版本中真实存在的配置和实验名）：

```bash
./scripts/run_openpi.sh scripts/train.py <config_name> --exp-name=<experiment_name>
```

可用训练配置以当前固定版本的 `module/openpi/src/openpi/training/config.py` 为准。不要直接复制另一版本的命令或配置名称。

## 3. 后续日常使用与更新原则

### 开发者同步团队已固定的版本

```bash
git pull --ff-only
git submodule update --init --recursive
```

一般不需要每次重新建环境。只有 OpenPI 的 `pyproject.toml` / `uv.lock` 变化，或者维护者明确要求重建环境时，再执行：

```bash
./scripts/setup_openpi_env.sh
```

环境脚本采用锁文件模式；如果 OpenPI 依赖声明和锁文件不一致，脚本会报错而不是静默更新依赖。应先由维护者审核并提交锁文件更新。

### 维护者更新 OpenPI 版本

维护者先在单独的分支中验证新版本，再更新子模块指向并提交：

```bash
git -C module/openpi fetch origin
git -C module/openpi checkout <经过验证的 commit SHA 或 tag>
git -C module/openpi submodule update --init --recursive
./scripts/setup_openpi_env.sh
./scripts/verify_openpi_env.sh

git add module/openpi
git commit -m "build: update pinned OpenPI revision"
git push
```

如果新提交的 `pyproject.toml` 与 `uv.lock` 不一致，应在 OpenPI 子模块的维护分支内按该版本的官方要求更新锁文件、完成验证并先提交 OpenPI 仓库，然后再更新父仓库中的 Submodule commit。

## 4. 目录约定

```text
robot_learning_workbench/
├── vendor/                 # NRC、相机、末端执行器等硬件相关适配/代码
├── teleop/                 # 遥操功能
├── hmi/
│   ├── data_collect/       # 数采界面
│   ├── train/              # 训练界面
│   └── deploy/             # 部署界面
├── module/
│   └── openpi/             # OpenPI Git Submodule（包含其指定的 LeRobot 依赖）
├── core/                   # 核心业务逻辑
│   └── openpi/             # OpenPI相关功能
├── configs/                # 工作台自己的配置
├── dataset/
│   ├── train/              # 本地训练数据，不进 Git
│   └── replay/             # 本地回放轨迹，不进 Git
├── checkpoints/            # 本地模型权重，不进 Git
├── thirdparty/             # 其他确实需要 vendoring 的第三方代码/SDK
├── scripts/                # 环境安装、验证和 OpenPI 包装脚本
└── logs/                   # 本地运行日志，不进 Git
```

当前业务目录只放了 `.gitkeep`，没有预先生成任何业务 Python 文件。不要把 OpenPI 完整源码复制到工作台其他目录；需要导入 OpenPI 的开发脚本应使用 `module/openpi/.venv/bin/python` 执行，或通过 `scripts/run_openpi.sh` 调用。

## 5. 环境隔离与提交规则

- 不提交任何 `.venv/`、缓存、数据集、checkpoint、日志或个人 `.env`。
- 不要在系统 Python 上运行 `pip install` 安装 OpenPI 依赖。
- 不要把另一套 LeRobot 源码放进 `module/lerobot/`；当前 OpenPI 版本所需的 LeRobot 版本由 OpenPI 的依赖配置和锁文件决定。
- 不要由每个开发者自行升级 OpenPI 子模块。版本更新由维护者统一验证、提交。
- 不要在 OpenPI 环境中随手安装未声明的额外包。未来工作台 GUI 若需要 OpenPI 未包含的依赖，应先由团队决定并记录依赖方案，避免只在某个人电脑上可用。
- ROS 2 Humble 和硬件驱动可能有独立的系统/Python 依赖；该基线不擅自把 ROS 依赖安装进 OpenPI 环境。等接入真实机器人时，再明确选择进程/接口边界。

## 官方参考

- [OpenPI 官方仓库](https://github.com/Physical-Intelligence/openpi)
- [OpenPI 官方安装说明](https://github.com/Physical-Intelligence/openpi#installation)
- [Astral uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)
- [uv 同步项目与锁文件](https://docs.astral.sh/uv/concepts/projects/sync/)

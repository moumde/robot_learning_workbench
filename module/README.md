# module/

当前仅添加 OpenPI Git Submodule：`module/openpi/`。

不单独添加 LeRobot 仓库。OpenPI 的 `pyproject.toml` 与 `uv.lock` 已定义此 OpenPI 版本使用的 LeRobot 依赖及固定来源；运行环境由 OpenPI 自己的 `uv` 项目管理。

首次由仓库维护者执行：

```bash
./scripts/add_openpi_submodule.sh
```

其他开发者通过 `git clone --recurse-submodules` 获取团队已固定的 OpenPI 提交。

# 启用自动测试

将 `tests.yml` 复制到 `.github/workflows/tests.yml` 并提交，即可对 push / pull request 运行 Python 3.10、3.12、3.13 的 Windows 测试。

本次发布凭据没有 GitHub `workflow` 权限，所以仓库先保留模板。通过具有该权限的凭据或 GitHub 网页提交工作流后即可启用。测试代码与本地验证结果已经包含在仓库中。

# mt-hotel-testdata-cli

酒店测试数据构造 CLI 工具。

## 安装

```bash
# 1. 安装（uv 已有的话直接跑，没有先 brew install uv）
uv tool install mt-hotel-testdata-cli --index-url http://pypi.sankuai.com/simple/ --force

# 或
pip install --upgrade mt-hotel-testdata-cli -i http://pypi.sankuai.com/simple --trusted-host pypi.sankuai.com

# 2. 验证
hotel-testdata --help
```

> ⚠️ 安装完成后如果提示 `hotel-testdata: command not found`，执行 `uv tool update-shell` 后重开终端即可。

## 发布新版本

```bash
# 1. 修改 setup.py 中的 version
# 2. 打包
rm -rf dist/
uv build

# 3. 发布（需先在 https://dev.sankuai.com/art/manage/PyPI/token-manage 申请 token）
export UV_PUBLISH_USERNAME=<mis账号>
export UV_PUBLISH_PASSWORD=<token>
uv publish dist/mt_hotel_testdata_cli-*.* --index mt


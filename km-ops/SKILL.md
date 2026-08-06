---
name: km-ops
description: 学城文档相关操作。当用户需要读写、新建、删除、移动、搜索、查看评论时阅读。触发词：学城、wiki、km、km.sankuai.com
---

```bash
alias km='bin/km-darwin-arm64'

# 文档链接 km.sankuai.com/collabpage/1461835105 中 ID 是 1461835105

cat > /tmp/doc.md <<'EOF'
# 技术方案
## 背景
![图](/tmp/photo.png)
EOF
km create < /tmp/doc.md # 自动上传本地图片；可加 --parent 1461835105
# km create --help

km read 1461835105 > /tmp/doc.html # 读取文档
km update 1461835105 < /tmp/doc.html # 更新文档

# 学城 HTML 参考
km template table # 表格
# km template --help # 表格/图片/提示框/折叠块/@人等

# 其它
km ls # 个人空间根目录
km ls 1461835105 # 子文档
km info 1461835105 # 信息
km copy 1461835105 "技术方案-副本" --to 2771969083 # 复制文档到指定父文档
km discussions 1461835105 # 划词评论
km search --keyword "技术方案" # 搜索文档
km --help # 权限/复制/移动/删除/恢复/最近/历史/评论等
```

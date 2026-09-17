#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中心化 SSL 配置模块（infra/ssl_helper.py）。

设计目标：
  1. 统一管理所有 Python 进程发往 yooz.sankuai.com 的 HTTPS 请求的 SSL 策略。
  2. 当前动作为跳过证书链严格校验，因为 Python 运行时默认不包含美团内网 CA。
  3. 预留升级路径：设置环境变量 MEITUAN_CA_PATH 指向内网 CA 证书文件，即可
     切换为完整校验模式，无需修改任何业务代码。

适用场景：
  - urllib.request.urlopen -> 导入 SSL_CONTEXT 作为 context 参数传入
  - requests 库           -> 导入 get_verify_flag() 作为 verify 参数传入

升级路径:
  MEITUAN_CA_PATH 未设置                -> 跳过校验（当前行为）
  MEITUAN_CA_PATH=/path/to/meituan-ca.crt  -> 加载该 CA 证书，完整校验

依赖：
  - 标准库 ssl（Python 3.x 内置，无需额外安装）
"""

import os
import ssl
import warnings

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    import requests.packages.urllib3.exceptions as req_urllib3_exc
    warnings.simplefilter("ignore", req_urllib3_exc.InsecureRequestWarning)
except Exception:
    pass


def _create_ssl_context():
    """创建统一的 SSLContext 实例。

    策略：
      1. 优先检测环境变量 MEITUAN_CA_PATH — 若存在且指向合法 CA 文件，
         则加载该 CA 证书进行完整 SSL 校验（check_hostname=True）。
      2. 否则返回跳过证书校验的 context（CERT_NONE），解决 Python 运行时
         不包含美团内网 CA 根证书导致的 CERTIFICATE_VERIFY_FAILED 异常。
    """
    ca_path = os.environ.get("MEITUAN_CA_PATH", "")

    if ca_path and os.path.isfile(ca_path):
        # 完整校验模式：加载内网 CA 证书
        # 注意：文件内容必须为合法 PEM 格式，否则 create_default_context 会抛异常
        try:
            ctx = ssl.create_default_context(cafile=ca_path)
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            return ctx
        except Exception:
            # 文件存在但内容不是合法 CA 证书时，降级到跳过校验模式
            # 这样用户设置 MEITUAN_CA_PATH 指向错误路径时不会导致服务中断
            pass

    # 跳过校验模式：不验证证书链和主机名
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# 模块级共享实例，各导入方直接使用，避免重复创建
SSL_CONTEXT = _create_ssl_context()


def get_verify_flag():
    """返回 requests 库 verify 参数的值。

    Returns:
        str: 当 MEITUAN_CA_PATH 设置且指向合法 CA 文件时，返回 CA 文件路径
        bool: 否则返回 False 跳过校验
    """
    ca_path = os.environ.get("MEITUAN_CA_PATH", "")
    if ca_path and os.path.isfile(ca_path):
        # 快速验证文件内容是否有 PEM 格式（BEGIN CERTIFICATE 标记）
        try:
            with open(ca_path, "r") as f:
                head = f.read(2048)
            if "BEGIN CERTIFICATE" in head:
                return ca_path
        except Exception:
            pass
    return False

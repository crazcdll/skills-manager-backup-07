#!/usr/bin/env python3
"""
大象消息发送脚本
基于大象开放平台 API
"""

import argparse
import base64
import json
import logging
import mimetypes
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("Error: pip3 install requests", file=sys.stderr)
    sys.exit(1)

try:
    import jwt
except ImportError:
    print("Error: pip3 install PyJWT", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# 发送消息所需的 audience scope（固定值）
_MSG_AUDIENCE = ['com.sankuai.it.ead.citadel', 'xm-xai']

# @所有人 的特殊 uid（Long 类型，-1）
_AT_ALL_UID = -1


class RobotClient:
    """大象机器人客户端"""

    def __init__(self, client_id: str, secret: str, test: bool = False):
        self.client_id = client_id
        self.secret = secret

        if test:
            self.token_url = "https://ssosv.it.test.sankuai.com/sson/auth/oidc/v1/token"
            self.api_base = "https://xopen.xm.test.sankuai.com"
        else:
            self.token_url = "https://ssosv.sankuai.com/sson/auth/oidc/v1/token"
            self.api_base = "https://xopen.sankuai.com"

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'daxiang-sender/1.0'
        })

        self._access_token = None
        self._token_expires_at = None

    def _generate_jwt(self, secret: str, audience: str) -> str:
        """生成 JWT 令牌"""
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(days=1)

        payload = {
            'sub': self.client_id,
            'iss': self.client_id,
            'aud': audience,
            'exp': int(expiration.timestamp()),
            'iat': int(now.timestamp()),
            'jti': str(uuid.uuid4())
        }

        token = jwt.encode(payload, secret.encode('utf-8'), algorithm='HS256')
        return token

    def _get_access_token(self, audience_client_ids: List[str]) -> Optional[str]:
        """获取访问令牌（带缓存）"""
        if self._access_token and self._token_expires_at:
            if datetime.now().timestamp() < self._token_expires_at:
                return self._access_token

        if not audience_client_ids:
            logger.error("参数错误，audience 为空")
            return None

        try:
            scope = ' '.join([f'client_id:{cid}' for cid in audience_client_ids])

            params = {
                'grant_type': 'client_credentials',
                'scope': scope,
                'client_id': self.client_id,
                'client_secret': self.secret,
                'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                'client_assertion': self._generate_jwt(self.secret, self.token_url)
            }

            response = self.session.post(
                self.token_url,
                data=params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()

            data = response.json()

            if 'access_token' in data:
                self._access_token = data['access_token']
                expires_in = data.get('expires_in', 3600)
                # 提前 5 分钟过期，避免边界情况
                self._token_expires_at = datetime.now().timestamp() + expires_in - 300
                return self._access_token
            else:
                logger.error(f"获取访问令牌失败: {data.get('error_description', '未知错误')}")
                return None

        except requests.RequestException as e:
            logger.error(f"请求访问令牌失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取访问令牌发生未知错误: {e}")
            return None

    def get_uid_by_mis(self, mis_list: List[str]) -> Optional[Dict[str, int]]:
        """根据 mis 列表批量获取 uid"""
        if not mis_list:
            logger.error("mis_list 不能为空")
            return None

        try:
            access_token = self._get_access_token(_MSG_AUDIENCE)
            if not access_token:
                return None

            response = self.session.post(
                f"{self.api_base}/open-apis/dx/queryEmpIdentityByMisList",
                headers=self._auth_headers(access_token),
                json={"misList": mis_list}
            )
            response.raise_for_status()

            result = response.json()
            if result.get('status', {}).get('code') == 0:
                raw_data = result.get('data', {}).get('data', {})
                return {
                    mis: info['uid']
                    for mis, info in raw_data.items()
                    if 'uid' in info
                }
            else:
                logger.error(f"根据 mis 获取 uid 失败: {result}")
                return None

        except requests.RequestException as e:
            logger.error(f"请求 mis->uid 失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 mis->uid 发生未知错误: {e}")
            return None

    def _auth_headers(self, access_token: str) -> Dict[str, str]:
        """构造带鉴权的请求头"""
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=utf-8'
        }

    def _send_msg(self, endpoint: str, payload: dict) -> Optional[Dict]:
        """发送消息的公共实现"""
        try:
            access_token = self._get_access_token(_MSG_AUDIENCE)
            if not access_token:
                return None

            url = f"{self.api_base}{endpoint}"
            logger.info(f"📤 请求地址: POST {url}")
            logger.info(f"📦 请求体:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")

            response = self.session.post(
                url,
                headers=self._auth_headers(access_token),
                json=payload
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"发送消息失败: {e}")
            return None
        except Exception as e:
            logger.error(f"发送消息发生未知错误: {e}")
            return None

    def send_chat_msg(self, receiver_ids: List[int], msg_type: str, body: str,
                      extension: dict = None, is_dynamic: bool = False) -> Optional[Dict]:
        """发送个人消息"""
        send_msg_info: dict = {"type": msg_type, "body": body, "isDynamicMsg": is_dynamic}
        if extension:
            send_msg_info["extension"] = extension
        return self._send_msg(
            "/open-apis/dx-msg/sendChatMsgByRobot",
            {"receiverIds": receiver_ids, "sendMsgInfo": send_msg_info}
        )

    def send_group_msg(self, gid: int, msg_type: str, body: str,
                       extension: dict = None, is_dynamic: bool = False) -> Optional[Dict]:
        """发送群组消息"""
        send_msg_info: dict = {"type": msg_type, "body": body, "isDynamicMsg": is_dynamic}
        if extension:
            send_msg_info["extension"] = extension
        return self._send_msg(
            "/open-apis/dx-msg/sendGroupMsgByRobot",
            {"gid": gid, "sendMsgInfo": send_msg_info}
        )

    def list_bot_groups(self, page_size: int = 100) -> Optional[List[Dict]]:
        """查询机器人所在的所有群（自动翻页）"""
        try:
            access_token = self._get_access_token(_MSG_AUDIENCE)
            if not access_token:
                return None

            groups = []
            cursor = None

            while True:
                payload: dict = {"request": {"limit": min(page_size, 100)}}
                if cursor is not None:
                    payload["request"]["cursor"] = cursor

                response = self.session.post(
                    f"{self.api_base}/open-apis/dx/pageQueryBotJoinedGroup",
                    headers=self._auth_headers(access_token),
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                if result.get('status', {}).get('code') != 0:
                    logger.error(f"查询机器人所在群失败: {result.get('status', {}).get('message', result)}")
                    return None

                data = result.get('data', {})
                group_list = data.get('groupList', [])
                groups.extend(group_list)

                next_cursor = data.get('cursor')
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor

            return groups

        except requests.RequestException as e:
            logger.error(f"查询机器人所在群请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"查询机器人所在群发生未知错误: {e}")
            return None


# ── 文件服务常量 ───────────────────────────────────────────────

FILE_UPLOAD_URL = "https://file.vip.sankuai.com/file"
IMG_UPLOAD_URL = "https://file.vip.sankuai.com/file/images"

# 公共文件服务凭证（来自大象开放平台公共存储），可通过环境变量覆盖
FILE_TENANT_ID = os.environ.get("DX_FILE_TENANT_ID", "1501437563754258442")
FILE_ACCESS_KEY = os.environ.get("DX_FILE_TOKEN", "4427e507ade34bd1b216a02558541051")

NO_PROXY = {"http": None, "https": None}


def upload_file(local_path: str, is_image: bool = False) -> dict:
    """上传本地文件到大象文件服务，返回包含文件元信息的字典。

    Returns:
        {
            "file_id": str,       # 文件 ID
            "download_url": str,  # 下载 URL
            "image_url": str,     # 图片 URL（仅图片上传有值）
            "size": int,          # 文件大小（字节）
            "mime": str,          # MIME 类型
            "filename": str,      # 文件名
        }
    """
    url = IMG_UPLOAD_URL if is_image else FILE_UPLOAD_URL
    filename = os.path.basename(local_path)
    mime = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    size = os.path.getsize(local_path)
    biz_id = f"dx-sender-{int(time.time())}"

    logger.info(f"📤 上传{'图片' if is_image else '文件'}: {local_path} ({size} bytes)")
    with open(local_path, "rb") as f:
        resp = requests.post(url, files={"file": (filename, f, mime)}, data={
            "tenantId": FILE_TENANT_ID,
            "accessKey": FILE_ACCESS_KEY,
            "fileName": filename,
            "creator": "daxiang-sender",
            "bizFileId": biz_id,
            "processCommands": "",
        }, timeout=30, proxies=NO_PROXY)

    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"文件上传失败: {data.get('message', resp.text)}")

    file_id = str(data.get("fileId", ""))
    items = data.get("fileItems", [])
    download_url = items[0].get("downloadUrl", "") if items else ""
    image_url = items[0].get("url", "") if items else ""
    logger.info(f"✅ 上传成功 fileId={file_id}")

    return {
        "file_id": file_id,
        "download_url": download_url,
        "image_url": image_url,
        "size": size,
        "mime": mime,
        "filename": filename,
    }


# ── 消息体构建函数 ─────────────────────────────────────────────

def build_text_body(text: str) -> str:
    """构建文本消息体"""
    return json.dumps({"text": text}, ensure_ascii=False)


def build_link_body(title: str, content: str, link: str, image: str) -> str:
    """构建链接消息体（图文卡片）
    注意：image 为必填字段，API 不接受空值。
    """
    return json.dumps({
        "title": title,
        "image": image,
        "content": content or "",
        "link": link,
    }, ensure_ascii=False)


def build_multilink_body(links: list) -> str:
    """构建多图文消息体
    links: [{"title": "", "content": "", "link": "", "image": ""}]
    注意：API 要求 content 字段为 JSON 数组序列化后的字符串（String 类型）。
    """
    content_str = json.dumps(links, ensure_ascii=False)
    return json.dumps({"num": len(links), "content": content_str}, ensure_ascii=False)


def build_file_body(url: str, name: str, size: int, fmt: str, file_id: str = "") -> str:
    """构建文件消息体
    Args:
        url:     文件地址，不能包含中文和服务端口
        name:    文件名
        size:    文件大小（字节）
        fmt:     MIME 类型，如 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
        file_id: 文件 ID，无内容传空字符串
    """
    return json.dumps({
        "id": file_id,
        "url": url,
        "name": name,
        "format": fmt,
        "size": size,
    }, ensure_ascii=False)


def build_image_body(url: str, thumbnail_url: str = None, normal_url: str = None) -> str:
    """构建图片消息体
    Args:
        url:           原图地址（必填）
        thumbnail_url: 缩略图地址，不传则与原图相同
        normal_url:    大图地址，不传则与原图相同
    注意：thumbnail/normal/original 三个字段均为必填。
    """
    thumbnail = thumbnail_url or url
    normal = normal_url or url
    return json.dumps({
        "thumbnail": thumbnail,
        "normal": normal,
        "original": url,
    }, ensure_ascii=False)


def build_vcard_body(uid: int, vcard_type: int = 1) -> str:
    """构建名片消息体
    Args:
        uid:        用户 uid（个人名片）或公众号 pubId（Pub 名片）
        vcard_type: 1=个人名片，2=Pub 名片
    """
    return json.dumps({"uid": uid, "type": vcard_type}, ensure_ascii=False)


def build_gvcard_body(gid: int) -> str:
    """构建群名片消息体"""
    return json.dumps({"guid": gid}, ensure_ascii=False)


def build_quote_body(quoted_msg_id: int, reply_text: str) -> str:
    """构建引用回复消息体（回复内容仅支持 text 类型）
    Args:
        quoted_msg_id: 被引用的消息 ID
        reply_text:    回复的文本内容
    """
    reply_body = json.dumps({"text": reply_text}, ensure_ascii=False)
    return json.dumps({
        "quotedMsgId": quoted_msg_id,
        "replyMsg": {
            "type": "text",
            "body": reply_body,
        },
    }, ensure_ascii=False)


def build_general_body(data: str, sub_type: int = 100, summary: str = None) -> str:
    """构建通用/富文本消息体
    Args:
        data:     消息内容，必须是 Base64 编码的字符串（富文本内容协议 JSON → Base64）
        sub_type: 消息子类型，100=富文本（推荐），11=旧卡片（已停止接入）
        summary:  消息摘要（可选）
    注意：data 字段必须是 Base64 编码，不能直接传明文 JSON。
    """
    body: dict = {"data": data, "type": sub_type}
    if summary:
        body["summary"] = summary
    return json.dumps(body, ensure_ascii=False)


def build_at_text(name: str, uid, is_bot: bool = False) -> str:
    """构建单个 @ 高亮文本片段。
    普通用户：[@名称|mtdaxiang://www.meituan.com/profile?uid=UID&isAt=true]
    机器人：  [@名称|mtdaxiang://www.meituan.com/pub/profile?pubid=ID&isAt=true]
    @所有人： [@所有人|mtdaxiang://www.meituan.com/profile?uid=-1&isAt=true]
    """
    if is_bot:
        url = f"mtdaxiang://www.meituan.com/pub/profile?pubid={uid}&isAt=true"
    else:
        url = f"mtdaxiang://www.meituan.com/profile?uid={uid}&isAt=true"
    return f"[@{name}|{url}]"


# ── 工具函数 ───────────────────────────────────────────────────

def load_config(config_path: str = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = os.path.expanduser("~/.daxiang.json")

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️  配置文件解析失败，已忽略: {e}")
        except Exception as e:
            logger.warning(f"⚠️  读取配置文件失败，已忽略: {e}")
    return {}


def _add_credential_args(parser: argparse.ArgumentParser):
    """为 parser 添加通用凭证参数"""
    parser.add_argument('--client-id', help='Client ID')
    parser.add_argument('--client-secret', help='Client Secret')
    parser.add_argument('--config', help='配置文件路径，默认 ~/.daxiang.json')
    parser.add_argument('--test', action='store_true', help='使用测试环境')
    parser.add_argument('--debug', action='store_true', help='打印调试信息')


def _resolve_credentials(args) -> tuple:
    """从 args / 环境变量 / 配置文件中解析凭证，返回 (client_id, client_secret)"""
    config = load_config(getattr(args, 'config', None))
    client_id = getattr(args, 'client_id', None) or os.environ.get('DX_CLIENT_ID') or config.get('clientId')
    client_secret = getattr(args, 'client_secret', None) or os.environ.get('DX_CLIENT_SECRET') or config.get('clientSecret')
    if not client_id or not client_secret:
        logger.error("❌ 请设置 client-id 和 client-secret")
        logger.error("   方式1: 环境变量 DX_CLIENT_ID, DX_CLIENT_SECRET")
        logger.error("   方式2: 配置文件 ~/.daxiang.json")
        logger.error("   方式3: --client-id xxx --client-secret xxx")
        sys.exit(1)
    return client_id, client_secret


def _resolve_at_uids(client: RobotClient, at_list: List[str]):
    """解析 --at 参数，支持 uid:名称 和 mis:名称 两种格式"""
    uid_list: List[int] = []
    text_parts: List[str] = []

    mis_entries = []
    uid_entries = []

    for entry in at_list:
        parts = entry.split(':', 1)
        if len(parts) != 2 or not parts[0].strip():
            logger.error(f"❌ --at 格式错误，应为 uid:显示名称 或 mis:显示名称，收到: {entry!r}")
            sys.exit(1)
        id_str, name = parts[0].strip(), parts[1].strip()
        if id_str.lstrip('-').isdigit():
            uid_entries.append((int(id_str), name))
        else:
            mis_entries.append((id_str, name))

    if mis_entries:
        mis_ids = [m for m, _ in mis_entries]
        logger.info(f"🔄 --at 转换 mis -> uid: {mis_ids}")
        uid_map = client.get_uid_by_mis(mis_ids)
        if not uid_map:
            logger.error("❌ --at mis -> uid 转换失败")
            sys.exit(1)
        for mis, name in mis_entries:
            if mis not in uid_map:
                logger.error(f"❌ 找不到 mis={mis} 对应的 uid")
                sys.exit(1)
            uid = uid_map[mis]
            logger.info(f"   {mis} -> {uid}")
            uid_entries.append((uid, name))

    for uid, name in uid_entries:
        uid_list.append(uid)
        text_parts.append(build_at_text(name, uid))

    return uid_list, text_parts


def _build_at_extension(client: RobotClient, args) -> tuple:
    """统一处理 @相关 extension 字段，返回 (at_uids, bot_at_ids, at_prefix_parts)"""
    at_uids: List[int] = []
    bot_at_ids: List[int] = []
    at_prefix_parts: List[str] = []

    if getattr(args, 'at_all', False):
        at_uids.append(_AT_ALL_UID)
        at_prefix_parts.append(build_at_text('所有人', _AT_ALL_UID))

    if getattr(args, 'at_list', None):
        uids, parts = _resolve_at_uids(client, args.at_list)
        at_uids.extend(uids)
        at_prefix_parts.extend(parts)

    for entry in (getattr(args, 'bot_at_list', None) or []):
        parts = entry.split(':', 1)
        if len(parts) != 2 or not parts[0].strip():
            logger.error(f"❌ --bot-at 格式错误，应为 机器人id:显示名称，收到: {entry!r}")
            sys.exit(1)
        bot_id, name = parts[0].strip(), parts[1].strip()
        bot_at_ids.append(int(bot_id))
        at_prefix_parts.append(build_at_text(name, bot_id, is_bot=True))

    # --custom-at 参数：清除自动生成的@文本，使text中的自定义@文本生效
    if getattr(args, 'custom_at', False):
        at_prefix_parts = []

    return at_uids, bot_at_ids, at_prefix_parts


def _handle_result(result, target: str):
    """统一处理发送结果"""
    if result:
        status = result.get('status', {})
        if status.get('code') == 0:
            data = result.get('data', {})
            msg_map = data.get('messageMap', {})
            fail_map = data.get('failMap', {})
            if msg_map:
                logger.info(f"✅ 发送成功！{target}")
                logger.info(f"   消息ID: {msg_map}")
            if fail_map:
                logger.error(f"❌ 部分发送失败: {fail_map}")
                sys.exit(1)
        else:
            logger.error(f"❌ 发送失败: {status}")
            sys.exit(1)
    else:
        logger.error("❌ 发送失败")
        sys.exit(1)


# ── send 子命令实现 ────────────────────────────────────────────

def cmd_send(args):
    """执行发送消息子命令"""
    client_id, client_secret = _resolve_credentials(args)
    client = RobotClient(client_id, client_secret, test=args.test)

    msg_type = args.msg_type
    body = None
    base_extension: dict = {}

    # ── 消息体构建 ──────────────────────────────────────────────

    if args.body_file:
        # 自定义消息体文件
        try:
            with open(args.body_file, 'r', encoding='utf-8') as f:
                body = f.read().strip()
            json.loads(body)
        except FileNotFoundError:
            logger.error(f"❌ 消息体文件不存在: {args.body_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"❌ 消息体文件不是合法 JSON: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ 读取消息体文件失败: {e}")
            sys.exit(1)

        if args.markdown:
            base_extension['fileType'] = 'markdown'

        at_uids, bot_at_ids, _ = _build_at_extension(client, args)
        if at_uids:
            base_extension['at'] = at_uids
            logger.info(f"📣 @用户 uid: {at_uids}")
        if bot_at_ids:
            base_extension['botAt'] = bot_at_ids
            logger.info(f"📣 @机器人 id: {bot_at_ids}")

    elif args.link:
        # 图文卡片消息（image 必填）
        if not args.title or not args.url:
            logger.error("❌ 链接消息需要 --title 和 --url")
            sys.exit(1)
        if not args.link_image:
            logger.error("❌ 链接消息 --link-image 为必填字段（API 要求）")
            sys.exit(1)
        msg_type = "link"
        body = build_link_body(args.title, args.content, args.url, args.link_image)

    elif getattr(args, 'file', None):
        # 文件消息（本地文件自动上传）
        file_path = args.file
        if not os.path.isfile(file_path):
            logger.error(f"❌ 文件不存在: {file_path}")
            sys.exit(1)
        try:
            uploaded = upload_file(file_path, is_image=False)
        except Exception as e:
            logger.error(f"❌ 文件上传失败: {e}")
            sys.exit(1)
        msg_type = "file"
        body = build_file_body(
            url=uploaded["download_url"],
            name=uploaded["filename"],
            size=uploaded["size"],
            fmt=uploaded["mime"],
            file_id=uploaded["file_id"],
        )

    elif args.file_url:
        # 文件消息（已有 URL，无需上传）
        if not args.file_name:
            logger.error("❌ 文件消息需要 --file-name")
            sys.exit(1)
        msg_type = "file"
        body = build_file_body(
            url=args.file_url,
            name=args.file_name,
            size=args.file_size or 0,
            fmt=args.file_format or "application/octet-stream",
            file_id=args.file_id or "",
        )

    elif getattr(args, 'image', None):
        # 图片消息（本地图片自动上传）
        image_path = args.image
        if not os.path.isfile(image_path):
            logger.error(f"❌ 图片文件不存在: {image_path}")
            sys.exit(1)
        try:
            uploaded = upload_file(image_path, is_image=True)
        except Exception as e:
            logger.error(f"❌ 图片上传失败: {e}")
            sys.exit(1)
        msg_type = "image"
        body = build_image_body(
            url=uploaded["image_url"],
        )

    elif args.image_url:
        # 图片消息（已有 URL，无需上传）
        msg_type = "image"
        body = build_image_body(
            url=args.image_url,
            thumbnail_url=args.image_thumbnail,
            normal_url=args.image_normal,
        )

    elif args.vcard_uid is not None:
        # 名片消息
        msg_type = "vcard"
        body = build_vcard_body(args.vcard_uid, args.vcard_type)

    elif args.gvcard_gid is not None:
        # 群名片消息
        msg_type = "gvcard"
        body = build_gvcard_body(args.gvcard_gid)

    elif args.quote_msg_id is not None:
        # 引用回复消息
        if not args.reply_text:
            logger.error("❌ 引用回复需要 --reply-text")
            sys.exit(1)
        msg_type = "quote"
        body = build_quote_body(args.quote_msg_id, args.reply_text)

    elif args.general_data:
        # 通用/富文本消息（data 必须是 Base64 编码）
        msg_type = "general"
        # 如果传入的是明文 JSON，自动 Base64 编码
        data_str = args.general_data
        try:
            # 尝试解析，如果是合法 JSON 且不是 Base64，则自动编码
            json.loads(data_str)
            # 是合法 JSON，自动 Base64 编码
            data_b64 = base64.b64encode(data_str.encode('utf-8')).decode('ascii')
            logger.info("ℹ️  检测到明文 JSON，已自动 Base64 编码")
        except json.JSONDecodeError:
            # 不是 JSON，当作已编码的 Base64 直接使用
            data_b64 = data_str
        body = build_general_body(data_b64, args.general_type, args.general_summary)
        is_dynamic = args.general_type == 11  # type=11 旧卡片必须 isDynamicMsg=true

    elif args.custom_template:
        # 模板消息（custom）
        if not args.custom_title or not args.custom_content:
            logger.error("❌ 模板消息需要 --custom-title 和 --custom-content")
            sys.exit(1)
        msg_type = "custom"
        custom_body: dict = {
            "templateName": args.custom_template,
            "contentTitle": args.custom_title,
            "content": args.custom_content,
        }
        if args.custom_link_name:
            custom_body["linkName"] = args.custom_link_name
        if args.custom_link:
            custom_body["link"] = args.custom_link
        body = json.dumps(custom_body, ensure_ascii=False)

        # extension.custom 扩展（按钮、详情链接）
        ext_custom: dict = {"version": 1, "type": 1}
        if args.custom_clink_name and args.custom_clink_url:
            ext_custom["clink"] = {"name": args.custom_clink_name, "link": args.custom_clink_url}
        if args.custom_buttons:
            buttons = []
            for btn_str in args.custom_buttons:
                # 格式：按钮文字|action_url[|PRIMARY|DANGER]
                # 使用 | 分隔，避免与 URL 中的 : 冲突
                parts = btn_str.split('|', 2)
                if len(parts) < 2:
                    logger.error(f"❌ --custom-button 格式错误，应为 文字|action_url[|PRIMARY|DANGER]，收到: {btn_str!r}")
                    sys.exit(1)
                btn_label = parts[0]
                btn_action = parts[1]
                btn_type = parts[2].upper() if len(parts) > 2 else "PRIMARY"
                buttons.append({"button": btn_label, "action": btn_action, "type": btn_type})
            ext_custom["buttons"] = buttons
        if len(ext_custom) > 2:  # 有实质内容（超过 version+type）
            base_extension['custom'] = ext_custom

    elif args.text is not None:
        # 文本消息
        msg_type = "text"
        at_uids, bot_at_ids, at_prefix_parts = _build_at_extension(client, args)

        prefix = ' '.join(at_prefix_parts)
        text_with_at = (prefix + ' ' + args.text) if prefix else args.text
        body = build_text_body(text_with_at)

        if args.markdown:
            base_extension['fileType'] = 'markdown'
        if at_uids:
            base_extension['at'] = at_uids
            logger.info(f"📣 @用户 uid: {at_uids}")
        if bot_at_ids:
            base_extension['botAt'] = bot_at_ids
            logger.info(f"📣 @机器人 id: {bot_at_ids}")

    else:
        logger.error("❌ 请指定消息内容（--text / --file / --file-url / --image / --image-url / --link / --vcard-uid / --gvcard-gid / --quote-msg-id / --general-data / --custom-template / --body-file）")
        sys.exit(1)

    if body is None:
        logger.error("❌ 消息体构建失败")
        sys.exit(1)

    extension = base_extension if base_extension else None
    is_dynamic = getattr(args, 'dynamic', False)
    # general type=11 强制 isDynamicMsg=true
    if msg_type == 'general' and args.general_type == 11:
        is_dynamic = True

    # ── 发送 ────────────────────────────────────────────────────
    if args.to:
        receivers = [r.strip() for r in args.to.split(',') if r.strip()]
        receiver_ids: List[int] = []
        mis_list = []

        for r in receivers:
            if r.lstrip('-').isdigit():
                receiver_ids.append(int(r))
            else:
                mis_list.append(r)

        if mis_list:
            logger.info(f"🔄 转换 mis -> uid: {mis_list}")
            uid_map = client.get_uid_by_mis(mis_list)
            if not uid_map:
                logger.error("❌ mis -> uid 转换失败")
                sys.exit(1)
            for mis in mis_list:
                if mis in uid_map:
                    receiver_ids.append(uid_map[mis])
                    logger.info(f"   {mis} -> {uid_map[mis]}")
                else:
                    logger.error(f"❌ 找不到 mis={mis} 对应的 uid")
                    sys.exit(1)

        result = client.send_chat_msg(receiver_ids, msg_type, body, extension, is_dynamic)
        target = f"用户 {receiver_ids}"
    else:
        result = client.send_group_msg(int(args.group), msg_type, body, extension, is_dynamic)
        target = f"群组 {args.group}"

    _handle_result(result, target)


def cmd_list_groups(args):
    """执行 list-groups 子命令：查询机器人所在群列表"""
    client_id, client_secret = _resolve_credentials(args)
    client = RobotClient(client_id, client_secret, test=args.test)

    logger.info("🔍 查询机器人所在群列表...")
    groups = client.list_bot_groups()

    if groups is None:
        logger.error("❌ 查询失败")
        sys.exit(1)

    if not groups:
        logger.info("ℹ️  该机器人尚未加入任何群")
        return

    logger.info(f"✅ 共找到 {len(groups)} 个群：\n")

    if args.json:
        print(json.dumps(
            [{"name": g.get("name", ""), "gid": g.get("gid")} for g in groups],
            ensure_ascii=False, indent=2
        ))
    else:
        max_name_len = max((len(g.get("name", "")) for g in groups), default=10)
        header = f"{'群名':<{max_name_len}}  group_id"
        logger.info(header)
        logger.info("-" * (max_name_len + 20))
        for g in groups:
            name = g.get("name", "(无名)")
            gid = g.get("gid", "")
            logger.info(f"{name:<{max_name_len}}  {gid}")


def main():
    parser = argparse.ArgumentParser(
        description='大象消息工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', metavar='COMMAND')
    subparsers.required = True

    # ── send 子命令 ──────────────────────────────────────────────
    send_parser = subparsers.add_parser(
        'send',
        help='发送消息',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 文本消息
  python3 send.py send --to suhao20 --text "Hello"

  # Markdown 消息
  python3 send.py send --to suhao20 --text "**加粗**" --markdown

  # 链接卡片（image 必填）
  python3 send.py send --to suhao20 --link --title "标题" --url "https://example.com" --link-image "https://example.com/cover.jpg"

  # 文件消息（本地文件自动上传）
  python3 send.py send --to suhao20 --file /path/to/report.xlsx

  # 文件消息（已有 URL）
  python3 send.py send --to suhao20 --file-url "https://example.com/file.xlsx" --file-name "报告.xlsx" --file-size 3296 --file-format "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

  # 图片消息（本地图片自动上传）
  python3 send.py send --to suhao20 --image /path/to/photo.jpg

  # 图片消息（已有 URL）
  python3 send.py send --to suhao20 --image-url "https://example.com/photo.jpg"

  # 名片消息
  python3 send.py send --to suhao20 --vcard-uid 2967510770

  # 群名片消息
  python3 send.py send --to suhao20 --gvcard-gid 70473524669

  # 引用回复（需提供被引用消息 ID）
  python3 send.py send --to suhao20 --quote-msg-id 1733381024879706115 --reply-text "收到！"

  # 模板消息（带按钮）
  python3 send.py send --to suhao20 --custom-template "审批通知" --custom-title "每日报销" --custom-content "请及时处理" --custom-button "通过|mtdaxiang://approve|PRIMARY" --custom-button "驳回|mtdaxiang://reject|DANGER"

  # 富文本消息（general type=100，data 自动 Base64 编码）
  python3 send.py send --to suhao20 --general-data '{"nodes":[{"t":"text","c":"Hello"}]}'

  # @某人
  python3 send.py send --group 69662141203 --text "请处理" --at suhao20:苏灏

  # @所有人
  python3 send.py send --group 69662141203 --text "大家注意" --at-all

  # 动态消息
  python3 send.py send --group 69662141203 --text "动态消息" --dynamic
        """
    )
    _add_credential_args(send_parser)

    target_group = send_parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument('--to', '-u', help='接收用户（mis 号或 uid），多个用逗号分隔')
    target_group.add_argument('--group', '-g', help='群组 ID (gid)')

    # ── 消息类型参数（互斥组） ────────────────────────────────────
    msg_group = send_parser.add_mutually_exclusive_group(required=True)
    msg_group.add_argument('--text', '-t', help='文本消息内容')
    msg_group.add_argument('--link', '-l', action='store_true', help='链接消息模式（需配合 --title --url --link-image）')
    msg_group.add_argument('--body-file', '-f', help='自定义消息体 JSON 文件路径（需配合 --msg-type）')
    msg_group.add_argument('--file', help='文件消息：本地文件路径（自动上传到文件服务）')
    msg_group.add_argument('--file-url', help='文件消息：文件地址 URL（不能含中文和端口）')
    msg_group.add_argument('--image', help='图片消息：本地图片路径（自动上传到文件服务）')
    msg_group.add_argument('--image-url', help='图片消息：原图地址 URL')
    msg_group.add_argument('--vcard-uid', type=int, help='名片消息：用户 uid 或公众号 pubId')
    msg_group.add_argument('--gvcard-gid', type=int, help='群名片消息：群 ID')
    msg_group.add_argument('--quote-msg-id', type=int, help='引用回复：被引用的消息 ID')
    msg_group.add_argument('--general-data', help='通用/富文本消息：内容（明文 JSON 自动 Base64 编码）')
    msg_group.add_argument('--custom-template', help='模板消息：模板名称')

    # ── 文本/Markdown 修饰 ───────────────────────────────────────
    send_parser.add_argument('--markdown', action='store_true', help='以 Markdown 渲染文本（--text 模式）')
    send_parser.add_argument('--dynamic', action='store_true',
                             help='发送动态消息（isDynamicMsg=true），后续可更新/撤回')

    # ── link 消息参数 ────────────────────────────────────────────
    link_group = send_parser.add_argument_group('link 消息参数')
    link_group.add_argument('--title', help='链接标题（--link 必填）')
    link_group.add_argument('--content', help='链接描述（--link 可选）')
    link_group.add_argument('--url', help='链接地址（--link 必填）')
    link_group.add_argument('--link-image', help='链接封面图 URL（--link 必填，API 要求）')

    # ── file 消息参数 ────────────────────────────────────────────
    file_group = send_parser.add_argument_group('file 消息参数')
    file_group.add_argument('--file-name', help='文件名')
    file_group.add_argument('--file-size', type=int, help='文件大小（字节）')
    file_group.add_argument('--file-format', help='MIME 类型，如 application/pdf')
    file_group.add_argument('--file-id', default='', help='文件 ID（可选，默认空字符串）')

    # ── image 消息参数 ───────────────────────────────────────────
    image_group = send_parser.add_argument_group('image 消息参数')
    image_group.add_argument('--image-thumbnail', help='缩略图地址（不传则与 --image-url 相同）')
    image_group.add_argument('--image-normal', help='大图地址（不传则与 --image-url 相同）')

    # ── vcard 消息参数 ───────────────────────────────────────────
    vcard_group = send_parser.add_argument_group('vcard 消息参数')
    vcard_group.add_argument('--vcard-type', type=int, default=1,
                             help='名片类型：1=个人名片（默认），2=Pub 名片')

    # ── quote 消息参数 ───────────────────────────────────────────
    quote_group = send_parser.add_argument_group('quote 引用回复参数')
    quote_group.add_argument('--reply-text', help='引用回复的文本内容（--quote-msg-id 必填）')

    # ── general 消息参数 ─────────────────────────────────────────
    general_group = send_parser.add_argument_group('general 通用/富文本消息参数')
    general_group.add_argument('--general-type', type=int, default=100,
                               help='消息子类型：100=富文本（默认），11=旧卡片（已停止接入）')
    general_group.add_argument('--general-summary', help='消息摘要（可选）')

    # ── custom 模板消息参数 ──────────────────────────────────────
    custom_group = send_parser.add_argument_group('custom 模板消息参数')
    custom_group.add_argument('--custom-title', help='模板消息标题（contentTitle）')
    custom_group.add_argument('--custom-content', help='模板消息内容')
    custom_group.add_argument('--custom-link-name', help='底部链接名称')
    custom_group.add_argument('--custom-link', help='底部链接地址')
    custom_group.add_argument('--custom-clink-name', help='extension.custom.clink 详情链接名称')
    custom_group.add_argument('--custom-clink-url', help='extension.custom.clink 详情链接地址')
    custom_group.add_argument('--custom-button', metavar='文字|action[|PRIMARY|DANGER]',
                              action='append', dest='custom_buttons',
                              help='操作按钮，格式：按钮文字|action_url[|PRIMARY|DANGER]，可多次使用')

    # ── body-file 消息参数 ───────────────────────────────────────
    send_parser.add_argument('--msg-type', default='text',
                             help='消息类型，配合 --body-file 使用（如 multilink），默认 text')

    # ── @ 提及参数 ───────────────────────────────────────────────
    at_group = send_parser.add_argument_group('@提及')
    at_group.add_argument('--at', metavar='ID:NAME', action='append', dest='at_list',
                          help='@某人，格式 uid:显示名称 或 mis:显示名称（自动转换），可多次使用')
    at_group.add_argument('--at-all', action='store_true', help='@所有人（仅群消息有效）')
    at_group.add_argument('--bot-at', metavar='BOTID:NAME', action='append', dest='bot_at_list',
                          help='@机器人，格式 机器人id:显示名称，可多次使用')
    at_group.add_argument('--custom-at', action='store_true',
                          help='配合--at使用，自定义@某人在text中的位置')

    send_parser.set_defaults(func=cmd_send)

    # ── list-groups 子命令 ───────────────────────────────────────
    lg_parser = subparsers.add_parser(
        'list-groups',
        help='查询机器人所在的所有群，输出群名和 group_id 映射',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 send.py list-groups
  python3 send.py list-groups --json
        """
    )
    _add_credential_args(lg_parser)
    lg_parser.add_argument('--json', action='store_true', help='以 JSON 格式输出结果')
    lg_parser.set_defaults(func=cmd_list_groups)

    # ── 兼容旧用法（无子命令时默认走 send）────────────────────────
    known_commands = {'send', 'list-groups'}
    if len(sys.argv) > 1 and sys.argv[1] not in known_commands and not sys.argv[1].startswith('-'):
        sys.argv.insert(1, 'send')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    args.func(args)


if __name__ == '__main__':
    main()

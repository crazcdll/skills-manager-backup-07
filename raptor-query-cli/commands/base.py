"""
命令基类
"""
import argparse
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from client import RaptorClient


class Command(ABC):
    """命令基类"""
    
    name: str = ""
    help_text: str = ""
    
    def __init__(self, client: "RaptorClient"):
        self.client = client
    
    @abstractmethod
    def run(self, args):
        """执行命令"""
        pass
    
    @staticmethod
    @abstractmethod
    def add_parser(subparsers) -> argparse.ArgumentParser:
        """添加子命令解析器"""
        pass

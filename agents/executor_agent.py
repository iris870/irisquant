#!/usr/bin/env python3
"""
执行 Agent - 运维操作执行器
"""

import sys
import subprocess
import logging
import shutil
from datetime import datetime
from pathlib import Path

# 确保可以导入 core 模块
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from core.data_recorder import get_recorder
except ImportError:
    # 兼容性处理，如果 data_recorder 不可用则不报错
    get_recorder = lambda: None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExecutorAgent:
    def __init__(self):
        self.recorder = get_recorder()
        self.project_root = Path(__file__).parent.parent

    def record_event(self, event_type, target, status):
        """记录系统事件到数据库"""
        if self.recorder and hasattr(self.recorder, 'record_system_event'):
            self.recorder.record_system_event(event_type, target, status)

    def restart_agent(self, agent_name):
        """重启指定 Agent"""
        try:
            result = subprocess.run(
                ['pm2', 'restart', agent_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            if success:
                logger.info(f"✅ 已重启 {agent_name}")
                self.record_event('restart', agent_name, 'success')
            else:
                logger.error(f"❌ 重启 {agent_name} 失败: {result.stderr}")
                self.record_event('restart_failed', agent_name, result.stderr.strip())
            return {'success': success, 'output': result.stdout.strip(), 'error': result.stderr.strip()}
        except Exception as e:
            logger.error(f"重启异常: {e}")
            return {'success': False, 'error': str(e)}

    def git_commit(self, message="auto-update"):
        """Git 提交"""
        try:
            # 先检查是否有变化
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if not status_result.stdout.strip():
                logger.info("无变化，跳过提交")
                return {'success': True, 'output': 'nothing to commit'}

            subprocess.run(['git', 'add', '.'], cwd=self.project_root, check=True, capture_output=True)
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"✅ Git 提交: {message}")
                self.record_event('git_commit', 'repository', 'success')
                return {'success': True, 'output': result.stdout.strip()}
            else:
                return {'success': False, 'output': result.stdout.strip(), 'error': result.stderr.strip()}
        except Exception as e:
            logger.error(f"Git 提交异常: {e}")
            return {'success': False, 'error': str(e)}

    def git_push(self):
        """Git 推送"""
        try:
            result = subprocess.run(
                ['git', 'push'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            success = result.returncode == 0
            if success:
                logger.info("✅ Git 推送成功")
                self.record_event('git_push', 'repository', 'success')
                return {'success': success, 'output': result.stdout.strip()}
            else:
                logger.error(f"❌ Git 推送失败: {result.stderr}")
                return {'success': False, 'output': result.stdout.strip(), 'error': result.stderr.strip()}
        except Exception as e:
            logger.error(f"Git 推送异常: {e}")
            return {'success': False, 'error': str(e)}

    def cleanup_logs(self, days=30):
        """清理旧日志"""
        log_dir = self.project_root / 'logs'
        if not log_dir.exists():
            return {'success': True, 'deleted': 0, 'message': 'Log directory does not exist'}

        cutoff = datetime.now().timestamp() - (days * 86400)
        deleted = 0
        for f in log_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        
        if deleted > 0:
            logger.info(f"清理了 {deleted} 个日志文件")
            self.record_event('cleanup_logs', 'logs', f'deleted {deleted}')
        return {'success': True, 'deleted': deleted}

    def backup_db(self):
        """备份数据库"""
        db_path = self.project_root / 'data' / 'rl_data.db'
        backup_dir = self.project_root / 'data' / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)

        if not db_path.exists():
            return {'success': False, 'error': '数据库不存在'}

        backup_name = f"rl_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = backup_dir / backup_name
        try:
            shutil.copy2(db_path, backup_path)
            logger.info(f"✅ 备份到 {backup_path}")
            self.record_event('backup_db', 'database', 'success')
            return {'success': True, 'backup': str(backup_path)}
        except Exception as e:
            logger.error(f"备份异常: {e}")
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', required=True,
                        choices=['restart', 'commit', 'push', 'cleanup', 'backup'])
    parser.add_argument('--agent', default=None)
    parser.add_argument('--message', default='auto-update')
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()

    executor = ExecutorAgent()

    if args.action == 'restart':
        if not args.agent:
            print({'success': False, 'error': '需要 --agent 参数'})
        else:
            print(executor.restart_agent(args.agent))
    elif args.action == 'commit':
        print(executor.git_commit(args.message))
    elif args.action == 'push':
        print(executor.git_push())
    elif args.action == 'cleanup':
        print(executor.cleanup_logs(args.days))
    elif args.action == 'backup':
        print(executor.backup_db())

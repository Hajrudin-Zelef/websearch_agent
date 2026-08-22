"""
Wrappers pour yt-dlp et xreach avec credentials depuis settings.json.
"""

import logging
import os
import subprocess

logger = logging.getLogger("websearch-agent.agent-reach.wrappers")


def _get_credential(key: str) -> str:
    """Lit un credential depuis settings.json (section api_keys)."""
    try:
        from core.settings import _get_setting
        return _get_setting("api_keys", key, "") or ""
    except Exception:
        return ""


def yt_dlp_command(args: list[str]) -> list[str]:
    """
    Wrapper yt-dlp qui injecte --cookies si YT_DLP_COOKIES_FILE est defini.
    """
    cookies_file = _get_credential("YT_DLP_COOKIES_FILE")
    
    if cookies_file and cookies_file != "***" and os.path.isfile(cookies_file):
        cmd = ["yt-dlp", "--cookies", cookies_file] + args
        logger.debug("yt-dlp avec cookies: %s", cookies_file)
    else:
        cmd = ["yt-dlp"] + args
        if cookies_file and cookies_file != "***":
            logger.warning("YT_DLP_COOKIES_FILE non trouvable: %s", cookies_file)
    
    return cmd


def xreach_command(args: list[str]) -> list[str]:
    """
    Wrapper xreach qui injecte --cookies si TWITTER_COOKIES_FILE est defini.
    """
    cookies_file = _get_credential("TWITTER_COOKIES_FILE")
    
    if cookies_file and cookies_file != "***" and os.path.isfile(cookies_file):
        cmd = ["xreach", "--cookies", cookies_file] + args
        logger.debug("xreach avec cookies: %s", cookies_file)
    else:
        cmd = ["xreach"] + args
        if cookies_file and cookies_file != "***":
            logger.warning("TWITTER_COOKIES_FILE non trouvable: %s", cookies_file)
    
    return cmd


def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """
    Execute une commande et retourne (returncode, stdout, stderr).
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Commande timeout"
    except FileNotFoundError:
        return -1, "", f"Commande non trouvee: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)

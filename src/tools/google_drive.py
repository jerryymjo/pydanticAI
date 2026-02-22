"""Google Drive tool."""

from agent import agent
from tools._gog import _base_args, _run_and_format


@agent.tool_plain
async def drive(
    action: str,
    query: str = '',
    item_id: str = '',
) -> str:
    """Google Drive CLI.

    Args:
        action: ls, search, get, download, upload, mkdir, delete
        query: 검색어 (search, ls)
        item_id: fileId (get/download/delete)
    """
    args = _base_args() + ['drive', action]

    # --- positional args ---
    if action == 'search' and query:
        args.append(query)
    elif action in ('get', 'download', 'delete') and item_id:
        args.append(item_id)

    # --- ls --query 플래그 ---
    if action == 'ls' and query:
        args.append(f'--query={query}')

    return await _run_and_format('drive', action, args)

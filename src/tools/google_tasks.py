"""Google Tasks tool."""

from agent import agent
from tools._gog import _base_args, _run_and_format


@agent.tool_plain
async def tasks(
    action: str,
    title: str = '',
    notes: str = '',
    due: str = '',
    list_id: str = '',
    item_id: str = '',
) -> str:
    """Google Tasks CLI.

    Args:
        action: lists, list, add, get, update, done, delete
        title: 할일 제목 (add/update)
        notes: 메모 (add/update)
        due: 마감일 YYYY-MM-DD (add/update)
        list_id: 목록 ID (기본: 첫번째 목록)
        item_id: taskId (get/update/done/delete)
    """
    args = _base_args() + ['tasks', action]

    # --- positional args ---
    if action in ('list', 'add', 'create') and list_id:
        args.append(list_id)
    elif action in ('get', 'done', 'delete', 'update') and list_id:
        args.append(list_id)
        if item_id:
            args.append(item_id)

    # --- add/create/update 플래그 ---
    if action in ('add', 'create', 'update'):
        if title:
            args.append(f'--title={title}')
        if notes:
            args.append(f'--notes={notes}')
        if due:
            args.append(f'--due={due}')

    return await _run_and_format('tasks', action, args)

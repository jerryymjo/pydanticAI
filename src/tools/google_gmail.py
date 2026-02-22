"""Google Gmail tool."""

from agent import agent
from tools._gog import _base_args, _run_and_format


@agent.tool_plain
async def gmail(
    action: str,
    query: str = '',
    to_email: str = '',
    cc: str = '',
    subject: str = '',
    body: str = '',
    item_id: str = '',
) -> str:
    """Google Gmail CLI.

    Args:
        action: list (받은편지함), search (Gmail 검색 구문), send, get
        query: Gmail 검색 구문 (in:inbox, from:xxx 등)
        to_email: 수신자 (쉼표 구분)
        cc: CC (쉼표 구분)
        subject: 제목 (send)
        body: 본문 (send)
        item_id: messageId (get)
    """
    # list → search 변환
    if action == 'list':
        action = 'search'
        if not query:
            query = 'in:inbox'

    args = _base_args() + ['gmail', action]

    # --- positional args ---
    if action == 'get' and item_id:
        args.append(item_id)
    elif action == 'search' and query:
        args.append(query)

    # --- send 플래그 ---
    if action == 'send':
        if to_email:
            args.append(f'--to={to_email}')
        if cc:
            args.append(f'--cc={cc}')
        if subject:
            args.append(f'--subject={subject}')
        if body:
            args.append(f'--body={body}')

    return await _run_and_format('gmail', action, args)

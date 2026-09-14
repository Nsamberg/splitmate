from pathlib import Path
from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .models import Member
from .security import pop_flashes

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def render(
    request: Request,
    template_name: str,
    context: Optional[dict] = None,
    member: Optional[Member] = None,
):
    ctx = {"member": member, "flashes": pop_flashes(request)}
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request, template_name, ctx)

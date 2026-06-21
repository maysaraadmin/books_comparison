from django import template
from django.utils.html import escape

register = template.Library()

@register.filter
def colored_diff(diff_text):
    """Convert unified diff to HTML with green/red highlighting."""
    if not diff_text:
        return ""

    lines = diff_text.splitlines()
    html_lines = []
    for line in lines:
        escaped = escape(line)
        if line.startswith('+'):
            html_lines.append(f'<div class="diff-added">{escaped}</div>')
        elif line.startswith('-'):
            html_lines.append(f'<div class="diff-deleted">{escaped}</div>')
        elif line.startswith('@@') or line.startswith('---') or line.startswith('+++'):
            html_lines.append(f'<div class="diff-header">{escaped}</div>')
        else:
            html_lines.append(f'<div class="diff-context">{escaped}</div>')
    return '\n'.join(html_lines)
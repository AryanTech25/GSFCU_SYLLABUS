from django import template
from django.utils.html import escape, format_html, mark_safe

register = template.Library()


@register.filter(name='split')
def split_filter(value, arg):
    """Splits a string by the given delimiter and returns a list.

    Usage in templates:
        {{ some_string|split:" " }}
        {% with parts=some_string|split:" " %}...{% endwith %}
    """
    return value.split(arg)


# ---------------------------------------------------------------------------
# audit_value — human-readable rendering of SyllabusEditLog old/new values
# ---------------------------------------------------------------------------

_LABEL_MAP = {
    'text': 'Text',
    'blooms_domain': "Bloom's Domain",
    'blooms_level':  "Bloom's Level",
    'unit_title': 'Unit Title',
    'hours': 'Hours',
    'unit_number': 'Unit No.',
    'pr_number': 'Pr. No.',
    'title': 'Title',
    'description': 'Description',
    'marks': 'Marks',
    'co_number': 'CO No.',
    'statement': 'Statement',
    'action': 'Action',
    'record_id': 'Record ID',
    'data': 'Data',
}


def _label(key):
    return _LABEL_MAP.get(key, key.replace('_', ' ').title())


def _fmt_scalar(val):
    if val is None:
        return '<span style="color:#bbb;font-style:italic;">—</span>'
    text = str(val)
    if len(text) > 120:
        escaped = escape(text[:120])
        full = escape(text)
        return f'<span title="{full}">{escaped}&hellip;</span>'
    return escape(text)


def _fmt_dict(d, depth=0):
    if not d:
        return '<span style="color:#bbb;font-style:italic;">empty</span>'
    rows = []
    for k, v in d.items():
        label = escape(_label(k))
        if isinstance(v, dict):
            cell = _fmt_dict(v, depth + 1)
        elif isinstance(v, list):
            cell = _fmt_list(v, depth + 1)
        else:
            cell = _fmt_scalar(v)
        rows.append(
            f'<tr>'
            f'<td style="padding:1px 6px 1px 0;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:top">{label}</td>'
            f'<td style="padding:1px 0;word-break:break-word;">{cell}</td>'
            f'</tr>'
        )
    inner = ''.join(rows)
    return f'<table style="border-collapse:collapse;font-size:.8rem;">{inner}</table>'


def _fmt_list(lst, depth=0):
    if not lst:
        return '<span style="color:#bbb;font-style:italic;">empty list</span>'
    if all(isinstance(i, dict) for i in lst):
        count = len(lst)
        badge = (
            f'<span style="display:inline-block;background:#e0f2fe;color:#0369a1;'
            f'padding:1px 6px;border-radius:9999px;font-size:.75rem;font-weight:700;">'
            f'{count} item{"s" if count != 1 else ""}</span>'
        )
        if depth > 0 or count > 3:
            return badge
        previews = []
        for item in lst[:3]:
            previews.append(_fmt_dict(item, depth + 1))
        sep = '<hr style="margin:4px 0;border:none;border-top:1px dashed #e2e8f0;">'
        body = sep.join(previews)
        suffix = f'{sep}<span style="color:#94a3b8;font-size:.75rem;">+ {count-3} more</span>' if count > 3 else ''
        return f'{badge}<div style="margin-top:4px">{body}{suffix}</div>'
    # Plain list of scalars
    items = ', '.join(_fmt_scalar(i) for i in lst[:8])
    more = f' <span style="color:#94a3b8">+{len(lst)-8} more</span>' if len(lst) > 8 else ''
    return items + more


@register.filter(name='audit_value', is_safe=True)
def audit_value(val):
    """
    Render a SyllabusEditLog old_value / new_value as human-readable HTML.

    Usage in template:
        {{ log.old_value|audit_value }}
    """
    if val is None:
        return mark_safe('<span style="color:#bbb;font-style:italic;">—</span>')
    if isinstance(val, dict):
        return mark_safe(_fmt_dict(val))
    if isinstance(val, list):
        return mark_safe(_fmt_list(val))
    return mark_safe(_fmt_scalar(val))

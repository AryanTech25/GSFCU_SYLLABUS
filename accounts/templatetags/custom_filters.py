from django import template

register = template.Library()


@register.filter(name='split')
def split_filter(value, arg):
    """Splits a string by the given delimiter and returns a list.

    Usage in templates:
        {{ some_string|split:" " }}
        {% with parts=some_string|split:" " %}...{% endwith %}
    """
    return value.split(arg)

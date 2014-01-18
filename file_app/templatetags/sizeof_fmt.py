from django import template

register = template.Library()

# user-friendly file sizes
# from http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
@register.filter
def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

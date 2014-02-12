from django.contrib import admin
from file_app.models import *

admin.site.register(FileNode)
admin.site.register(DirNode)
admin.site.register(UserTOTP)

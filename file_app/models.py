from django.db import models

class BaseNode(models.Model):
  parent = models.ForeignKey("file_app.DirNode", null=True)
  nodeID = models.CharField(max_length=32, unique=True)
  visibleName = models.CharField(max_length=65535) # name displayed on view
  slug = models.CharField(max_length=65535) # shortcut to node
  createdOn = models.DateTimeField(auto_now_add=True)
  lastModified = models.DateTimeField(auto_now=True)
  
  class Meta:
    abstract = True

class DirNode(BaseNode):
  pass

class FileNode(BaseNode):
  fileSignature = models.CharField(max_length=64)
  mimeType = models.CharField(max_length=65535)
  fileSize = models.BigIntegerField(default=0)


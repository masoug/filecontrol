from django.db import models

class FileNode(models.Model):
    visibleName = models.CharField(max_length=65535) # name displayed on view
    nodeID = models.CharField(max_length=32)
    fileSignature = models.CharField(max_length=64)
    mimeType = models.CharField(max_length=65535)
    fileSize = models.BigIntegerField()
 

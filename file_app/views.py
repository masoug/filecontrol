from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.core.files.uploadhandler import FileUploadHandler
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.urlresolvers import reverse
import os, uuid
from Crypto.Hash import HMAC, SHA256
from file_app.models import *
from file_app.recaptcha import RecaptchaClient

# TODO: These will eventually live in settings.py
FILE_STORAGE_PATH = (
  "/home/sammy/Web/filecontrol/",
  "/cs/student/masoug/filecontrol",
)
for pth in FILE_STORAGE_PATH:
  if os.path.isdir(pth):
    FILE_STORAGE_PATH = pth
    break

# TODO: make hmac secret as long as the digest
FILE_HMAC_SECRET = b"hmacsecret"
RECAPTCHA_PUBLIC_KEY = "6LeALu0SAAAAAKJ7blSSdNo_2HG9nh7hMgt4MhnE"
RECAPTCHA_PRIVATE_KEY = "6LeALu0SAAAAACjaqanZ5gTkv2RVIGRhNn5PQP1X"

# user-friendly file sizes
# from http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size
def sizeof_fmt(num):
  for x in ['bytes','KB','MB','GB']:
    if num < 1024.0 and num > -1024.0:
      return "%3.1f%s" % (num, x)
    num /= 1024.0
  return "%3.1f%s" % (num, 'TB')

# generates list for breadcrumbs
def gen_breadcrumbs(node_id, currList=None):
  if DirNode.objects.filter(nodeID=node_id).exists():
    activeDir = DirNode.objects.get(nodeID=node_id)
    if not currList:
      currList = list()
    currList.insert(0, activeDir)
    if activeDir.parent:
      return gen_breadcrumbs(activeDir.parent.nodeID, currList)
    else:
      return currList
  else:
    return currList

# Custom upload handler
class DirectFileHandler(FileUploadHandler): 
  # TODO: Add try-excepts to handle any errors gracefully!
  def __init__(self, newModels):
    self.hasher = HMAC.new(FILE_HMAC_SECRET, digestmod=SHA256)
    self.currentFilename = str()
    self.currentFile = None
    self.fileModel = None
    self.newModels = newModels

  def receive_data_chunk(self, raw_data, start):
    self.hasher.update(raw_data)
    self.currentFile.write(raw_data)
    self.currentFile.flush()

  def file_complete(self, file_size):
    digest = str(self.hasher.hexdigest())
    print "%s uploaded; %s %s" % (self.currentFilename, digest, str(file_size))
    self.hasher = HMAC.new(FILE_HMAC_SECRET, digestmod=SHA256)
    self.currentFile.close()
    self.fileModel.fileSize = file_size
    self.fileModel.fileSignature = digest
    self.fileModel.parent = None
    self.fileModel.save()
    self.newModels.append(self.fileModel)

  def new_file(self, field_name, file_name, content_type, content_length, charset):
    fileID = str(uuid.uuid4().hex)
    self.currentFilename = os.path.join(FILE_STORAGE_PATH, fileID)
    self.currentFile = open(self.currentFilename, "wb")
    self.fileModel = FileNode()
    self.fileModel.nodeID = fileID
    self.fileModel.visibleName = file_name
    self.fileModel.mimeType = content_type

  def upload_complete(self):
    # TODO: return an uploadedfile object
    pass

def index(request):
  return browse(request, None)

def browse(request, node_id):
  # returns directory listing if node_id is a directory
  # else returns a file page
  ctx = {}
  # is the supplied node_id a directory?
  if DirNode.objects.filter(nodeID=node_id).exists():
    # then list directory
    directory = DirNode.objects.get(nodeID=node_id)
    subdirs = DirNode.objects.filter(parent=directory)
    files = FileNode.objects.filter(parent=directory)
    ctx["breadcrumbs"] = gen_breadcrumbs(directory.nodeID)
    ctx["directory"] = directory
    ctx["subdirs"] = subdirs
    ctx["files"] = files
    return render(request, "browse_dir.html", ctx)
  elif FileNode.objects.filter(nodeID=node_id).exists():
    # then list file
    fnode = FileNode.objects.get(nodeID=node_id)
    if fnode.parent:
      ctx["breadcrumbs"] = gen_breadcrumbs(fnode.parent.nodeID)
    else:
      ctx["breadcrumbs"] = list()
    ctx["fnode"] = fnode
    # handle captcha
    captcha_client = RecaptchaClient(RECAPTCHA_PRIVATE_KEY, RECAPTCHA_PUBLIC_KEY)
    ctx["captcha_code"] = captcha_client.get_challenge_markup(use_ssl=True)
    return render(request, "browse_file.html", ctx)
  else:
    # then list root directory
    directory = None
    subdirs = DirNode.objects.filter(parent=None)
    files = FileNode.objects.filter(parent=None)
    ctx["breadcrumbs"] = list()
    ctx["directory"] = directory
    ctx["subdirs"] = subdirs
    ctx["files"] = files
    return render(request, "browse_dir.html", ctx)

def slug(request, slug):
  # redirect to browse by looking up slug
  return HttpResponseRedirect("/")

@csrf_protect
def mkdir(request):
  # make directory
  if request.method == "POST":
    try:
      parentID = request.POST.get("parent")
      name = request.POST.get("dir_name")
      new_dir = DirNode()
      new_dir.nodeID = str(uuid.uuid4().hex)
      new_dir.visibleName = name
      if parentID == "NULL":
        # put in root directory
        new_dir.parent = None
      else:
        # put in current directory
        new_dir.parent = DirNode.objects.get(nodeID=parentID)
      new_dir.save()
      if new_dir.parent:
        return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": new_dir.parent.nodeID}))
      else:
        return HttpResponseRedirect(reverse("file_app.views.index"))
    except Exception as e:
      return render(request, "message.html", {"message": "Error getting node: "+str(e)}, status=400)
  else:
    return HttpResponseRedirect("/")

@csrf_protect
def rename(request):
  if request.method == "POST":
    try:
      node_ID = request.POST.get("node_ID")
      new_name = request.POST.get("new_name")
      if node_ID and new_name:
        fdnode = None
        if DirNode.objects.filter(nodeID=node_ID).exists():
          fdnode = DirNode.objects.get(nodeID=node_ID)
        elif FileNode.objects.filter(nodeID=node_ID).exists():
          fdnode = FileNode.objects.get(nodeID=node_ID)
        else:
          return render(request, "message.html", {"message": "Node ID not found."}, status=400)
        fdnode.visibleName = new_name
        fdnode.save()
        return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": node_ID}))
      else:
        return render(request, "message.html", {"message": "Node ID and name shouldn't be empty."}, status=400)        
    except Exception as e:
      return render(request, "message.html", {"message": "Error getting node: "+str(e)}, status=400)
  else:
    return HttpResponseRedirect("/")

@csrf_protect
def delete(request):
  if request.method == "POST":
    try:
      # Delete file/directory and all its children
      # check captcha
      captcha_client = RecaptchaClient(RECAPTCHA_PRIVATE_KEY, RECAPTCHA_PUBLIC_KEY)
      if captcha_client.is_solution_correct(
          request.POST.get("recaptcha_response_field"),
          request.POST.get("recaptcha_challenge_field"),
          request.META['REMOTE_ADDR']):
        # delete object
        node_ID = request.POST.get("node_ID")
        canFilePath = os.path.join(FILE_STORAGE_PATH, node_ID)
        if os.path.isfile(canFilePath):
          os.remove(canFilePath)
          fnode = FileNode.objects.get(nodeID=node_ID)
          parent = fnode.parent
          fnode.delete()
          if parent:
            return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": parent.nodeID}))
          else:
            return HttpResponseRedirect(reverse("file_app.views.index"))
        else:
          return render(request, "message.html", {"message": "File not found in filesystem."}, status=500)
      else:
        return render(request, "message.html", {"message": "Invalid solution to recaptcha."}, status=400)
    except Exception as e:
      return render(request, "message.html", {"message": str(e)}, status=400)
  else:
    return HttpResponseRedirect("/")

@csrf_protect
def _upload(request, newModels):
  # redirect to newly-uploaded file
  # reparent the newModels
  try:
    parent = request.POST.get("parent")
    parentModel = None
    if parent != "NULL":
      parentModel = DirNode.objects.get(nodeID=parent)
    for m in newModels:
      m.parent = parentModel
      m.save()
    if parentModel:
      return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": parentModel.nodeID}))
    else:
      return HttpResponseRedirect(reverse("file_app.views.index"))
  except Exception as e:
    return render(request, "message.html", {"message": "Error uploading file: "+str(e)}, status=400)

@csrf_exempt
def upload(request):
  newModels = list()
  request.upload_handlers = [DirectFileHandler(newModels)]
  return _upload(request, newModels)

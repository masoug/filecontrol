from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render
from django.core.files.uploadhandler import FileUploadHandler
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
import os, uuid
#from Crypto.Hash import HMAC, SHA256
import hmac, hashlib
import time, struct, base64
from file_app.models import *
from file_app.recaptcha import RecaptchaClient
import pushover

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

# handle two-factor auth:
# code borrowed from: http://www.brool.com/index.php/using-google-authenticator-for-your-website
# TODO: each secret should be unique to each user, so put this in the database (encrypted, of course)!
def check_totp(secret_code, code_attempt):
  tm = int(time.time() / 30)
  secretkey = base64.b32decode(secret_code)

  # try 30 seconds behind and ahead as well
  for ix in [-1, 0, 1]:
      # convert timestamp to raw bytes
      b = struct.pack(">q", tm + ix)

      # generate HMAC-SHA1 from timestamp based on secret key
      hm = hmac.HMAC(secretkey, b, hashlib.sha1).digest()

      # extract 4 bytes from digest based on LSB
      offset = ord(hm[-1]) & 0x0F
      truncatedHash = hm[offset:offset+4]

      # get the code from it
      code = struct.unpack(">L", truncatedHash)[0]
      code &= 0x7FFFFFFF;
      code %= 1000000;

      if ("%06d" % code) == str(code_attempt):
          return True

  return False

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
    self.hasher = hmac.new(FILE_HMAC_SECRET, digestmod=hashlib.sha256)
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
    self.hasher = hmac.new(FILE_HMAC_SECRET, digestmod=hashlib.sha256)
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
    if not file_name:
      self.fileModel.visibleName = "Untitled File"
    else:
      self.fileModel.visibleName = file_name
    self.fileModel.mimeType = content_type

  def upload_complete(self):
    # TODO: return an uploadedfile object
    pass

def index(request):
  return browse(request, None)

def getAllSubdirs(root, currList):
  for subdir in DirNode.objects.filter(parent=root):
    getAllSubdirs(subdir, currList)
  currList.append(root.nodeID)

@login_required
def browse(request, node_id):
  # returns directory listing if node_id is a directory
  # else returns a file page
  ctx = {
    "user": request.user
  }
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

    # Show move targets
    invTargets = list()
    getAllSubdirs(directory, invTargets)
    ctx["move_targets"] = DirNode.objects.all().exclude(nodeID__in=invTargets)
    return render(request, "browse_dir.html", ctx)
  elif FileNode.objects.filter(nodeID=node_id).exists():
    # then list file
    fnode = FileNode.objects.get(nodeID=node_id)
    if fnode.parent:
      ctx["breadcrumbs"] = gen_breadcrumbs(fnode.parent.nodeID)
    else:
      ctx["breadcrumbs"] = list()
    ctx["fnode"] = fnode
    ctx["move_targets"] = DirNode.objects.all()
    return render(request, "browse_file.html", ctx)
  else:
    # then list root directory
    subdirs = DirNode.objects.filter(parent=None)
    files = FileNode.objects.filter(parent=None)
    ctx["breadcrumbs"] = list()
    ctx["directory"] = None
    ctx["subdirs"] = subdirs
    ctx["files"] = files
    return render(request, "browse_dir.html", ctx)

def slug(request, slug):
  # redirect to browse by looking up slug
  return HttpResponseRedirect("/")

@login_required
@csrf_protect
def mkdir(request):
  # make directory
  if request.method == "POST":
    try:
      parentID = request.POST.get("parent")
      name = request.POST.get("dir_name")
      if not name:
        name = "Untitled Directory"
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

@login_required
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

# delete a FileNode INSTANCE!
def rmFileNode(fileNode):
  filePath = os.path.join(FILE_STORAGE_PATH, fileNode.nodeID)
  if os.path.isfile(filePath):
    os.remove(filePath)
    parent = fileNode.parent
    fileNode.delete()
    return parent
  else:
    raise Exception("File (%s) not found on filesystem!" % (fileNode.nodeID,))

# delete a DirNode INSTANCE!
def rmDirNode(dirNode):
  fchildren = FileNode.objects.filter(parent=dirNode)
  for fchild in fchildren:
    rmFileNode(fchild)
  dchildren = DirNode.objects.filter(parent=dirNode)
  for dchild in dchildren:
    rmDirNode(dchild)
  parent = dirNode.parent
  dirNode.delete()
  return parent

@login_required
@csrf_protect
def delete(request):
  if request.method == "POST":
    try:
      # Delete file/directory and all its children
      # delete object
      node_ID = request.POST.get("node_ID")
      parent = None
      if FileNode.objects.filter(nodeID=node_ID).exists():
        parent = rmFileNode(FileNode.objects.get(nodeID=node_ID))
      elif DirNode.objects.filter(nodeID=node_ID).exists():
        parent = rmDirNode(DirNode.objects.get(nodeID=node_ID))
      else:
        return render(request, "message.html", {"message": "node_ID not found."}, status=400)
      if parent:
        return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": parent.nodeID}))
      else:
        return HttpResponseRedirect(reverse("file_app.views.index"))
    except Exception as e:
      return render(request, "message.html", {"message": str(e)}, status=400)
  else:
    return HttpResponseRedirect("/")

@login_required
@csrf_protect
def move(request):
  if request.method == "POST":
    try:
      node_ID = request.POST.get("node_ID")
      target_ID = request.POST.get("target_ID")
      if node_ID == target_ID:
        return render(request, "message.html", {"message": "Cannot move directory to itself!"}, status=400)
      nodeObj = None
      if FileNode.objects.filter(nodeID=node_ID).exists():
        nodeObj = FileNode.objects.get(nodeID=node_ID)
      elif DirNode.objects.filter(nodeID=node_ID).exists():
        nodeObj = DirNode.objects.get(nodeID=node_ID)
        invTargets = list()
        getAllSubdirs(nodeObj, invTargets)
        if target_ID in invTargets:
          return render(request, "message.html", {"message": "Cannot move directory to descendent!"}, status=400)
      else:
        return render(request, "message.html", {"message": "node_ID not found."}, status=400)
      if DirNode.objects.filter(nodeID=target_ID).exists():
        nodeObj.parent = DirNode.objects.get(nodeID=target_ID)
      else:
        nodeObj.parent = None
      nodeObj.save()
      return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": node_ID}))
    except Exception as e:
      return render(request, "message.html", {"message": str(e)}, status=400)
  else:
    return HttpResponseRedirect("/")

def login_view(request):
  if request.method == "POST":
    try:
      # handle login attempt
      user = authenticate(
        username=request.POST.get("username"),
        password=request.POST.get("password"))
      if user is not None:
        if not UserTOTP.objects.filter(user=user).exists():
          pushover.push_improper_user(user.username)
          return render(request, "message.html", {"message": "Invalid credentials!"}, status=500)
        if not check_totp(UserTOTP.objects.get(user=user).secretKey, request.POST.get("otcode")):
          # TODO: add ipaddress field
          pushover.push_failed_totp("IPADDRESS", user.username)
          return render(request, "message.html", {"message": "Invalid credentials!"}, status=400)
        if user.is_active:
          login(request, user)
          return HttpResponseRedirect(reverse("file_app.views.index"))
        else:
          return render(request, "message.html", {"message": "LOGIN DISABLED"}, status=400)
      else:
        # TODO: add ipaddress field
        pushover.push_failed_login("IPADDRESS", request.POST.get("username"))
        return render(request, "message.html", {"message": "Invalid credentials!"}, status=400)
    except Exception as e:
      return render(request, "message.html", {"message": "Invalid POST request! ("+str(e)+")"}, status=400)
  else:
    # render login page or redirect to index
    if request.user.is_authenticated():
      return HttpResponseRedirect(reverse("file_app.views.index"))
    else:
      return render(request, "login.html")

def logout_view(request):
  logout(request)
  return HttpResponseRedirect(reverse("file_app.views.index"))

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

@login_required
@csrf_exempt
def upload(request):
  newModels = list()
  request.upload_handlers = [DirectFileHandler(newModels)]
  return _upload(request, newModels)

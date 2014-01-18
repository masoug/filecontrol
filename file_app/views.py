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
FILE_STORAGE_PATH = "/home/sammy/Web/filecontrol/"
# make hmac secret as long as the digest
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

# Custom upload handler
class DirectFileHandler(FileUploadHandler): 
    # TODO: Add try-excepts to handle any errors gracefully!
    def __init__(self):
        self.hasher = HMAC.new(FILE_HMAC_SECRET, digestmod=SHA256)
        self.currentFilename = str()
        self.currentFile = None
        self.fileModel = None
        
    def receive_data_chunk(self, raw_data, start):
        self.hasher.update(raw_data)
        self.currentFile.write(raw_data)
        self.currentFile.flush()
        pass

    def file_complete(self, file_size):
        digest = str(self.hasher.hexdigest())
        print "%s uploaded; %s %s" % (self.currentFilename, digest, str(file_size))
        self.hasher = HMAC.new(FILE_HMAC_SECRET, digestmod=SHA256)
        self.currentFile.close()
        self.fileModel.fileSize = file_size
        self.fileModel.fileSignature = digest
        self.fileModel.save()
        pass

    def new_file(self, field_name, file_name, content_type, content_length, charset):
        fileID = str(uuid.uuid4().hex)
        self.currentFilename = os.path.join(FILE_STORAGE_PATH, fileID)
        self.currentFile = open(self.currentFilename, "wb")
        self.fileModel = FileNode()
        self.fileModel.nodeID = fileID
        self.fileModel.visibleName = file_name
        self.fileModel.mimeType = content_type
        pass
    
    def upload_complete(self):
        # TODO: return an uploadedfile object
        pass

def index(request):
    # show vaults
    return HttpResponseRedirect("/"+32*"0")
   
def browse(request, node_id):
    # returns directory listing if node_id is a directory
    # else returns a file page
    ctx = {}
    if node_id == 32*"0":
        # root directory
        ctx["file_nodes"] = []
        for fnode in FileNode.objects.all():
            ctx["file_nodes"].append((
                fnode.visibleName, sizeof_fmt(fnode.fileSize),
                fnode.mimeType, fnode.nodeID,
            ))
        return render(request, "browse_dir.html", ctx)
    else:
        # view file
        try:
          fnode = FileNode.objects.get(nodeID=node_id)
          ctx["fnode"] = fnode
          # handle captcha
          captcha_client = RecaptchaClient(RECAPTCHA_PRIVATE_KEY, RECAPTCHA_PUBLIC_KEY)
          ctx["captcha_code"] = captcha_client.get_challenge_markup(use_ssl=True)
        except Exception as e:
          return render(request, "message.html", {"message": "Error getting node: "+str(e)}, status=400)
        return render(request, "browse_file.html", ctx)


def slug(request, slug):
    # redirect to browse by looking up slug
    return HttpResponseRedirect("/")

@csrf_protect
def rename(request):
    if request.method == "POST":
        node_ID = request.POST.get("node_ID")
        new_name = request.POST.get("new_name")
        if node_ID and new_name:
            try:
              fnode = FileNode.objects.get(nodeID=node_ID)
            except Exception as e:
              return render(request, "message.html", {"message": "Error getting node: "+str(e)}, status=400)
            fnode.visibleName = new_name
            # TODO: stamp last modification
            fnode.save()
            return HttpResponseRedirect(reverse("file_app.views.browse", kwargs={"node_id": node_ID}))
        return render(request, "message.html", {"message": "Invalid node_id or name."}, status=400)
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
            FileNode.objects.get(nodeID=node_ID).delete()
            canFilePath = os.path.join(FILE_STORAGE_PATH, node_ID)
            if os.path.isfile(canFilePath):
                os.remove(canFilePath)
            # TODO: redirect to parent directory
            return HttpResponseRedirect("/")
          else:
            return render(request, "message.html", {"message": "Invalid solution to recaptcha."}, status=400)
        except Exception as e:
          return render(request, "message.html", {"message": str(e)}, status=400)
    else:
        return HttpResponseRedirect("/")

@csrf_protect
def _upload(request):
    # redirect to newly-uploaded file
    return HttpResponseRedirect("/")

@csrf_exempt
def upload(request):
    request.upload_handlers = [DirectFileHandler()]
    return _upload(request)

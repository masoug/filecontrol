from django.conf.urls import patterns, url
from file_app import views

urlpatterns = patterns('',
  url(r"^$", views.index, name="index"),
  url(r"^upload/$", views.upload, name="upload"),
  url(r"^delete/$", views.delete, name="delete"),
  url(r"^rename/$", views.rename, name="rename"),
  url(r"^mkdir/$", views.mkdir, name="mkdir"),
  url(r"^move/$", views.move, name="move"),
  url(r"^login/$", views.login_view, name="login"),
  url(r"^logout/$", views.logout_view, name="logout"),
  url(r"^(?P<node_id>[0-9a-f]{32})/$", views.browse, name="browse"),
  url(r"^(?P<slug>[a-z-]+)/$", views.slug, name="slug"),
)

# Packages
from django.conf.urls import url
# Project
from api.views import ZoekApiView, GeoZoekView, OpenApiView

urlpatterns = [
    url(r'^zorg/zoek/activiteit/$', ZoekApiView.as_view(), {'search_for': 'activiteit'}),
    url(r'^zorg/zoek/locatie/$', ZoekApiView.as_view(), {'search_for': 'locatie'}),
    url(r'^zorg/zoek/organisatie/$', ZoekApiView.as_view(), {'search_for': 'organisatie'}),
    url(r'^zorg/zoek/thema/$', ZoekApiView.as_view(), {'search_for': 'thema'}),
    url(r'^zorg/zoek/geo/$', GeoZoekView.as_view()),
    url(r'^zorg/zoek/$', ZoekApiView.as_view()),
    url(r'^zorg/openapi.yml', OpenApiView.as_view())
]

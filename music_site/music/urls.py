from django.urls import path
from . import views

urlpatterns = [
    path("", views.song_list, name="song_list"),
    path("songs/", views.song_list, name="song_list_alias"),
    path("search/", views.search, name="search"),
    path("songs/<str:song_id>/", views.song_detail, name="song_detail"),
    path("songs/<str:song_id>/comments/<int:comment_id>/delete/", views.delete_comment, name="delete_comment"),
    path("singers/", views.singer_list, name="singer_list"),
    path("singers/<str:singer_id>/", views.singer_detail, name="singer_detail"),
]
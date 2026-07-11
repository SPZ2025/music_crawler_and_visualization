import json
from pathlib import Path
from time import perf_counter
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from .models import Comment


BASE_DIR = Path(__file__).resolve().parent.parent

_SONGS_CACHE = None
_SINGERS_CACHE = None
_SONG_MAP_CACHE = None
_SINGER_ID_MAP_CACHE = None

#转换windows格式
def normalize_static_path(path):
    if not path:
        return ""
    return str(path).replace("\\", "/")

#------------------------------------------------------
#链接到base
#------------------------------------------------------
def base(request):
    return render(request, "music/base.html",)

#------------------------------------------------------
#链接到song_list
#------------------------------------------------------
def load_songs():
    global _SONGS_CACHE

    if _SONGS_CACHE is not None:
        return _SONGS_CACHE

    songs_path = BASE_DIR / "data" / "songs.json"
    with open(songs_path, "r", encoding="utf-8") as f:
        songs = json.load(f)

    for song in songs:
        song["song_photo_path"] = normalize_static_path(song.get("song_photo_path"))

    _SONGS_CACHE = songs
    return _SONGS_CACHE

def song_list(request):
    songs = load_songs()

    paginator = Paginator(songs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    displayed_page_range = paginator.get_elided_page_range(
    page_obj.number,
    on_each_side=2,
    on_ends=1
)

    return render(request, "music/song_list.html", {
        "page_obj": page_obj,
        "displayed_page_range": displayed_page_range,
    })

#------------------------------------------------------
#链接到song_detail
#------------------------------------------------------
def get_song_map():
    global _SONG_MAP_CACHE

    if _SONG_MAP_CACHE is not None:
        return _SONG_MAP_CACHE

    _SONG_MAP_CACHE = {
        song["song_id"]: song for song in load_songs() if song.get("song_id")
    }
    return _SONG_MAP_CACHE

def get_song_by_id(song_id):
    return get_song_map().get(song_id)

def get_song_singer_ids(song):
    singer_ids = song.get("song_singer_ids")
    if isinstance(singer_ids, list):
        return [str(singer_id).strip() for singer_id in singer_ids if str(singer_id).strip()]

    singer_id = str(song.get("song_singer_id") or "").strip()
    if singer_id:
        return [singer_id]

    return []

def get_singers_for_song(song):
    singer_map = get_singer_id_map()
    singers = []
    missing_singer_ids = []

    for singer_id in get_song_singer_ids(song):
        singer = singer_map.get(singer_id)
        if singer is None:
            missing_singer_ids.append(singer_id)
        else:
            singers.append(singer)

    return singers, missing_singer_ids

def song_detail(request, song_id):
    song = get_song_by_id(song_id)

    if song is None:
        raise Http404("歌曲不存在")

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            Comment.objects.create(song_id= song_id, content= content)
        return redirect("song_detail", song_id= song_id)

    singers, missing_singer_ids = get_singers_for_song(song)
    comments = Comment.objects.filter(song_id= song_id).order_by("-created_at")

    return render(request, "music/song_detail.html", {
        "song": song,
        "singers": singers,
        "missing_singer_ids": missing_singer_ids,
        "comments": comments
    })

def delete_comment(request, song_id, comment_id):
    if request.method != "POST":
        return redirect("song_detail", song_id= song_id)

    comment = get_object_or_404(Comment, id= comment_id, song_id= song_id)
    comment.delete()
    return redirect("song_detail", song_id= song_id)

#------------------------------------------------------
#链接到singer_list
#------------------------------------------------------
def load_singers():
    global _SINGERS_CACHE

    if _SINGERS_CACHE is not None:
        return _SINGERS_CACHE

    singers_path = BASE_DIR / "data" / "singers.json"
    with open(singers_path, "r", encoding="utf-8") as f:
        singers = json.load(f)

    for singer in singers:
        singer["singer_photo_path"] = normalize_static_path(singer.get("singer_photo_path"))

    _SINGERS_CACHE = singers
    return _SINGERS_CACHE

def singer_list(request):
    singers = load_singers()

    paginator = Paginator(singers, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    displayed_page_range = paginator.get_elided_page_range(
    page_obj.number,
    on_each_side=2,
    on_ends=1
)

    return render(request, "music/singer_list.html", {
        "page_obj": page_obj,
        "displayed_page_range": displayed_page_range,
    })

#------------------------------------------------------
#链接到singer_detail
#------------------------------------------------------
def get_singer_id_map():
    global _SINGER_ID_MAP_CACHE

    if _SINGER_ID_MAP_CACHE is not None:
        return _SINGER_ID_MAP_CACHE

    _SINGER_ID_MAP_CACHE = {
        singer["singer_id"]: singer
        for singer in load_singers()
        if singer.get("singer_id")
    }
    return _SINGER_ID_MAP_CACHE

def get_singer_by_id(singer_id):
    return get_singer_id_map().get(singer_id)


def singer_detail(request, singer_id):
    singer = get_singer_by_id(singer_id)

    if singer is None:
        raise Http404("歌手不存在")

    singer_songs = []

    for song in load_songs():
        song_singer_ids = get_song_singer_ids(song)

        if singer_id in song_singer_ids:
            singer_songs.append(song)

    return render(request, "music/singer_detail.html", {
        "singer": singer,
        "singer_songs": singer_songs,
    })

#------------------------------------------------------
#设计搜索视图
#------------------------------------------------------
def search(request):
    query = request.GET.get("q", "").strip()
    search_type = request.GET.get("type", "song")

    results = []
    error = ""
    elapsed_time = 0
#字数超过限制 不是对应类型 为输入搜索内容
    if search_type not in ["song", "singer"]:
        search_type = "song"
    
    if "q" in request.GET and not query:
        error = "请输入搜索内容"
    
    elif len(query) > 20:
        error = "搜索内容不能超过二十个字符"
    
    elif query:
        start_time = perf_counter()
        keyword = query.casefold()

        if search_type == "song":
            songs = load_songs()

            for song in songs:
                title = str(song.get("song_title", ""))
                singers = str(song.get("song_singer", ""))
                lyrics = song.get("song_lyrics", [])
                if isinstance(lyrics, list):
                    lyrics_text = "\n".join(str(line) for line in lyrics)
                else:
                    lyrics_text = str(lyrics)

                searchable_text = "\n".join([title, singers, lyrics_text]).casefold()

                if keyword in searchable_text:
                    results.append(song)

        else:
            singers = load_singers()

            for singer in singers:
                name = str(singer.get("singer_name", ""))

                introduction = str(singer.get("singer_info",  singer.get("简介", "")))

                searchable_text = "\n".join([name, introduction,]).casefold()

                if keyword in searchable_text:
                    results.append(singer)

        elapsed_time = (perf_counter() - start_time) * 1000

    result_count = len(results)

    paginator = Paginator(results, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    displayed_page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)

    return render(request, "music/search_result.html", {
        "query": query,
        "search_type": search_type,
        "page_obj": page_obj,
        "result_count": result_count,
        "elapsed_time": elapsed_time,
        "error": error,
        "displayed_page_range": displayed_page_range,
    })
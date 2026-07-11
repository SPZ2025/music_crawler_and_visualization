import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SONGS_PATH = BASE_DIR / "data" / "songs.json"
SINGERS_PATH = BASE_DIR / "data" / "singers.json"

BAD_SINGER_ID = "002SpsUU3fZaM4"


with open(SONGS_PATH, "r", encoding="utf-8") as f:
    songs = json.load(f)

with open(SINGERS_PATH, "r", encoding="utf-8") as f:
    singers = json.load(f)

singer_ids = []
for singer in singers:
    singer_ids.append(singer["singer_id"])

new_songs = []
for song in songs:
    keep_song = True

    for singer_id in song["song_singer_ids"]:
        if singer_id not in singer_ids:
            keep_song = False
        if singer_id == BAD_SINGER_ID:
            keep_song = False

    if keep_song:
        new_songs.append(song)

with open(SONGS_PATH, "w", encoding="utf-8") as f:
    json.dump(new_songs, f, ensure_ascii=False, indent=2)

print("原歌曲数量：", len(songs))
print("清洗后歌曲数量：", len(new_songs))
print("删除歌曲数量：", len(songs) - len(new_songs))

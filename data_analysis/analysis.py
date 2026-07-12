import json
import re
import matplotlib.pyplot as plt
from pathlib import Path
from statistics import median
import numpy as np
import jieba
import random
from collections import defaultdict
from itertools import combinations
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


#解析歌曲数据
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SONGS_PATH = PROJECT_ROOT / "music_site" / "data" / "songs.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SINGERS_PATH = PROJECT_ROOT / "music_site" / "data" / "singers.json" 
def load_songs():
    with SONGS_PATH.open("r", encoding= "utf-8") as f:
        return json.load(f)
def load_singers():
    with SINGERS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)
#正则尽可能匹配掉无效信息
CREDIT_PATTERN = re.compile(
    r"^\s*("
    r"作词|作曲|编曲|制作人|录音师|录音工作室|录音|"
    r"混音师|混音工作室|混音|母带后期制作人|母带后期处理工程师|"
    r"母带后期处理录音室|母带|吉他|贝斯|和音|弦乐|"
    r"音乐制作助理|词\s*Lyric|曲\s*Compo|词：|曲：|"
    r"和声|企划|监制|缩混|OP|SP|制作|音频|"
    r"Producer|Recording|Mixing|Mastering|Studio|Arrangement"
    r")",
    re.IGNORECASE,
)
def clean_lyrics(lyric_list):
    lyric_cleaned = []

    for index, lyric in enumerate(lyric_list):
        if index == 0:
            continue
        if  not lyric:
            continue
        if CREDIT_PATTERN.search(lyric):
            continue
        lyric_cleaned.append(lyric)

    return lyric_cleaned


#--------------------------------------------------------------------------------------------------------------
#子任务一：有关歌词重复率的基本调查，并探讨歌词重复率和评论平均长度的关系
#--------------------------------------------------------------------------------------------------------------

#设计一个标准：歌词重复率，通过唯一行数和重复行数来得到
def calculate_lyric_metrics(lyrics):
    line_count = len(lyrics)

    if line_count == 0:
        return 0, 0, 0.0

    unique_line_count = len(set(lyrics))
    repetition_rate = 1 - unique_line_count / line_count

    return line_count, unique_line_count, repetition_rate

#设计一个标准：评论平均长度，计算评论平均字符长度
def calculate_average_comment_length(comments):
    if not comments:
        return 0.0

    lengths = []

    for comment in comments:
        comment_text = comment.get("comment_text", "").strip()

        if comment_text:
            lengths.append(len(comment_text))

    if not lengths:
        return 0.0

    return sum(lengths) / len(lengths)

#将前两个标准关联，尝试找出关系
def build_analysis_records(songs):
    records = []

    for song in songs:
        cleaned_lyrics = clean_lyrics(song.get("song_lyrics", []))

        if len(cleaned_lyrics) < 5:
            continue

        line_count, unique_line_count, repetition_rate = (
            calculate_lyric_metrics(cleaned_lyrics)
        )

        average_comment_length = calculate_average_comment_length(
            song.get("song_comments", [])
        )

        record = {
            "song_title": song.get("song_title", "未知歌曲"),
            "song_singer": song.get("song_singer", "未知歌手"),
            "line_count": line_count,
            "unique_line_count": unique_line_count,
            "repetition_rate": repetition_rate,
            "average_comment_length": average_comment_length,
        }
        records.append(record)

    return records

#打印某首歌的数据，检查用
def print_record(record):
    print(
        f"{record['song_title']} - {record['song_singer']} | "
        f"总行数：{record['line_count']} | "
        f"唯一行数：{record['unique_line_count']} | "
        f"重复率：{record['repetition_rate']:.2%} | "
        f"评论平均长度：{record['average_comment_length']:.2f}"
    )

#绘制歌曲重复率直方图
def draw_hist():
    songs = load_songs()   
    records = build_analysis_records(songs)

    average_repetition_rate = (sum(record["repetition_rate"] for record in records) / len(records))

    repetition_rates = [record["repetition_rate"] * 100 for record in records]

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False

    plt.figure(figsize=(10, 6))

    plt.hist(
        repetition_rates,
        bins=20,
        color="#3B82F6",
        edgecolor="white",
    )

    plt.axvline(
        average_repetition_rate * 100,
        color="#DC2626",
        linestyle="--",
        linewidth=2,
        label=f"平均值：{average_repetition_rate:.2%}",
    )

    plt.title("歌曲歌词重复率分布")
    plt.xlabel("歌词重复率（%）")
    plt.ylabel("歌曲数量")
    plt.legend()
    plt.tight_layout()

    output_path = OUTPUT_DIR / "lyric_repetition_distribution.png"
    plt.savefig(output_path, dpi=200)
    plt.close()

    print(f"图表已保存：{output_path}")

#计算相关系数并绘制散点图
def draw_co_scatter():
    songs = load_songs()
    records = build_analysis_records(songs)

    comment_records = [record for record in records if record["average_comment_length"] > 0]

    x_repetition = np.array([record["repetition_rate"] * 100 for record in comment_records])

    y_comment_length = np.array([record["average_comment_length"] for record in comment_records])

    correlation = np.corrcoef(x_repetition, y_comment_length,)[0,1]

    print(f"参与评论分析的歌曲数：{len(comment_records)}")
    print(f"重复率与评论平均长度的相关系数：{correlation:.4f}")

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False

    plt.figure(figsize= (10, 6))

    plt.scatter(x_repetition, y_comment_length, alpha = 0.35, s= 20, color= "#3B82F6")

    trend_line = np.poly1d(np.polyfit(x_repetition, y_comment_length, 1))

    x_line = np.linspace(x_repetition.min(), x_repetition.max(), 1000)
    
    plt.plot(x_line, trend_line(x_line), color= "#3B82F6", linewidth= 2, label=f"相关系数：{correlation:.3f}")
    plt.title("歌词重复率与评论平均长度的关系")
    plt.xlabel("歌词重复率（%）")
    plt.ylabel("评论平均长度（字符）")
    plt.legend()
    plt.tight_layout()
    
    output_path = OUTPUT_DIR / "repetition_comment_correlation.png"
    plt.savefig(output_path, dpi=200)
    plt.close()

    print(f"相关性图表已保存：{output_path}")

#计算重复率歌曲占比和中位数数值
def compute_rate():
    songs = load_songs()
    records = build_analysis_records(songs)

    repetition_rates = [record["repetition_rate"] * 100 for record in records]

    median_repetition_rate = median(repetition_rates)

    below_20_count = sum(rate < 20 for rate in repetition_rates)
    between_20_and_60_count = sum(
        20 <= rate <= 60 for rate in repetition_rates
    )
    above_60_count = sum(rate > 60 for rate in repetition_rates)

    total_count = len(repetition_rates)

    print(f"重复率中位数：{median_repetition_rate:.2f}%")
    print(
        f"重复率低于20%：{below_20_count}首，"
        f"占比{below_20_count / total_count:.2%}"
    )
    print(
        f"重复率位于20%至60%：{between_20_and_60_count}首，"
        f"占比{between_20_and_60_count / total_count:.2%}"
    )
    print(
        f"重复率高于60%：{above_60_count}首，"
        f"占比{above_60_count / total_count:.2%}"
    )


#--------------------------------------------------------------------------------------------------------------
#子任务二：有关歌词相似度的基本调查，探究不同歌手与相同歌手的歌词相似度之间的差异
#--------------------------------------------------------------------------------------------------------------

#jieba分词
STOP_WORDS = {
    "的", "了", "着", "是", "在", "和", "与", "也",
    "都", "就", "又", "而", "但", "却", "还", "很",
    "我", "你", "他", "她", "它", "我们", "你们", "他们",
    "这", "那", "一个", "一种", "什么", "怎么", "没有",
}
def tokenize_lyrics(cleaned_lyrics):
    #这里不能用set，原因在于set会打乱顺序，因此我们转字典后再转列表
    unique_lyrics = list(dict.fromkeys(cleaned_lyrics))
    lyrics_text = " ".join(unique_lyrics).lower()

    words = jieba.lcut(lyrics_text)
    valid_words = []

    for word in words:
        if not word:
            continue
        if word in STOP_WORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", word):
            valid_words.append(word)
        elif re.fullmatch(r"[a-z]+", word) and len(word) >= 2:
            valid_words.append(word)
    
    return valid_words

#准备好可以用的歌曲和文本
def prepare_similarity_data(songs):
    similarity_songs = []
    documents = []

    for song in songs:
        cleaned_lyrics = clean_lyrics(
            song.get("song_lyrics", [])
        )

        if len(cleaned_lyrics) < 5:
            continue

        words = tokenize_lyrics(cleaned_lyrics)

        if len(words) < 10:
            continue

        if len(song.get("song_singer_ids", [])) != 1:
            continue

        singer_id = song.get("song_singer_id", "未知id")
        similarity_songs.append({
            "song_title": song.get("song_title", "未知歌曲"),
            "song_singer": song.get("song_singer", "未知歌手"),
            "singer_id": singer_id,
        })

        documents.append(" ".join(words))

    return similarity_songs, documents

#比较同歌手与不同歌手的歌曲相似度
def compare_lyric_similarity(songs, random_seed = 42):
    similarity_songs, documents = prepare_similarity_data(songs)

    vectorizer = TfidfVectorizer(tokenizer= str.split, preprocessor= None,
                                token_pattern= None, min_df= 2, max_df= 0.8,
                                sublinear_tf= True
                                )

    tfidf_matrix = vectorizer.fit_transform(documents)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    singer_indices = defaultdict(list)

    for index, song in enumerate(similarity_songs):
        singer_indices[song["song_singer"]].append(index)

    same_singer_pairs = []
    for indices in singer_indices.values():
        if len(indices) < 2:
            continue
        same_singer_pairs.extend(combinations(indices, 2))
    
    same_singer_scores = [similarity_matrix[first_index][second_index]
                          for first_index, second_index in same_singer_pairs]
    
    random_generator = random.Random(random_seed)
    different_singer_scores = []
    while len(different_singer_scores) < len(same_singer_scores):
        first_index, second_index = random_generator.sample(
            range(len(similarity_songs)),
            2,)
        
        if similarity_songs[first_index]["singer_id"] == similarity_songs[second_index]["singer_id"]:
            continue
        different_singer_scores.append(similarity_matrix[first_index][second_index])

    return (same_singer_scores,
            different_singer_scores,
            len(similarity_songs),
            len(vectorizer.get_feature_names_out()))

#有关相似度的一些数据
def similarity_analysis_data():
    songs = load_songs()
    (
        same_singer_scores,
        different_singer_scores,
        similarity_song_count,
        vocabulary_size,
    ) = compare_lyric_similarity(songs)

    print(f"参与相似度分析的歌曲数：{similarity_song_count}")
    print(f"TF-IDF词汇数量：{vocabulary_size}")

    print(f"同歌手歌曲组合数：{len(same_singer_scores)}")

    print("同歌手平均相似度：" f"{np.mean(same_singer_scores):.4f}")
    print("不同歌手平均相似度：" f"{np.mean(different_singer_scores):.4f}")
    print("同歌手相似度中位数：" f"{np.median(same_singer_scores):.4f}")
    print("不同歌手相似度中位数：" f"{np.median(different_singer_scores):.4f}")


    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.figure(figsize=(9, 6))

    boxplot = plt.boxplot(
        [same_singer_scores, different_singer_scores,],
        tick_labels=["同一歌手", "不同歌手",],
        patch_artist=True,
        showmeans=True,
        showfliers=False,
    )   

    colors = ["#3B82F6", "#DC2626"]

    for box, color in zip(boxplot["boxes"], colors):
        box.set_facecolor(color)

    plt.title("同歌手与不同歌手的歌词相似度比较")
    plt.xlabel("歌曲组合类型")
    plt.ylabel("TF-IDF余弦相似度")

    plt.text(
        1,
        np.median(same_singer_scores) + 0.01,
        f"中位数：{np.median(same_singer_scores):.4f}",
        horizontalalignment="center",
    )

    plt.text(
        2,
        np.median(different_singer_scores) + 0.01,
        f"中位数：{np.median(different_singer_scores):.4f}",
        horizontalalignment="center",
    )  

    plt.tight_layout()

    output_path = OUTPUT_DIR / "same_vs_different_singer_similarity.png"
    plt.savefig(output_path, dpi=200)
    plt.close()

    print(f"歌词相似度图表已保存：{output_path}")


#--------------------------------------------------------------------------------------------------------------
#子任务三：有关歌词重复率的进一步调查，探讨歌词重复率与歌手出生年代的关系
#--------------------------------------------------------------------------------------------------------------

#提取歌手出生年代
def extract_birth_year(singer):
    birthday = singer.get("生日", "")
    if not birthday:
        return None

    result = re.search(r"(19\d{2}|20\d{2})", str(birthday))

    if result is None:
        return None

    return int(result.group(1))

#分组统计结果
def analyze_decade_repetition(songs, singers):
    singer_birth_years = {}

    for singer in singers:
        birth_year = extract_birth_year(singer)

        if birth_year is None:
            continue

        singer_id = singer.get("singer_id")

        if singer_id:
            singer_birth_years[singer_id] = birth_year

    decade_rates = defaultdict(list)

    for song in songs:
        singer_ids = song.get("song_singer_ids", [])

        #排除合唱歌曲
        if len(singer_ids) != 1:
            continue

        singer_id = singer_ids[0]

        if singer_id not in singer_birth_years:
            continue

        cleaned_lyrics = clean_lyrics(
            song.get("song_lyrics", [])
        )

        if len(cleaned_lyrics) < 5:
            continue

        _, _, repetition_rate = calculate_lyric_metrics(cleaned_lyrics)

        birth_year = singer_birth_years[singer_id]
        decade = birth_year // 10 * 10

        decade_rates[decade].append(repetition_rate)

    summaries = []

    for decade, rates in sorted(decade_rates.items()):
        # 样本过少的年代不参与比较
        if len(rates) < 30:
            continue

        summaries.append({
            "decade": decade,
            "song_count": len(rates),
            "mean_rate": float(np.mean(rates)),
            "median_rate": float(np.median(rates)),
        })

    return summaries

#得出基本数据并绘制柱状图
def draw_decade_rate_bar():
    songs = load_songs()
    singers = load_singers()
    decade_summaries = analyze_decade_repetition(songs, singers,)

    print("\n不同出生年代歌手的歌词重复率：")
    for summary in decade_summaries:
        print(
            f"{summary['decade']}年代："
            f"{summary['song_count']}首，"
            f"平均值{summary['mean_rate']:.2%}，"
            f"中位数{summary['median_rate']:.2%}"
        )
    
    decade_labels = [f"{summary['decade']}年代" for summary in decade_summaries]
    mean_rates = [summary["mean_rate"] * 100 for summary in decade_summaries]
    median_rates = [summary["median_rate"] * 100 for summary in decade_summaries]
    song_counts = [summary["song_count"] for summary in decade_summaries]

    x_positions = np.arange(len(decade_labels))
    bar_width = 0.36

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.figure(figsize=(10, 6))

    plt.bar(
        x_positions - bar_width / 2,
        mean_rates,
        width=bar_width,
        label="平均重复率",
        color="#3B82F6",
    )

    plt.bar(
        x_positions + bar_width / 2,
        median_rates,
        width=bar_width,
        label="重复率中位数",
        color="#DC2626",
    )

    plt.xticks(x_positions, decade_labels)
    plt.xlabel("歌手出生年代")
    plt.ylabel("歌词重复率（%）")
    plt.title("不同出生年代歌手的歌词重复率比较")
    plt.legend()

    for index, count in enumerate(song_counts):
        bar_height = max(mean_rates[index], median_rates[index],)

        plt.text(
            index,
            bar_height + 1,
            f"n={count}",
            horizontalalignment="center",
        )

    plt.ylim(0, max(max(mean_rates), max(median_rates)) + 8,)

    plt.tight_layout()

    output_path = OUTPUT_DIR / "birth_decade_repetition.png"
    plt.savefig(output_path, dpi=200)
    plt.close()


# -*- coding: utf-8 -*-
"""有人声歌曲书：按情绪分类的华语校园热门歌（少量英文），供本地缓存试听与在线检索过滤。"""
from __future__ import annotations

import re

# 检索时排除纯音乐、伴奏、白噪音等
INSTRUMENTAL_MARKERS = (
    "instrumental",
    "karaoke",
    "backing track",
    "piano version",
    "piano cover",
    "piano stab",
    "lullaby",
    "rockabye baby",
    "music box",
    "lofi",
    "lo-fi",
    "lo fi",
    "ambient",
    "meditation",
    "sleep music",
    "rain sounds",
    "white noise",
    "soundtrack",
    "score version",
    "orchestra version",
    "tribute to",
    "string quartet",
    "marching band",
    "纯音乐",
    "轻音乐",
    "钢琴曲",
    "伴奏",
    "演奏版",
    "白噪音",
    "白噪声",
    "助眠",
    "瑜伽",
    "bgm",
    "翻自",
    "翻唱",
    "铃声",
    "dj版",
    "dj 版",
    "remix",
    "rmx",
    "proghouse",
    "production music",
    "stock music",
    "library music",
)

# 检索词本身被当成歌名的库存人声/配乐
STOCK_TITLE_MARKERS = (
    "pop song",
    "rock song",
    "upbeat pop",
    "dark pop",
    "feel good pop",
    "dance pop vocals",
    "super idol",
    "multilingual",
    "免费小说",
    "七猫",
)

SKIP_PERFORMERS = (
    "kidz bop",
    "kids bop",
    "baby rockstar",
    "vitamin string quartet",
    "piano guys",
    "piano dreamers",
    "rockabye baby",
    "midnite string quartet",
    "twinkle twinkle",
    "relaxing piano",
    "pickin' on",
    "pickin on",
    "midwest winds",
    "marching band",
    "twinkle twinkle little rock star",
)

# 繁体检索结果折成简体再比对歌名；展示时也走同一张表。
_TRAD_TO_SIMP = str.maketrans(
    "愛後為國樂發時長門開東風雲點實現與無這個們來對會體醜強獨戰鐘煙湧陰貓樹傑銘謙飛兒鄧陳趙歲戀聽記過錯氣龍捲義術單簡當從業書華語經總應該說讓給還進運關問題歡熱陽離獸團傳蘭齊劉買綱願乾燦爛態戲劇觀覺優傷殤俠雙盧樸馮靜倫誇闆裡麼線將畫憶懷邊條孫隻隻臺蘋麼麼聲帶專輯場錄選數賜碼銀鏡際內寫讀請區灣標準寶貝頁頭題顏館廣廳響處歷據產權號級類組員並確滿漢彙視藝職網質價電務間葉滾搖見絲詩迴蕭驚顫慄溫學認島黃嘆髮孃煉園遊盤騎亂羅曖榮詞話親變萬遠換擇證驗聯習鳳車馬魚錢賣鬆麵廠鐵億儀慶禮節責曆絡織閉係裏詠曉鴻穎聰艷偉麗鵬濤潔純紅機軍殺謝鋒殘竅極誘計動軌跡約橋興嗎殺戰雞隻蘋"
    "紅機軍殺謝鋒殘竅極誘計動軌跡約橋興嗎雞蘋隻",
    "爱后为国乐发时长门开东风云点实现与无这个们来对会体丑强独战钟烟涌阴猫树杰铭谦飞儿邓陈赵岁恋听记过错气龙卷义术单简当从业书华语经总应该说让给还进运关问题欢热阳离兽团传兰齐刘买纲愿干灿烂态戏剧观觉优伤殇侠双卢朴冯静伦夸板里么线将画忆怀边条孙只只台苹么么声带专辑场录选数赐码银镜际内写读请区湾标准宝贝页头题颜馆广厅响处历据产权号级类组员并确满汉汇视艺职网质价电务间叶滚摇见丝诗回萧惊颤栗温学认岛黄叹发娘炼园游盘骑乱罗暧荣词话亲变万远换择证验联习凤车马鱼钱卖松面厂铁亿仪庆礼节责历络织闭系里咏晓鸿颖聪艳伟丽鹏涛洁纯红机军杀谢锋残窍极诱计动轨迹约桥兴吗杀战鸡只苹"
    "红机军杀谢锋残窍极诱计动轨迹约桥兴吗鸡苹只",
)

_ALBUM_TAIL = (
    (re.compile(r"\s*[-–—]\s*Single\s*$", re.I), " - 单曲"),
    (re.compile(r"\s*[-–—]\s*EP\s*$", re.I), " - 迷你专辑"),
    (re.compile(r"\s*[-–—]\s*Album\s*$", re.I), " - 专辑"),
)


_EXTRA_TRAD = str.maketrans({
    "紅": "红", "機": "机", "軍": "军", "殺": "杀", "謝": "谢", "鋒": "锋",
    "殘": "残", "竅": "窍", "極": "极", "誘": "诱", "計": "计", "動": "动",
    "軌": "轨", "跡": "迹", "約": "约", "橋": "桥", "興": "兴", "嗎": "吗",
    "雞": "鸡", "張": "张", "妳": "你", "瑋": "玮", "議": "议", "の": "之",
    "偉": "伟", "僅": "仅", "億": "亿", "嵐": "岚", "層": "层", "樓": "楼",
    "寶": "宝", "暢": "畅",
})


def to_simplified(text: str) -> str:
    return (text or "").translate(_TRAD_TO_SIMP).translate(_EXTRA_TRAD)


def pretty_text(text: str) -> str:
    t = to_simplified(text).strip()
    if not t:
        return ""
    for pat, repl in _ALBUM_TAIL:
        t = pat.sub(repl, t)
    t = re.sub(r"\s*[-–—]\s*Single\b", " - 单曲", t, flags=re.I)
    t = re.sub(r"\(\s*Single\s*\)", "(单曲)", t, flags=re.I)
    t = re.sub(r"\(\s*Live\s*\)", "(现场)", t, flags=re.I)
    t = re.sub(r"(第\d+期)Live", r"\1现场", t, flags=re.I)
    t = re.sub(r"\(\s*Hong Kong Version\s*\)", "(香港版)", t, flags=re.I)
    t = re.sub(r"\bVersion\b", "版", t)
    return t


def localize_song(song: dict) -> dict:
    if not song:
        return song
    out = dict(song)
    for key in ("title", "artist", "album"):
        if out.get(key):
            out[key] = pretty_text(str(out[key]))
    label = out.get("source_label") or ""
    if "iTunes" in label:
        out["source_label"] = label.replace("iTunes", "苹果音乐")
    if "Deezer" in label:
        out["source_label"] = label.replace("Deezer", "国际曲库")
    return out


def fold_zh(text: str) -> str:
    return to_simplified(text).lower()


def title_key(text: str) -> str:
    t = fold_zh(text)
    t = t.replace("°c", "度").replace("℃", "度").replace("°", "度")
    t = t.replace(" ", "").replace(",", "").replace("，", "")
    for sep in ("(", "（", "/", "|"):
        t = t.split(sep, 1)[0]
    return t.strip()


def title_seen(key: str, seen: set[str]) -> bool:
    if not key or key in seen:
        return True
    for old in seen:
        if len(key) >= 4 and key in old:
            return True
        if len(old) >= 4 and old in key:
            return True
    return False


# 每类选「一听就对上标签」的华语校园热歌，让情绪切换反差尽量大。少量英文。
VOCAL_SONGBOOK = [
    # 喜 · 阳光、蹦跳、开口就笑（最热的排前面）
    dict(id="vocal-happy-01", emotion="happy", title="热爱105°C的你", artist="阿肆", query="热爱105度的你 阿肆"),
    dict(id="vocal-happy-09", emotion="happy", title="告白气球", artist="周杰伦", query="告白气球 周杰伦"),
    dict(id="vocal-happy-08", emotion="happy", title="小幸运", artist="田馥甄", query="小幸运 田馥甄"),
    dict(id="vocal-happy-06", emotion="happy", title="简单爱", artist="周杰伦", query="简单爱 周杰伦"),
    dict(id="vocal-happy-02", emotion="happy", title="爱你", artist="王心凌", query="爱你 王心凌"),
    dict(id="vocal-happy-10", emotion="happy", title="星晴", artist="周杰伦", query="星晴 周杰伦"),
    dict(id="vocal-happy-04", emotion="happy", title="日不落", artist="蔡依林", query="日不落 蔡依林"),
    dict(id="vocal-happy-07", emotion="happy", title="甜甜的", artist="周杰伦", query="甜甜的 周杰伦"),
    dict(id="vocal-happy-03", emotion="happy", title="阳光宅男", artist="周杰伦", query="阳光宅男 周杰伦"),
    dict(id="vocal-happy-05", emotion="happy", title="恋爱ing", artist="五月天", query="恋爱ing 五月天"),
    dict(id="vocal-happy-11", emotion="happy", title="Mojito", artist="周杰伦", query="Mojito 周杰伦"),
    dict(id="vocal-happy-12", emotion="happy", title="我的歌声里", artist="曲婉婷", query="我的歌声里 曲婉婷"),
    dict(id="vocal-happy-13", emotion="happy", title="小酒窝", artist="林俊杰", query="小酒窝 林俊杰"),
    dict(id="vocal-happy-14", emotion="happy", title="说爱你", artist="蔡依林", query="说爱你 蔡依林"),
    dict(id="vocal-happy-15", emotion="happy", title="小苹果", artist="筷子兄弟", query="小苹果 筷子兄弟"),
    dict(id="vocal-happy-16", emotion="happy", title="喜欢你", artist="G.E.M. 邓紫棋", query="喜欢你 邓紫棋"),
    dict(id="vocal-happy-17", emotion="happy", title="暖暖", artist="梁静茹", query="暖暖 梁静茹"),
    dict(id="vocal-happy-18", emotion="happy", title="彩虹", artist="周杰伦", query="彩虹 周杰伦"),
    dict(id="vocal-happy-19", emotion="happy", title="可爱女人", artist="周杰伦", query="可爱女人 周杰伦"),
    dict(id="vocal-happy-20", emotion="happy", title="Happy", artist="Pharrell Williams", query="Happy Pharrell Williams"),
    dict(id="vocal-happy-21", emotion="happy", title="笑忘歌", artist="五月天", query="笑忘歌 五月天"),
    dict(id="vocal-happy-22", emotion="happy", title="给我一首歌的时间", artist="周杰伦", query="给我一首歌的时间 周杰伦"),
    dict(id="vocal-happy-23", emotion="happy", title="第一次爱的人", artist="王心凌", query="第一次爱的人 王心凌"),
    dict(id="vocal-happy-24", emotion="happy", title="Good Time", artist="Owl City", query="Good Time Owl City"),
    dict(id="vocal-happy-25", emotion="happy", title="浪漫手机", artist="周杰伦", query="浪漫手机 周杰伦"),
    dict(id="vocal-happy-26", emotion="happy", title="不能说的秘密", artist="周杰伦", query="不能说的秘密 周杰伦"),
    dict(id="vocal-happy-27", emotion="happy", title="今天你要嫁给我", artist="陶喆", query="今天你要嫁给我 陶喆"),
    dict(id="vocal-happy-28", emotion="happy", title="就是爱你", artist="陶喆", query="就是爱你 陶喆"),
    dict(id="vocal-happy-29", emotion="happy", title="被风吹过的夏天", artist="金莎", query="被风吹过的夏天 金莎"),
    dict(id="vocal-happy-30", emotion="happy", title="夏日之风", artist="温岚", query="夏日之风 温岚"),
    dict(id="vocal-happy-31", emotion="happy", title="快乐崇拜", artist="潘玮柏", query="快乐崇拜 潘玮柏"),
    dict(id="vocal-happy-32", emotion="happy", title="Walking On Sunshine", artist="Katrina and the Waves", query="Walking On Sunshine Katrina"),
    # 怒 · 攻击性、宣泄，不用励志燃曲
    dict(id="vocal-angry-01", emotion="angry", title="双截棍", artist="周杰伦", query="双截棍 周杰伦"),
    dict(id="vocal-angry-06", emotion="angry", title="霍元甲", artist="周杰伦", query="霍元甲 周杰伦"),
    dict(id="vocal-angry-02", emotion="angry", title="龙拳", artist="周杰伦", query="龙拳 周杰伦"),
    dict(id="vocal-angry-09", emotion="angry", title="双刀", artist="周杰伦", query="双刀 周杰伦"),
    dict(id="vocal-angry-03", emotion="angry", title="怒放的生命", artist="汪峰", query="怒放的生命 汪峰"),
    dict(id="vocal-angry-08", emotion="angry", title="一无所有", artist="崔健", query="一无所有 崔健"),
    dict(id="vocal-angry-10", emotion="angry", title="最后的战役", artist="周杰伦", query="最后的战役 周杰伦"),
    dict(id="vocal-angry-05", emotion="angry", title="Numb", artist="LINKIN PARK", query="Numb LINKIN PARK"),
    dict(id="vocal-angry-07", emotion="angry", title="分裂", artist="周杰伦", query="分裂 周杰伦"),
    dict(id="vocal-angry-04", emotion="angry", title="无地自容", artist="黑豹乐队", query="无地自容 黑豹"),
    dict(id="vocal-angry-11", emotion="angry", title="死了都要爱", artist="信乐团", query="死了都要爱 信乐团"),
    dict(id="vocal-angry-12", emotion="angry", title="我恨我爱你", artist="张惠妹", query="我恨我爱你 张惠妹"),
    dict(id="vocal-angry-13", emotion="angry", title="不再犹豫", artist="Beyond", query="不再犹豫 Beyond"),
    dict(id="vocal-angry-14", emotion="angry", title="止战之殇", artist="周杰伦", query="止战之殇 周杰伦"),
    dict(id="vocal-angry-15", emotion="angry", title="世界末日", artist="周杰伦", query="世界末日 周杰伦"),
    dict(id="vocal-angry-16", emotion="angry", title="斗牛", artist="周杰伦", query="斗牛 周杰伦"),
    dict(id="vocal-angry-17", emotion="angry", title="我管你", artist="华晨宇", query="我管你 华晨宇"),
    dict(id="vocal-angry-18", emotion="angry", title="龙战骑士", artist="周杰伦", query="龙战骑士 周杰伦"),
    dict(id="vocal-angry-19", emotion="angry", title="乱舞春秋", artist="周杰伦", query="乱舞春秋 周杰伦"),
    dict(id="vocal-angry-20", emotion="angry", title="In The End", artist="LINKIN PARK", query="In The End LINKIN PARK"),
    dict(id="vocal-angry-21", emotion="angry", title="假行僧", artist="崔健", query="假行僧 崔健"),
    dict(id="vocal-angry-22", emotion="angry", title="精忠报国", artist="屠洪刚", query="精忠报国 屠洪刚"),
    dict(id="vocal-angry-23", emotion="angry", title="齐天", artist="华晨宇", query="齐天 华晨宇"),
    dict(id="vocal-angry-24", emotion="angry", title="Faint", artist="LINKIN PARK", query="Faint LINKIN PARK"),
    dict(id="vocal-angry-25", emotion="angry", title="将军", artist="周杰伦", query="将军 周杰伦"),
    dict(id="vocal-angry-26", emotion="angry", title="杀破狼", artist="JS", query="杀破狼 JS"),
    dict(id="vocal-angry-27", emotion="angry", title="悟空", artist="戴荃", query="悟空 戴荃"),
    dict(id="vocal-angry-28", emotion="angry", title="刀马旦", artist="李玟", query="刀马旦 李玟"),
    dict(id="vocal-angry-29", emotion="angry", title="新长征路上的摇滚", artist="崔健", query="新长征路上的摇滚 崔健"),
    dict(id="vocal-angry-30", emotion="angry", title="男儿当自强", artist="林子祥", query="男儿当自强 林子祥"),
    dict(id="vocal-angry-31", emotion="angry", title="One Step Closer", artist="LINKIN PARK", query="One Step Closer LINKIN PARK"),
    dict(id="vocal-angry-32", emotion="angry", title="Crawling", artist="LINKIN PARK", query="Crawling LINKIN PARK"),
    # 哀 · 哭腔情歌，KTV 一放就鼻酸
    dict(id="vocal-sad-01", emotion="sad", title="后来", artist="刘若英", query="后来 刘若英"),
    dict(id="vocal-sad-10", emotion="sad", title="那些年", artist="胡夏", query="那些年 胡夏"),
    dict(id="vocal-sad-02", emotion="sad", title="十年", artist="陈奕迅", query="十年 陈奕迅"),
    dict(id="vocal-sad-09", emotion="sad", title="安静", artist="周杰伦", query="安静 周杰伦"),
    dict(id="vocal-sad-03", emotion="sad", title="体面", artist="于文文", query="体面 于文文"),
    dict(id="vocal-sad-06", emotion="sad", title="可惜不是你", artist="梁静茹", query="可惜不是你 梁静茹"),
    dict(id="vocal-sad-07", emotion="sad", title="突然好想你", artist="五月天", query="突然好想你 五月天"),
    dict(id="vocal-sad-08", emotion="sad", title="泡沫", artist="G.E.M. 邓紫棋", query="泡沫 G.E.M."),
    dict(id="vocal-sad-04", emotion="sad", title="听海", artist="张惠妹", query="听海 张惠妹"),
    dict(id="vocal-sad-05", emotion="sad", title="消愁", artist="毛不易", query="消愁 毛不易"),
    dict(id="vocal-sad-11", emotion="sad", title="开不了口", artist="周杰伦", query="开不了口 周杰伦"),
    dict(id="vocal-sad-12", emotion="sad", title="好久不见", artist="陈奕迅", query="好久不见 陈奕迅"),
    dict(id="vocal-sad-13", emotion="sad", title="花海", artist="周杰伦", query="花海 周杰伦"),
    dict(id="vocal-sad-14", emotion="sad", title="搁浅", artist="周杰伦", query="搁浅 周杰伦"),
    dict(id="vocal-sad-15", emotion="sad", title="说好的幸福呢", artist="周杰伦", query="说好的幸福呢 周杰伦"),
    dict(id="vocal-sad-16", emotion="sad", title="空白格", artist="蔡健雅", query="空白格 蔡健雅"),
    dict(id="vocal-sad-17", emotion="sad", title="我怀念的", artist="孙燕姿", query="我怀念的 孙燕姿"),
    dict(id="vocal-sad-18", emotion="sad", title="修炼爱情", artist="林俊杰", query="修炼爱情 林俊杰"),
    dict(id="vocal-sad-19", emotion="sad", title="说散就散", artist="JC 陈咏桐", query="说散就散 JC"),
    dict(id="vocal-sad-20", emotion="sad", title="Someone Like You", artist="Adele", query="Someone Like You Adele"),
    dict(id="vocal-sad-21", emotion="sad", title="她说", artist="林俊杰", query="她说 林俊杰"),
    dict(id="vocal-sad-22", emotion="sad", title="勇气", artist="梁静茹", query="勇气 梁静茹"),
    dict(id="vocal-sad-23", emotion="sad", title="富士山下", artist="陈奕迅", query="富士山下 陈奕迅"),
    dict(id="vocal-sad-24", emotion="sad", title="When I Was Your Man", artist="Bruno Mars", query="When I Was Your Man Bruno Mars"),
    dict(id="vocal-sad-25", emotion="sad", title="红豆", artist="王菲", query="红豆 王菲"),
    dict(id="vocal-sad-26", emotion="sad", title="匆匆那年", artist="王菲", query="匆匆那年 王菲"),
    dict(id="vocal-sad-27", emotion="sad", title="你不知道的事", artist="王力宏", query="你不知道的事 王力宏"),
    dict(id="vocal-sad-28", emotion="sad", title="过火", artist="张信哲", query="过火 张信哲"),
    dict(id="vocal-sad-29", emotion="sad", title="一千年以后", artist="林俊杰", query="一千年以后 林俊杰"),
    dict(id="vocal-sad-30", emotion="sad", title="刻在我心底的名字", artist="卢广仲", query="刻在我心底的名字 卢广仲"),
    dict(id="vocal-sad-31", emotion="sad", title="残酷月光", artist="林宥嘉", query="残酷月光 林宥嘉"),
    dict(id="vocal-sad-32", emotion="sad", title="Hello", artist="Adele", query="Hello Adele"),
    # 惧 · 暗夜、鬼气、惊悚叙事
    dict(id="vocal-fear-01", emotion="fear", title="夜曲", artist="周杰伦", query="夜曲 周杰伦"),
    dict(id="vocal-fear-09", emotion="fear", title="黑色毛衣", artist="周杰伦", query="黑色毛衣 周杰伦"),
    dict(id="vocal-fear-10", emotion="fear", title="忍者", artist="周杰伦", query="忍者 周杰伦"),
    dict(id="vocal-fear-02", emotion="fear", title="夜的第七章", artist="周杰伦", query="夜的第七章 周杰伦"),
    dict(id="vocal-fear-08", emotion="fear", title="烟花易冷", artist="周杰伦", query="烟花易冷 周杰伦"),
    dict(id="vocal-fear-03", emotion="fear", title="威廉古堡", artist="周杰伦", query="威廉古堡 周杰伦"),
    dict(id="vocal-fear-04", emotion="fear", title="以父之名", artist="周杰伦", query="以父之名 周杰伦"),
    dict(id="vocal-fear-06", emotion="fear", title="迷魂曲", artist="周杰伦", query="迷魂曲 周杰伦"),
    dict(id="vocal-fear-07", emotion="fear", title="黑色幽默", artist="周杰伦", query="黑色幽默 周杰伦"),
    dict(id="vocal-fear-05", emotion="fear", title="Thriller", artist="Michael Jackson", query="Thriller Michael Jackson"),
    dict(id="vocal-fear-11", emotion="fear", title="发如雪", artist="周杰伦", query="发如雪 周杰伦"),
    dict(id="vocal-fear-12", emotion="fear", title="来自天堂的魔鬼", artist="G.E.M. 邓紫棋", query="来自天堂的魔鬼 邓紫棋"),
    dict(id="vocal-fear-13", emotion="fear", title="千里之外", artist="周杰伦", query="千里之外 周杰伦"),
    dict(id="vocal-fear-14", emotion="fear", title="乔克叔叔", artist="周杰伦", query="乔克叔叔 周杰伦"),
    dict(id="vocal-fear-15", emotion="fear", title="皮影戏", artist="周杰伦", query="皮影戏 周杰伦"),
    dict(id="vocal-fear-16", emotion="fear", title="黄金甲", artist="周杰伦", query="黄金甲 周杰伦"),
    dict(id="vocal-fear-17", emotion="fear", title="四面楚歌", artist="周杰伦", query="四面楚歌 周杰伦"),
    dict(id="vocal-fear-18", emotion="fear", title="黑暗骑士", artist="林俊杰", query="黑暗骑士 林俊杰"),
    dict(id="vocal-fear-19", emotion="fear", title="魔术先生", artist="周杰伦", query="魔术先生 周杰伦"),
    dict(id="vocal-fear-20", emotion="fear", title="Bring Me To Life", artist="Evanescence", query="Bring Me To Life Evanescence"),
    dict(id="vocal-fear-21", emotion="fear", title="不死之身", artist="林俊杰", query="不死之身 林俊杰"),
    dict(id="vocal-fear-22", emotion="fear", title="反方向的钟", artist="周杰伦", query="反方向的钟 周杰伦"),
    dict(id="vocal-fear-23", emotion="fear", title="醉赤壁", artist="林俊杰", query="醉赤壁 林俊杰"),
    dict(id="vocal-fear-24", emotion="fear", title="Going Under", artist="Evanescence", query="Going Under Evanescence"),
    dict(id="vocal-fear-25", emotion="fear", title="暗号", artist="周杰伦", query="暗号 周杰伦"),
    dict(id="vocal-fear-26", emotion="fear", title="杀手", artist="林俊杰", query="杀手 林俊杰"),
    dict(id="vocal-fear-27", emotion="fear", title="黑色柳丁", artist="陶喆", query="黑色柳丁 陶喆"),
    dict(id="vocal-fear-28", emotion="fear", title="夜半歌声", artist="张国荣", query="夜半歌声 张国荣"),
    dict(id="vocal-fear-29", emotion="fear", title="天黑黑", artist="孙燕姿", query="天黑黑 孙燕姿"),
    dict(id="vocal-fear-30", emotion="fear", title="鬼迷心窍", artist="李宗盛", query="鬼迷心窍 李宗盛"),
    dict(id="vocal-fear-31", emotion="fear", title="Haunted", artist="Evanescence", query="Haunted Evanescence"),
    dict(id="vocal-fear-32", emotion="fear", title="Smooth Criminal", artist="Michael Jackson", query="Smooth Criminal Michael Jackson"),
    # 惊 · 突然爆开、哇一下，和「甜甜的喜」分开
    dict(id="vocal-surprise-02", emotion="surprise", title="野狼disco", artist="宝石Gem", query="野狼disco 宝石Gem"),
    dict(id="vocal-surprise-07", emotion="surprise", title="卡路里", artist="火箭少女101", query="卡路里 火箭少女101"),
    dict(id="vocal-surprise-01", emotion="surprise", title="本草纲目", artist="周杰伦", query="本草纲目 周杰伦"),
    dict(id="vocal-surprise-10", emotion="surprise", title="我的滑板鞋", artist="华晨宇", query="我的滑板鞋 华晨宇"),
    dict(id="vocal-surprise-09", emotion="surprise", title="牛仔很忙", artist="周杰伦", query="牛仔很忙 周杰伦"),
    dict(id="vocal-surprise-04", emotion="surprise", title="最炫民族风", artist="凤凰传奇", query="最炫民族风 凤凰传奇"),
    dict(id="vocal-surprise-05", emotion="surprise", title="龙卷风", artist="周杰伦", query="龙卷风 周杰伦"),
    dict(id="vocal-surprise-03", emotion="surprise", title="离开地球表面", artist="五月天", query="离开地球表面 五月天"),
    dict(id="vocal-surprise-06", emotion="surprise", title="半兽人", artist="周杰伦", query="半兽人 周杰伦"),
    dict(id="vocal-surprise-08", emotion="surprise", title="自由飞翔", artist="凤凰传奇", query="自由飞翔 凤凰传奇"),
    dict(id="vocal-surprise-11", emotion="surprise", title="舞娘", artist="蔡依林", query="舞娘 蔡依林"),
    dict(id="vocal-surprise-12", emotion="surprise", title="大艺术家", artist="蔡依林", query="大艺术家 蔡依林"),
    dict(id="vocal-surprise-13", emotion="surprise", title="精舞门", artist="罗志祥", query="精舞门 罗志祥"),
    dict(id="vocal-surprise-14", emotion="surprise", title="不潮不用花钱", artist="林俊杰", query="不潮不用花钱 林俊杰"),
    dict(id="vocal-surprise-15", emotion="surprise", title="伤心的人别听慢歌", artist="五月天", query="伤心的人别听慢歌 五月天"),
    dict(id="vocal-surprise-16", emotion="surprise", title="特务J", artist="蔡依林", query="特务J 蔡依林"),
    dict(id="vocal-surprise-17", emotion="surprise", title="园游会", artist="周杰伦", query="园游会 周杰伦"),
    dict(id="vocal-surprise-18", emotion="surprise", title="我的地盘", artist="周杰伦", query="我的地盘 周杰伦"),
    dict(id="vocal-surprise-19", emotion="surprise", title="迷迭香", artist="周杰伦", query="迷迭香 周杰伦"),
    dict(id="vocal-surprise-20", emotion="surprise", title="Uptown Funk", artist="Mark Ronson", query="Uptown Funk Mark Ronson"),
    dict(id="vocal-surprise-21", emotion="surprise", title="看我72变", artist="蔡依林", query="看我72变 蔡依林"),
    dict(id="vocal-surprise-22", emotion="surprise", title="Super Star", artist="S.H.E", query="Super Star SHE"),
    dict(id="vocal-surprise-23", emotion="surprise", title="远走高飞", artist="金志文", query="远走高飞 金志文"),
    dict(id="vocal-surprise-24", emotion="surprise", title="Shake It Off", artist="Taylor Swift", query="Shake It Off Taylor Swift"),
    dict(id="vocal-surprise-25", emotion="surprise", title="火力全开", artist="王力宏", query="火力全开 王力宏"),
    dict(id="vocal-surprise-26", emotion="surprise", title="舞极限", artist="罗志祥", query="舞极限 罗志祥"),
    dict(id="vocal-surprise-27", emotion="surprise", title="马德里不思议", artist="蔡依林", query="马德里不思议 蔡依林"),
    dict(id="vocal-surprise-28", emotion="surprise", title="Honey", artist="王心凌", query="Honey 王心凌"),
    dict(id="vocal-surprise-29", emotion="surprise", title="荷塘月色", artist="凤凰传奇", query="荷塘月色 凤凰传奇"),
    dict(id="vocal-surprise-30", emotion="surprise", title="郎的诱惑", artist="凤凰传奇", query="郎的诱惑 凤凰传奇"),
    dict(id="vocal-surprise-31", emotion="surprise", title="爱情36计", artist="蔡依林", query="爱情36计 蔡依林"),
    dict(id="vocal-surprise-32", emotion="surprise", title="Dynamite", artist="BTS", query="Dynamite BTS"),
    # 厌 · 嫌弃、自嘲、刺耳，不用漂亮情歌
    dict(id="vocal-disgust-01", emotion="disgust", title="丑八怪", artist="薛之谦", query="丑八怪 薛之谦"),
    dict(id="vocal-disgust-02", emotion="disgust", title="演员", artist="薛之谦", query="演员 薛之谦"),
    dict(id="vocal-disgust-09", emotion="disgust", title="淘汰", artist="陈奕迅", query="淘汰 陈奕迅"),
    dict(id="vocal-disgust-10", emotion="disgust", title="浮夸", artist="陈奕迅", query="浮夸 陈奕迅"),
    dict(id="vocal-disgust-06", emotion="disgust", title="绅士", artist="薛之谦", query="绅士 薛之谦"),
    dict(id="vocal-disgust-08", emotion="disgust", title="说谎", artist="林宥嘉", query="说谎 林宥嘉"),
    dict(id="vocal-disgust-07", emotion="disgust", title="红玫瑰", artist="陈奕迅", query="红玫瑰 陈奕迅"),
    dict(id="vocal-disgust-03", emotion="disgust", title="怪咖", artist="薛之谦", query="怪咖 薛之谦"),
    dict(id="vocal-disgust-05", emotion="disgust", title="阴天", artist="莫文蔚", query="阴天 莫文蔚"),
    dict(id="vocal-disgust-04", emotion="disgust", title="垃圾场", artist="何勇", query="垃圾场 何勇"),
    dict(id="vocal-disgust-11", emotion="disgust", title="Play我呸", artist="蔡依林", query="Play我呸 蔡依林"),
    dict(id="vocal-disgust-12", emotion="disgust", title="不将就", artist="李荣浩", query="不将就 李荣浩"),
    dict(id="vocal-disgust-13", emotion="disgust", title="你还要我怎样", artist="薛之谦", query="你还要我怎样 薛之谦"),
    dict(id="vocal-disgust-14", emotion="disgust", title="最佳损友", artist="陈奕迅", query="最佳损友 陈奕迅"),
    dict(id="vocal-disgust-15", emotion="disgust", title="浪费", artist="林宥嘉", query="浪费 林宥嘉"),
    dict(id="vocal-disgust-16", emotion="disgust", title="你要的全拿走", artist="胡彦斌", query="你要的全拿走 胡彦斌"),
    dict(id="vocal-disgust-17", emotion="disgust", title="算什么男人", artist="周杰伦", query="算什么男人 周杰伦"),
    dict(id="vocal-disgust-18", emotion="disgust", title="不爱我就拉倒", artist="周杰伦", query="不爱我就拉倒 周杰伦"),
    dict(id="vocal-disgust-19", emotion="disgust", title="暧昧", artist="薛之谦", query="暧昧 薛之谦"),
    dict(id="vocal-disgust-20", emotion="disgust", title="Complicated", artist="Avril Lavigne", query="Complicated Avril Lavigne"),
    dict(id="vocal-disgust-21", emotion="disgust", title="意外", artist="薛之谦", query="意外 薛之谦"),
    dict(id="vocal-disgust-22", emotion="disgust", title="喜剧之王", artist="李荣浩", query="喜剧之王 李荣浩"),
    dict(id="vocal-disgust-23", emotion="disgust", title="我好像在哪见过你", artist="薛之谦", query="我好像在哪见过你 薛之谦"),
    dict(id="vocal-disgust-24", emotion="disgust", title="Girlfriend", artist="Avril Lavigne", query="Girlfriend Avril Lavigne"),
    dict(id="vocal-disgust-25", emotion="disgust", title="天份", artist="薛之谦", query="天份 薛之谦"),
    dict(id="vocal-disgust-26", emotion="disgust", title="其实", artist="薛之谦", query="其实 薛之谦"),
    dict(id="vocal-disgust-27", emotion="disgust", title="一半", artist="薛之谦", query="一半 薛之谦"),
    dict(id="vocal-disgust-28", emotion="disgust", title="动物世界", artist="薛之谦", query="动物世界 薛之谦"),
    dict(id="vocal-disgust-29", emotion="disgust", title="K歌之王", artist="陈奕迅", query="K歌之王 陈奕迅"),
    dict(id="vocal-disgust-30", emotion="disgust", title="人来人往", artist="陈奕迅", query="人来人往 陈奕迅"),
    dict(id="vocal-disgust-31", emotion="disgust", title="你的背包", artist="陈奕迅", query="你的背包 陈奕迅"),
    dict(id="vocal-disgust-32", emotion="disgust", title="Sk8er Boi", artist="Avril Lavigne", query="Sk8er Boi Avril Lavigne"),
    # 中性 · 平走、日常，不哭不闹不嗨
    dict(id="vocal-neutral-06", emotion="neutral", title="晴天", artist="周杰伦", query="晴天 周杰伦"),
    dict(id="vocal-neutral-09", emotion="neutral", title="七里香", artist="周杰伦", query="七里香 周杰伦"),
    dict(id="vocal-neutral-07", emotion="neutral", title="稻香", artist="周杰伦", query="稻香 周杰伦"),
    dict(id="vocal-neutral-01", emotion="neutral", title="成都", artist="赵雷", query="成都 赵雷"),
    dict(id="vocal-neutral-02", emotion="neutral", title="青花瓷", artist="周杰伦", query="青花瓷 周杰伦"),
    dict(id="vocal-neutral-10", emotion="neutral", title="夜空中最亮的星", artist="逃跑计划", query="夜空中最亮的星 逃跑计划"),
    dict(id="vocal-neutral-08", emotion="neutral", title="南山南", artist="马頔", query="南山南 马頔"),
    dict(id="vocal-neutral-03", emotion="neutral", title="听妈妈的话", artist="周杰伦", query="听妈妈的话 周杰伦"),
    dict(id="vocal-neutral-04", emotion="neutral", title="春风十里", artist="鹿先森乐队", query="春风十里 鹿先森"),
    dict(id="vocal-neutral-05", emotion="neutral", title="Count on Me", artist="Bruno Mars", query="Count on Me Bruno Mars"),
    dict(id="vocal-neutral-11", emotion="neutral", title="同桌的你", artist="老狼", query="同桌的你 老狼"),
    dict(id="vocal-neutral-12", emotion="neutral", title="李白", artist="李荣浩", query="李白 李荣浩"),
    dict(id="vocal-neutral-13", emotion="neutral", title="因为爱情", artist="陈奕迅", query="因为爱情 陈奕迅"),
    dict(id="vocal-neutral-14", emotion="neutral", title="东风破", artist="周杰伦", query="东风破 周杰伦"),
    dict(id="vocal-neutral-15", emotion="neutral", title="理想三旬", artist="陈鸿宇", query="理想三旬 陈鸿宇"),
    dict(id="vocal-neutral-16", emotion="neutral", title="慢慢喜欢你", artist="莫文蔚", query="慢慢喜欢你 莫文蔚"),
    dict(id="vocal-neutral-17", emotion="neutral", title="遇见", artist="孙燕姿", query="遇见 孙燕姿"),
    dict(id="vocal-neutral-18", emotion="neutral", title="南方姑娘", artist="赵雷", query="南方姑娘 赵雷"),
    dict(id="vocal-neutral-19", emotion="neutral", title="模特", artist="李荣浩", query="模特 李荣浩"),
    dict(id="vocal-neutral-20", emotion="neutral", title="I'm Yours", artist="Jason Mraz", query="I'm Yours Jason Mraz"),
    dict(id="vocal-neutral-21", emotion="neutral", title="董小姐", artist="宋冬野", query="董小姐 宋冬野"),
    dict(id="vocal-neutral-22", emotion="neutral", title="兰亭序", artist="周杰伦", query="兰亭序 周杰伦"),
    dict(id="vocal-neutral-23", emotion="neutral", title="半岛铁盒", artist="周杰伦", query="半岛铁盒 周杰伦"),
    dict(id="vocal-neutral-24", emotion="neutral", title="Perfect", artist="Ed Sheeran", query="Perfect Ed Sheeran"),
    dict(id="vocal-neutral-25", emotion="neutral", title="轨迹", artist="周杰伦", query="轨迹 周杰伦"),
    dict(id="vocal-neutral-26", emotion="neutral", title="蒲公英的约定", artist="周杰伦", query="蒲公英的约定 周杰伦"),
    dict(id="vocal-neutral-27", emotion="neutral", title="回到过去", artist="周杰伦", query="回到过去 周杰伦"),
    dict(id="vocal-neutral-28", emotion="neutral", title="三年二班", artist="周杰伦", query="三年二班 周杰伦"),
    dict(id="vocal-neutral-29", emotion="neutral", title="外婆", artist="周杰伦", query="外婆 周杰伦"),
    dict(id="vocal-neutral-30", emotion="neutral", title="年少有为", artist="李荣浩", query="年少有为 李荣浩"),
    dict(id="vocal-neutral-31", emotion="neutral", title="斑马斑马", artist="宋冬野", query="斑马斑马 宋冬野"),
    dict(id="vocal-neutral-32", emotion="neutral", title="安和桥", artist="宋冬野", query="安和桥 宋冬野"),
]


def is_instrumental(title: str = "", artist: str = "", genre: str = "") -> bool:
    blob = f"{title} {artist} {genre}".lower()
    text = f"{title}{artist}{genre}"
    for mark in INSTRUMENTAL_MARKERS:
        if mark.isascii():
            if mark in blob:
                return True
        elif mark in text:
            return True
    if "piano" in blob and "cover" in blob:
        return True
    return False


def is_stock_track(title: str = "", artist: str = "") -> bool:
    blob = f"{title} {artist}".lower()
    if any(mark in blob for mark in STOCK_TITLE_MARKERS):
        return True
    if any(who in blob for who in SKIP_PERFORMERS):
        return True
    return False


def is_vocal_song(title: str = "", artist: str = "", genre: str = "") -> bool:
    if is_instrumental(title, artist, genre):
        return False
    if is_stock_track(title, artist):
        return False
    return True

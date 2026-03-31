from __future__ import annotations

BEAUTY_TAXONOMY: dict[str, list[str]] = {
    "防晒": [
        "防晒",
        "防晒霜",
        "防晒乳",
        "防晒喷雾",
        "防晒棒",
        "物理防晒",
        "化学防晒",
        "敏感肌防晒",
        "油皮防晒",
        "干皮防晒",
        "军训防晒",
    ],
    "精华": [
        "精华",
        "精华液",
        "次抛精华",
        "抗老精华",
        "修护精华",
        "美白精华",
        "淡斑精华",
        "保湿精华",
    ],
    "修护敏感肌": [
        "修护",
        "抗老",
        "敏感肌修护",
        "屏障修护",
    ],
    "面膜": [
        "面膜",
        "补水面膜",
        "清洁面膜",
    ],
    "面霜眼霜": [
        "面霜",
        "修护面霜",
        "抗老面霜",
        "敏感肌面霜",
        "眼霜",
    ],
    "水乳化妆水": [
        "水乳",
        "爽肤水",
        "精华水",
    ],
    "清洁卸妆": [
        "洁面",
        "洗面奶",
        "卸妆",
        "卸妆油",
        "卸妆膏",
    ],
    "底妆": [
        "底妆",
        "粉底液",
        "气垫",
        "持妆粉底",
        "油皮底妆",
        "干皮底妆",
        "夏季底妆",
    ],
    "定妆妆前": [
        "遮瑕",
        "散粉",
        "定妆",
        "定妆喷雾",
        "定妆粉",
        "妆前乳",
        "隔离",
        "粉饼",
        "遮瑕液",
    ],
    "唇部彩妆": [
        "口红",
        "唇釉",
        "唇蜜",
    ],
    "眼部面部彩妆": [
        "腮红",
        "高光",
        "眼影",
        "眉笔",
        "睫毛膏",
        "眼线",
        "修容",
    ],
    "场景人群风格": [
        "学生党美妆",
        "平价彩妆",
        "通勤妆",
        "伪素颜妆",
    ],
}


BEAUTY_RECOMMENDED_EXPANSIONS: dict[str, list[str]] = {
    "功效补充": [
        "控油",
        "祛痘",
        "维稳",
        "抗氧化",
        "提亮",
        "去黄",
        "毛孔",
        "补水",
    ],
    "肤质人群补充": [
        "混油皮",
        "混干皮",
        "痘肌",
        "熬夜肌",
        "熟龄肌",
        "新手化妆",
    ],
    "场景补充": [
        "通勤底妆",
        "约会妆",
        "淡妆",
        "出游防晒",
        "伪素颜底妆",
    ],
    "品牌补充": [
        "兰蔻",
        "雅诗兰黛",
        "欧莱雅",
        "可复美",
        "修丽可",
        "阿玛尼",
        "YSL",
        "毛戈平",
        "资生堂",
        "安热沙",
    ],
}


def flatten_keywords(taxonomy: dict[str, list[str]]) -> list[str]:
    seen: set[str] = set()
    keywords: list[str] = []

    for values in taxonomy.values():
        for keyword in values:
            if keyword in seen:
                continue
            seen.add(keyword)
            keywords.append(keyword)

    return keywords


BEAUTY_KEYWORDS: list[str] = flatten_keywords(BEAUTY_TAXONOMY)
BEAUTY_EXPANSION_KEYWORDS: list[str] = flatten_keywords(BEAUTY_RECOMMENDED_EXPANSIONS)
BEAUTY_ALL_KEYWORDS: list[str] = flatten_keywords(
    {
        "core": BEAUTY_KEYWORDS,
        "expansion": BEAUTY_EXPANSION_KEYWORDS,
    }
)

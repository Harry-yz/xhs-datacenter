import unittest


from app.services.brand_recognition import build_brand_seed_items, extract_brand_matches


class BrandRecognitionTests(unittest.TestCase):
    def test_build_brand_seed_items_includes_beauty_brands(self) -> None:
        items = build_brand_seed_items()
        by_name = {item["brand_name"]: item for item in items}

        self.assertIn("兰蔻", by_name)
        self.assertIn("雅诗兰黛", by_name)
        self.assertIn("YSL", by_name)

        self.assertEqual(by_name["兰蔻"]["industry"], "美妆护肤")
        self.assertIn("ysl", [alias.lower() for alias in by_name["YSL"]["alias"]])

    def test_extract_brand_matches_prefers_longer_aliases_and_dedupes(self) -> None:
        matches = extract_brand_matches(
            title="YSL黑管和兰蔻粉水能一起用吗",
            content="这次顺手也试了圣罗兰黑管，感觉和兰蔻粉水搭配还不错。",
            tags=["圣罗兰", "粉水"],
        )

        self.assertEqual(
            [match["brand_name"] for match in matches],
            ["YSL", "兰蔻"],
        )
        self.assertEqual(matches[0]["matched_keyword"], "圣罗兰")
        self.assertEqual(matches[1]["matched_keyword"], "兰蔻")

    def test_extract_brand_matches_handles_case_insensitive_english_alias(self) -> None:
        matches = extract_brand_matches(
            title="ysl粉气垫真的适合油皮吗",
            content="最近一直在看 ysl 和 Armani 的底妆。",
            tags=["油皮底妆"],
        )

        self.assertEqual(
            [match["brand_name"] for match in matches],
            ["YSL", "阿玛尼"],
        )


if __name__ == "__main__":
    unittest.main()

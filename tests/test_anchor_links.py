import unittest


from app.services.anchor_links import resolve_anchor_link, resolve_author_id


class AnchorLinkTests(unittest.TestCase):
    def test_resolve_anchor_link_prefers_direct_profile_url(self) -> None:
        link = "https://www.xiaohongshu.com/user/profile/5a5b1a1b4eacab69e79c2338"
        self.assertEqual(resolve_anchor_link(anchor_ref=link, stored_anchor_link=None), link)

    def test_resolve_anchor_link_uses_stored_profile_url_for_author_id(self) -> None:
        stored = "https://www.xiaohongshu.com/user/profile/601d007e000000000101efa8"
        self.assertEqual(resolve_anchor_link(anchor_ref="kilo8866", stored_anchor_link=stored), stored)

    def test_resolve_anchor_link_returns_none_without_valid_profile_url(self) -> None:
        self.assertIsNone(resolve_anchor_link(anchor_ref="262624206", stored_anchor_link=None))

    def test_resolve_author_id_falls_back_to_stored_author(self) -> None:
        self.assertEqual(resolve_author_id(author_ref=None, stored_author_id="550767102"), "550767102")


if __name__ == "__main__":
    unittest.main()

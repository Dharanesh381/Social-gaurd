"""Reddit Public Content Extractor.

Extracts post text, hashtags, visible comments, timestamps, author information,
and media references from publicly rendered Reddit HTML or JSON structures.

COMPLIANCE & PRIVACY:
- Only parses publicly rendered DOM elements.
- Never attempts authentication bypass, private subreddits, or rate-limit circumvention.
- Gracefully returns null/empty values when elements are missing.
"""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from app.platform.base import BasePlatformExtractor
from app.schemas.domain_models import (
    Comment,
    Media,
    MediaType,
    SocialMediaPost,
    UserProfile,
)

logger = logging.getLogger(__name__)


class RedditExtractor(BasePlatformExtractor):
    """Platform extractor for Reddit posts and discussion threads."""

    def extract_post_from_html(self, html_content: str, source_url: str | None = None) -> SocialMediaPost:
        """Extract structured SocialMediaPost from Reddit post HTML DOM.

        Extracts:
        - Post title + body text
        - Embedded hashtags / topic tags
        - Post timestamp (<time> tags or datetime attributes)
        - Public author username
        - Visible attached image / preview media
        - Visible comment elements (text, author, timestamp, upvotes)
        """
        if not html_content or not html_content.strip():
            return SocialMediaPost(
                platform="reddit",
                text="No content provided.",
            )

        soup = BeautifulSoup(html_content, "html.parser")

        # ----------------------------------------------------------------------
        # 1. Post Text & Title Extraction
        # ----------------------------------------------------------------------
        title = ""
        # Modern Reddit uses shreddit-post or h1/post-title tags
        title_el = (
            soup.find("h1")
            or soup.find("a", {"data-testid": "post-title"})
            or soup.find("div", {"data-adclicklocation": "title"})
            or soup.find("h2")
        )
        if title_el:
            title = title_el.get_text(strip=True)

        body_text = ""
        # Reddit post body paragraphs
        body_el = (
            soup.find("div", {"data-testid": "post-rtjson-content"})
            or soup.find("div", class_=lambda c: c and "RichTextJSON-root" in c)
            or soup.find("div", {"slot": "text-body"})
            or soup.find("div", class_="usertext-body")
        )
        if body_el:
            paragraphs = [p.get_text(strip=True) for p in body_el.find_all(["p", "li"])]
            body_text = "\n".join(paragraphs) if paragraphs else body_el.get_text(strip=True)

        combined_text = f"{title}\n\n{body_text}".strip() if body_text else title
        if not combined_text:
            combined_text = "Untitled Reddit post without textual body."

        # ----------------------------------------------------------------------
        # 2. Hashtags / Topic Flair Extraction
        # ----------------------------------------------------------------------
        hashtags: list[str] = []
        # Flair tag
        flair_el = (
            soup.find("div", {"data-testid": "post-flair"})
            or soup.find("span", class_=lambda c: c and "flair" in c.lower())
        )
        if flair_el:
            flair_text = flair_el.get_text(strip=True)
            if flair_text:
                hashtags.append(f"#{flair_text.replace(' ', '')}")

        # In-text hashtags
        in_text_tags = re.findall(r"#\w+", combined_text)
        for t in in_text_tags:
            if t not in hashtags:
                hashtags.append(t)

        # ----------------------------------------------------------------------
        # 3. Post Timestamp Extraction
        # ----------------------------------------------------------------------
        post_timestamp: datetime | None = None
        time_el = soup.find("time")
        if time_el and time_el.get("datetime"):
            try:
                # Parse ISO timestamp
                iso_str = time_el["datetime"].replace("Z", "+00:00")
                post_timestamp = datetime.fromisoformat(iso_str)
            except Exception as e:
                logger.debug("Could not parse Reddit post datetime: %s", e)

        # ----------------------------------------------------------------------
        # 4. Public Author Information
        # ----------------------------------------------------------------------
        author_profile: UserProfile | None = None
        author_el = (
            soup.find("a", href=lambda h: h and "/user/" in h)
            or soup.find("a", {"data-testid": "post_author_link"})
            or soup.find("span", class_=lambda c: c and "author" in c.lower())
        )
        if author_el:
            raw_author = author_el.get_text(strip=True).lstrip("u/").lstrip("r/")
            if raw_author and raw_author.lower() != "deleted":
                author_profile = UserProfile(
                    username=raw_author,
                    followers=0,
                    following=0,
                )

        # ----------------------------------------------------------------------
        # 5. Media URLs Extraction
        # ----------------------------------------------------------------------
        media_list: list[Media] = []
        # Look for post image containers
        img_els = soup.find_all("img", src=lambda s: s and ("i.redd.it" in s or "preview.redd.it" in s or "external-preview" in s))
        for img in img_els[:2]:
            src = img.get("src")
            if src and src.startswith("http"):
                media_list.append(Media(url=src, media_type=MediaType.IMAGE))

        # ----------------------------------------------------------------------
        # 6. Visible Comments Extraction
        # ----------------------------------------------------------------------
        comments: list[Comment] = []
        comment_els = (
            soup.find_all("shreddit-comment")
            or soup.find_all("div", {"data-testid": "comment"})
            or soup.find_all("div", class_=lambda c: c and "entry" in c and "comment" in c)
        )

        for idx, c_el in enumerate(comment_els[:10]):
            c_text_el = (
                c_el.find("div", {"slot": "comment"})
                or c_el.find("div", {"data-testid": "comment-content"})
                or c_el.find("div", class_="md")
                or c_el
            )
            c_text = c_text_el.get_text(strip=True) if c_text_el else ""

            # Filter out empty or duplicate post text
            if c_text and c_text != combined_text and len(c_text) > 5:
                # Comment author if visible
                c_author_el = c_el.find("a", href=lambda h: h and "/user/" in h)
                c_username = c_author_el.get_text(strip=True).lstrip("u/") if c_author_el else f"user_{idx+1}"

                # Comment timestamp
                c_time_el = c_el.find("time")
                c_time = None
                if c_time_el and c_time_el.get("datetime"):
                    try:
                        c_time = datetime.fromisoformat(c_time_el["datetime"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                # Upvotes/Score if available
                score_el = c_el.find("span", id=lambda i: i and "score" in i) or c_el.find("div", class_="score")
                likes = 0
                if score_el:
                    try:
                        likes = int(re.sub(r"[^\d]", "", score_el.get_text(strip=True)) or 0)
                    except Exception:
                        pass

                # Extract emojis
                from app.modules.comment_analysis.preprocessing import extract_emojis
                emojis = extract_emojis(c_text)

                comments.append(Comment(
                    comment_id=f"reddit_c_{idx+1}",
                    author_id=c_username,
                    text=c_text,
                    timestamp=c_time,
                    likes=likes,
                    emojis=emojis,
                    emoji_count=len(emojis),
                ))

        # Build clean SocialMediaPost entity
        return SocialMediaPost(
            platform="reddit",
            text=combined_text,
            hashtags=hashtags,
            media=media_list,
            timestamp=post_timestamp,
            author=author_profile,
            comments=comments,
        )


reddit_extractor = RedditExtractor()

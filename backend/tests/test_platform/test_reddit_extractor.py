"""
Tests for Platform Extraction (Reddit Extractor).
"""

from datetime import datetime
import pytest

from app.platform.reddit_extractor import RedditExtractor, reddit_extractor
from app.schemas.domain_models import SocialMediaPost, MediaType


SAMPLE_REDDIT_HTML = """
<!DOCTYPE html>
<html>
<head><title>Breaking: Major discovery announced</title></head>
<body>
    <div class="post-container">
        <h1 data-testid="post-title">Breaking: Major scientific discovery announced today #science #space</h1>
        <div data-testid="post-flair">Research Update</div>
        <div class="meta">
            <span>Posted by <a data-testid="post_author_link" href="/user/dr_astronomer">u/dr_astronomer</a></span>
            <time datetime="2026-09-10T08:00:00Z">2 hours ago</time>
        </div>
        <div data-testid="post-rtjson-content">
            <p>Scientists have observed an unprecedented radio signal from a nearby stellar system.</p>
            <p>Peer review is ongoing and results are pending confirmation.</p>
        </div>
        <div class="media-container">
            <img src="https://i.redd.it/sample_astronomy_chart.png" alt="Signal spectrum graph" />
        </div>
    </div>

    <!-- Visible Comments Section -->
    <div class="comments-section">
        <div data-testid="comment">
            <a href="/user/astro_fan99">u/astro_fan99</a>
            <time datetime="2026-09-10T08:15:00Z">1 hour ago</time>
            <span id="score-1">42 points</span>
            <div data-testid="comment-content">This is huge if true! 🚀✨ Let's wait for peer review though.</div>
        </div>
        <div data-testid="comment">
            <a href="/user/skeptic_dave">u/skeptic_dave</a>
            <time datetime="2026-09-10T08:30:00Z">45 minutes ago</time>
            <span id="score-2">15 points</span>
            <div data-testid="comment-content">Looks like terrestrial interference, seen this happen before.</div>
        </div>
    </div>
</body>
</html>
"""

MINIMAL_REDDIT_HTML = """
<html>
<body>
    <h1>Short Question</h1>
    <div slot="text-body"><p>What do you think?</p></div>
</body>
</html>
"""

EMPTY_HTML = "   "


def test_reddit_extractor_full_post():
    """Verify complete extraction of post, tags, comments, author, and media."""
    extractor = RedditExtractor()
    post = extractor.extract_post_from_html(SAMPLE_REDDIT_HTML)

    assert isinstance(post, SocialMediaPost)
    assert post.platform == "reddit"
    assert "Breaking: Major scientific discovery announced today" in post.text
    assert "Scientists have observed an unprecedented radio signal" in post.text

    # Hashtags and flairs
    assert "#ResearchUpdate" in post.hashtags
    assert "#science" in post.hashtags
    assert "#space" in post.hashtags

    # Post timestamp
    assert post.timestamp is not None
    assert post.timestamp.year == 2026
    assert post.timestamp.hour == 8

    # Author info
    assert post.author is not None
    assert post.author.username == "dr_astronomer"

    # Media references
    assert len(post.media) == 1
    assert post.media[0].media_type == MediaType.IMAGE
    assert "sample_astronomy_chart.png" in str(post.media[0].url)

    # Comments
    assert len(post.comments) == 2
    c1 = post.comments[0]
    assert c1.author_id == "astro_fan99"
    assert "This is huge if true!" in c1.text
    assert "🚀" in c1.emojis or len(c1.emojis) >= 1
    assert c1.likes == 42

    c2 = post.comments[1]
    assert c2.author_id == "skeptic_dave"
    assert "Looks like terrestrial interference" in c2.text
    assert c2.likes == 15


def test_reddit_extractor_minimal_post():
    """Verify graceful handling when optional elements are missing."""
    post = reddit_extractor.extract_post_from_html(MINIMAL_REDDIT_HTML)

    assert post.platform == "reddit"
    assert "Short Question" in post.text
    assert "What do you think?" in post.text
    assert post.hashtags == []
    assert post.comments == []
    assert post.media == []
    assert post.timestamp is None
    assert post.author is None


def test_reddit_extractor_empty_content():
    """Verify extraction does not crash on empty input."""
    post = reddit_extractor.extract_post_from_html(EMPTY_HTML)

    assert post.platform == "reddit"
    assert post.text == "No content provided."
    assert post.comments == []
    assert post.media == []

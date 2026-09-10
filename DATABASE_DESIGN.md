# Social Guard: Relational Database Schema & Architecture

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Document:** DATABASE_DESIGN.md  
**ORM:** SQLAlchemy 2.0 (Asyncio)  
**Supported Databases:** PostgreSQL (Production / Development), SQLite (Fallback & Test Harness)

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    USERS ||--o{ POSTS : "authors"
    USERS ||--o{ COMMENTS : "writes"
    POSTS ||--o{ COMMENTS : "contains"
    POSTS ||--o{ EVIDENCE : "extracted_from"
    POSTS ||--o{ ANALYSIS_RESULTS : "evaluated_in"

    USERS {
        int id PK
        string username UK
        int account_age_days
        int followers
        int following
        float posts_per_day
        float comments_per_day
        float engagement_rate
        float duplicate_content_ratio
        float hashtag_repetition_rate
        json raw_behaviour_metadata
        datetime created_at
    }

    POSTS {
        int id PK
        string platform_post_id
        string platform
        text text
        json hashtags
        json media_urls
        datetime post_timestamp
        int author_id FK
        datetime created_at
    }

    COMMENTS {
        int id PK
        int post_id FK
        int author_id FK
        string comment_platform_id
        text text
        int likes
        json emojis
        int emoji_count
        datetime comment_timestamp
        datetime created_at
    }

    EVIDENCE {
        int id PK
        int post_id FK
        text claim_text
        string status
        string publisher
        string publisher_url
        string raw_rating
        float normalized_truth_score
        float source_credibility_weight
        text ocr_extracted_text
        datetime created_at
    }

    ANALYSIS_RESULTS {
        int id PK
        string request_id UK
        int post_id FK
        float final_score
        string classification
        float ai_generated_probability
        string confidence_level
        float comment_score
        float evidence_score
        float behaviour_score
        float similarity_score
        text explanation_summary
        json positive_factors
        json negative_factors
        json module_breakdowns
        json flags
        datetime created_at
    }
```

---

## 2. Table Specifications & Indexes

### 2.1 `users`
Stores public aggregate account metadata and behavioral features.
- **Indexes:** `ix_users_username` (Unique), `idx_users_username_followers` (Composite).

### 2.2 `posts`
Stores verified post content, attached media URLs, and platform source.
- **Indexes:** `ix_posts_platform_post_id`, `idx_posts_platform_timestamp` (Composite).

### 2.3 `comments`
Stores discussion thread comments, timestamps, and emoji arrays for NLP and temporal burst scoring.
- **Indexes:** `ix_comments_post_id`, `ix_comments_author_id`.

### 2.4 `evidence`
Stores fact-check claims, review ratings from IFCN organizations, and source weights.
- **Indexes:** `ix_evidence_post_id`, `ix_evidence_publisher`, `ix_evidence_claim_text`.

### 2.5 `analysis_results`
Stores the complete Explainable AI verification session, factor rankings, and breakdown metrics.
- **Indexes:** `ix_analysis_results_request_id` (Unique), `idx_analysis_classification_score` (Composite).

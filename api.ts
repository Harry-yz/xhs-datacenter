const DEFAULT_BASE_URL = "https://api.datacenter.photog.art/api/v1";

export const BASE_URL =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL
    ? process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")
    : DEFAULT_BASE_URL;

export type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

export type ApiListData<T> = {
  items: T[];
};

export type Pagination = {
  total: number;
  page: number;
  size: number;
  has_more: boolean;
};

export type PaginatedData<T> = {
  list: T[];
  pagination: Pagination;
};

export type BeautyCategoryRow = {
  category_name: string;
  total_posts: number;
};

export type BeautyTrendRow = {
  stat_date: string;
  category_name: string;
  total_posts: number;
};

export type BeautyBrandRow = {
  brand_name: string;
  mention_count: number;
  creator_count?: number;
  like_total?: number;
  comment_total?: number;
  collection_total?: number;
};

export type BeautyPostRow = {
  post_id: string;
  platform: string;
  publish_time: string | null;
  post_url: string | null;
  title: string | null;
  content: string;
  media_type: string | null;
  duration_seconds: number | null;
  tags: string[];
  media_urls: string[];
  cover_image_url: string | null;
  author_id: string | null;
  author_nickname: string | null;
  author_fans_count: number;
  category_name: string | null;
  like_count: number;
  collection_count: number;
  comment_count: number;
  share_count: number;
  read_count: number;
  stat_count: number;
  exp_count: number;
  interaction_total: number;
  ai_category?: string;
  ai_brand?: string;
  ai_sentiment?: "positive" | "negative" | "neutral";
  ai_post_tags?: string[];
  ai_extracted_pain_points?: string[];
  ai_extracted_selling_points?: string[];
  ai_extracted_scenarios?: string[];
};

export type BeautyTaxonomyCategory = {
  category_name: string;
  sort_no: number;
  keywords: string[];
  suggested_keywords: string[];
};

export type BeautyTaxonomyResponse = {
  categories: BeautyTaxonomyCategory[];
  suggested_groups: Array<{
    group_name: string;
    keywords: string[];
  }>;
};

export type NoteListRow = {
  note_id: string;
  title: string | null;
  author_id: string | null;
  author_nickname: string | null;
  read_count: number;
  like_count: number;
  comment_count: number;
  collection_count: number;
  share_count: number;
  post_url: string;
  publish_time: string | null;
  tags: string[];
};

export type NoteDetailRow = {
  note_id: string;
  title: string | null;
  content: string | null;
  post_url: string;
  publish_time: string | null;
  media_type: string | null;
  duration_seconds: number | null;
  tags: string[];
  media_urls: string[];
  cover_image_url: string | null;
  read_count: number;
  like_count: number;
  comment_count: number;
  collection_count: number;
  share_count: number;
  stat_count: number;
  exp_count: number;
  author_id: string | null;
  author_nickname: string | null;
  author_fans_count: number;
};

export type XhsNoteCenterRow = {
  platform: string;
  search_keyword: string | null;
  search_rank: number | null;
  search_type: string | null;
  note_id: string;
  post_url: string | null;
  publish_time: string | null;
  title: string | null;
  content: string | null;
  media_type: string | null;
  tags: string[];
  media_urls: string[];
  cover_image_url: string | null;
  like_count: number;
  collection_count: number;
  comment_count: number;
  share_count: number;
  read_count: number;
  author_id: string | null;
  nickname: string | null;
  follower_count: number | null;
  verified_type: string | null;
  video_cpm: number | null;
  picture_cpm: number | null;
  total_notes: number | null;
  like_coll_total: number | null;
  crawl_time: string | null;
};

export type XhsCommentCenterRow = {
  parent_note_id: string;
  comment_text: string | null;
  comment_sentiment: string | null;
  commenter_id: string | null;
  commenter_nickname: string | null;
  comment_likes: number | null;
  comment_time: string | null;
  crawl_time: string | null;
};

export type XhsAnchorCenterRow = {
  author_id: string;
  nickname: string | null;
  follower_count: number | null;
  verified_type: string | null;
  video_cpm: number | null;
  picture_cpm: number | null;
  total_notes: number | null;
  like_coll_total: number | null;
  crawl_time: string | null;
  anchor_link: string | null;
  red_id: string | null;
  contact: string | null;
};

export type XhsBrandCenterRow = {
  brand_id: string;
  brand_name: string;
  note_count: number;
  creator_count: number;
  like_total: number;
  collection_total: number;
  comment_total: number;
  read_total: number;
  max_like_count: number;
  latest_publish_time: string | null;
  crawl_time: string | null;
};

export type KOLMatchRow = {
  kol_avatar: string;
  kol_nickname: string;
  kol_followers: number;
  kol_cpe_price: number;
  ai_match_score: number;
  擅长方向: string;
};

export type AIBriefs = {
  选题一: { 标题: string; 推荐理由: string };
  选题二: { 标题: string; 推荐理由: string };
  选题三: { 标题: string; 推荐理由: string };
};

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

async function requestData<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
    ...init,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }

  const json: ApiEnvelope<T> = await res.json();

  if (json.code !== 200) {
    throw new Error(`API ${path} business error: ${json.message}`);
  }

  return json.data;
}

async function requestItems<T>(path: string, init?: RequestInit): Promise<T[]> {
  const data = await requestData<ApiListData<T>>(path, init);
  return data.items;
}

export async function getBeautyCategories(): Promise<BeautyCategoryRow[]> {
  return requestItems<BeautyCategoryRow>("/dashboard/beauty/categories");
}

export async function getBeautyTrend(days = 30): Promise<BeautyTrendRow[]> {
  return requestItems<BeautyTrendRow>(`/dashboard/beauty/trend${buildQuery({ days })}`);
}

export async function getBeautyBrands(): Promise<BeautyBrandRow[]> {
  return requestItems<BeautyBrandRow>("/dashboard/beauty/brands");
}

export async function getBeautyPosts(params?: {
  limit?: number;
  minLike?: number;
  keyword?: string;
  brandName?: string;
}): Promise<BeautyPostRow[]> {
  return requestItems<BeautyPostRow>(
    `/dashboard/beauty/posts${buildQuery({
      limit: params?.limit ?? 20,
      min_like: params?.minLike ?? 100,
      keyword: params?.keyword,
      brand_name: params?.brandName,
    })}`,
  );
}

export async function getBeautyTaxonomy(): Promise<BeautyTaxonomyResponse> {
  return requestData<BeautyTaxonomyResponse>("/query/beauty-taxonomy");
}

export async function getCategoryTags(limit = 100): Promise<Array<{ name: string; count: number }>> {
  return requestData<Array<{ name: string; count: number }>>(
    `/query/categories${buildQuery({ limit })}`,
  );
}

export async function getNotes(params: {
  category: string;
  page?: number;
  size?: number;
  sortBy?: "publish_time" | "read_count" | "like_count" | "comment_count";
  order?: "asc" | "desc";
}): Promise<PaginatedData<NoteListRow>> {
  return requestData<PaginatedData<NoteListRow>>(
    `/query/notes${buildQuery({
      category: params.category,
      page: params.page ?? 1,
      size: params.size ?? 20,
      sort_by: params.sortBy ?? "publish_time",
      order: params.order ?? "desc",
    })}`,
  );
}

export async function getNoteDetail(noteId: string): Promise<NoteDetailRow> {
  return requestData<NoteDetailRow>(`/query/notes/${encodeURIComponent(noteId)}`);
}

export async function getXhsNoteCenter(params?: {
  limit?: number;
  minLike?: number;
  brandName?: string;
}): Promise<XhsNoteCenterRow[]> {
  return requestItems<XhsNoteCenterRow>(
    `/query/xhs-note-center${buildQuery({
      limit: params?.limit ?? 100,
      min_like: params?.minLike ?? 0,
      brand_name: params?.brandName,
    })}`,
  );
}

export async function getXhsCommentCenter(params?: {
  limit?: number;
  noteId?: string;
}): Promise<XhsCommentCenterRow[]> {
  return requestItems<XhsCommentCenterRow>(
    `/query/xhs-comment-center${buildQuery({
      limit: params?.limit ?? 100,
      note_id: params?.noteId,
    })}`,
  );
}

export async function getXhsAnchorCenter(limit = 100): Promise<XhsAnchorCenterRow[]> {
  return requestItems<XhsAnchorCenterRow>(
    `/query/xhs-anchor-center${buildQuery({ limit })}`,
  );
}

export async function getXhsBrandCenter(limit = 100): Promise<XhsBrandCenterRow[]> {
  return requestItems<XhsBrandCenterRow>(
    `/query/xhs-brand-center${buildQuery({ limit })}`,
  );
}

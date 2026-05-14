const fallbackItems = [
  {
    id: "sample-toxoplasma-rhoptry",
    title: "Rhoptry and dense granule effectors in Toxoplasma host-cell remodeling",
    url: "https://pubmed.ncbi.nlm.nih.gov/?term=Toxoplasma+gondii+rhoptry+dense+granule",
    source: "PubMed search",
    tag: "Toxoplasma",
    type: "PubMed",
    editor: "PubMed",
    ageHours: 24,
    score: 120,
    journal: "Example query",
    pubDate: "sample",
    authors: ["Query template"],
    why: "示例条目：运行抓取脚本后，这里会替换成真实 PubMed 文献摘要。",
  },
  {
    id: "sample-plasmodium-resistance",
    title: "Plasmodium falciparum drug resistance surveillance and parasite biology",
    url: "https://pubmed.ncbi.nlm.nih.gov/?term=Plasmodium+falciparum+drug+resistance",
    source: "PubMed search",
    tag: "Plasmodium",
    type: "PubMed",
    editor: "PubMed",
    ageHours: 30,
    score: 108,
    journal: "Example query",
    pubDate: "sample",
    authors: ["Query template"],
    why: "示例条目：用于页面预览。真实数据来自 scripts/fetch_research.py。",
  },
];

const STORAGE_KEYS = {
  votes: "parasiteSignalVotes",
  saved: "parasiteSignalSaved",
  discussions: "parasiteSignalDiscussions",
};

const loadedResearchItems =
  Array.isArray(window.researchItems) && window.researchItems.length > 0
    ? window.researchItems
    : fallbackItems;

const state = {
  items: loadedResearchItems.map(normalizeItem),
  activeTag: "All",
  sort: "hot",
  query: "",
  savedOnly: false,
  votes: readStoredObject(STORAGE_KEYS.votes),
  saved: readStoredObject(STORAGE_KEYS.saved),
  discussions: readStoredObject(STORAGE_KEYS.discussions),
};

const feedList = document.querySelector("#feedList");
const tagList = document.querySelector("#tagList");
const emptyState = document.querySelector("#emptyState");
const searchInput = document.querySelector("#feedSearch");
const submitDialog = document.querySelector("#submitDialog");
const submitForm = document.querySelector("#submitForm");
const dataFreshness = document.querySelector("#dataFreshness");
const feedStats = document.querySelector("#feedStats");
const savedOnlyToggle = document.querySelector("#savedOnlyToggle");
const exportSavedButton = document.querySelector("#exportSaved");
const filterHint = document.querySelector("#filterHint");
const filterHintText = document.querySelector("#filterHintText");
const clearFiltersButton = document.querySelector("#clearFilters");

function readStoredObject(key) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function normalizeItem(item) {
  const topics = Array.isArray(item.topics)
    ? item.topics
    : String(item.tag || item.topic || "Research")
        .split("/")
        .map((topic) => topic.trim())
        .filter(Boolean);

  const normalized = {
    id: item.id || `item-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    title: item.title || "Untitled",
    url: item.url || "#",
    source: item.source || "PubMed",
    tag: topics[0] || "Research",
    topics: topics.length > 0 ? topics : ["Research"],
    type: item.type || "PubMed",
    editor: item.editor || item.source || "PubMed",
    ageHours: Number.isFinite(Number(item.ageHours)) ? Number(item.ageHours) : 999,
    score: Number.isFinite(Number(item.score)) ? Number(item.score) : 1,
    journal: item.journal || "",
    pubDate: item.pubDate || "",
    authors: Array.isArray(item.authors) ? item.authors : [],
    pmid: item.pmid || "",
    doi: item.doi || "",
    why: item.why || item.abstract || "No abstract available.",
  };

  return {
    ...normalized,
    stableId: getStableItemId(normalized),
  };
}

function normalizeKey(value) {
  return String(value || "")
    .normalize("NFKC")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function normalizeUrl(value) {
  const raw = String(value || "").trim();
  if (!raw || raw === "#") return "";

  try {
    const parsed = new URL(raw, window.location.href);
    parsed.hash = "";
    return parsed.href.replace(/\/$/, "").toLowerCase();
  } catch {
    return raw.replace(/\/$/, "").toLowerCase();
  }
}

function getStableItemId(item) {
  const pmid = normalizeKey(item.pmid);
  if (pmid) return `pmid:${pmid}`;

  const doi = normalizeKey(item.doi);
  if (doi) return `doi:${doi}`;

  const url = normalizeUrl(item.url);
  if (url) return `url:${url}`;

  const titleDate = normalizeKey(`${item.title || "untitled"}|${item.pubDate || "undated"}`);
  return `title:${titleDate || "untitled"}`;
}

function migrateSavedState() {
  let changed = false;

  state.items.forEach((item) => {
    if (item.id && item.id !== item.stableId && state.saved[item.id]) {
      state.saved[item.stableId] = true;
      delete state.saved[item.id];
      changed = true;
    }
  });

  if (changed) persist();
}

function persist() {
  localStorage.setItem(STORAGE_KEYS.votes, JSON.stringify(state.votes));
  localStorage.setItem(STORAGE_KEYS.saved, JSON.stringify(state.saved));
  localStorage.setItem(STORAGE_KEYS.discussions, JSON.stringify(state.discussions));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function cleanMarkdownText(value) {
  return String(value || "")
    .replace(/\r?\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function escapeMarkdownHeading(value) {
  return cleanMarkdownText(value).replace(/^#+\s*/, "").replaceAll("|", "\\|") || "Untitled";
}

function escapeYamlString(value) {
  return `"${cleanMarkdownText(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"')}"`;
}

function getScore(item) {
  return item.score + (state.votes[item.id] || 0);
}

function isItemSaved(item) {
  return Boolean(state.saved[item.stableId] || (item.id && state.saved[item.id]));
}

function toggleSaved(item) {
  if (isItemSaved(item)) {
    delete state.saved[item.stableId];
    if (item.id) delete state.saved[item.id];
  } else {
    state.saved[item.stableId] = true;
    if (item.id && item.id !== item.stableId) delete state.saved[item.id];
  }

  persist();
}

function getSavedItems() {
  return sortItems(state.items.filter(isItemSaved));
}

function getDiscussionItems(item) {
  const comments = state.discussions[item.stableId];
  return Array.isArray(comments) ? comments : [];
}

function getDiscussionCount(item) {
  return getDiscussionItems(item).length;
}

function makeCommentId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `comment-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function addDiscussionItem(item, body) {
  const text = cleanMarkdownText(body);
  if (!text) return;

  const now = new Date().toISOString();
  const comments = getDiscussionItems(item);
  state.discussions[item.stableId] = [
    ...comments,
    {
      id: makeCommentId(),
      body: text,
      createdAt: now,
      updatedAt: now,
    },
  ];
  persist();
}

function editDiscussionItem(item, commentId, body) {
  const text = cleanMarkdownText(body);
  if (!text) return;

  const comments = getDiscussionItems(item);
  state.discussions[item.stableId] = comments.map((comment) =>
    comment.id === commentId
      ? { ...comment, body: text, updatedAt: new Date().toISOString() }
      : comment,
  );
  persist();
}

function deleteDiscussionItem(item, commentId) {
  const comments = getDiscussionItems(item).filter((comment) => comment.id !== commentId);
  if (comments.length > 0) {
    state.discussions[item.stableId] = comments;
  } else {
    delete state.discussions[item.stableId];
  }
  persist();
}

function formatAge(item) {
  if (item.ageHours < 24) return `${Math.max(0, Math.round(item.ageHours))}h`;
  if (item.ageHours < 24 * 14) return `${Math.round(item.ageHours / 24)}d`;
  return item.pubDate || "unknown date";
}

function formatLocalDate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getTags() {
  const counts = state.items.reduce(
    (acc, item) => {
      acc.All += 1;
      item.topics.forEach((topic) => {
        acc[topic] = (acc[topic] || 0) + 1;
      });
      return acc;
    },
    { All: 0 },
  );

  return Object.entries(counts);
}

function matchesQuery(item, query) {
  if (!query) return true;
  const comments = getDiscussionItems(item).map((comment) => comment.body);

  return [
    item.title,
    item.source,
    item.tag,
    item.topics.join(" "),
    item.type,
    item.why,
    item.journal,
    item.pubDate,
    item.pmid,
    item.doi,
    item.authors.join(" "),
    comments.join(" "),
  ]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function sortItems(items) {
  return [...items].sort((a, b) => {
    if (state.sort === "recent") return a.ageHours - b.ageHours;
    if (state.sort === "top") return getScore(b) - getScore(a);
    return getScore(b) / Math.sqrt(b.ageHours + 2) - getScore(a) / Math.sqrt(a.ageHours + 2);
  });
}

function filteredItems() {
  const query = state.query.trim().toLowerCase();

  return sortItems(
    state.items
      .filter((item) => state.activeTag === "All" || item.topics.includes(state.activeTag))
      .filter((item) => !state.savedOnly || isItemSaved(item))
      .filter((item) => matchesQuery(item, query)),
  );
}

function hasActiveFilters() {
  return state.activeTag !== "All" || Boolean(state.query.trim()) || state.savedOnly;
}

function renderTags() {
  tagList.innerHTML = getTags()
    .map(([tag, count]) => {
      const active = tag === state.activeTag ? " active" : "";
      const label = tag === "All" ? "全部" : tag;
      return `
        <button class="tag-pill${active}" type="button" data-tag="${escapeHtml(tag)}">
          <span>${escapeHtml(label)}</span>
          <span>${count}</span>
        </button>
      `;
    })
    .join("");
}

function renderFreshness() {
  const updated = window.researchLastUpdated;
  const count = state.items.length;

  if (!updated) {
    dataFreshness.textContent = `当前显示 ${count} 条示例/本地条目。`;
    return;
  }

  dataFreshness.textContent = `数据更新：${updated} · ${count} 条文献`;
}

function renderControls(items, savedCount) {
  savedOnlyToggle.checked = state.savedOnly;
  const discussionCount = state.items.reduce((total, item) => total + getDiscussionCount(item), 0);

  if (state.savedOnly) {
    feedStats.textContent = `显示 ${items.length}/${savedCount} 篇收藏 · 讨论 ${discussionCount} 条`;
  } else {
    feedStats.textContent = `显示 ${items.length}/${state.items.length} 篇 · 收藏 ${savedCount} 篇 · 讨论 ${discussionCount} 条`;
  }

  exportSavedButton.disabled = savedCount === 0;
  exportSavedButton.textContent =
    savedCount > 0 ? `导出收藏 ${savedCount} 篇` : "暂无收藏可导出";
}

function renderFilterHint(items, savedCount) {
  if (items.length > 0 || !hasActiveFilters()) {
    filterHint.hidden = true;
    return;
  }

  filterHint.hidden = false;
  if (state.savedOnly && savedCount > 0) {
    filterHintText.textContent = "当前筛选条件下无收藏，可清除筛选。";
  } else if (state.savedOnly) {
    filterHintText.textContent = "还没有收藏文献，点击星标后可导出 Markdown。";
  } else {
    filterHintText.textContent = "没有匹配的文献，可清除筛选。";
  }
}

function formatCommentTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

function renderDiscussionThread(item) {
  const comments = getDiscussionItems(item);
  const commentHtml = comments
    .map(
      (comment) => `
        <div class="comment-item">
          <div class="comment-avatar" aria-hidden="true">你</div>
          <div class="comment-body">
            <div class="comment-meta">
              <strong>本地观点</strong>
              <span>${escapeHtml(formatCommentTime(comment.updatedAt || comment.createdAt))}</span>
            </div>
            <p>${escapeHtml(comment.body)}</p>
            <div class="comment-actions">
              <button class="link-button comment-edit" type="button" data-item-id="${escapeHtml(item.stableId)}" data-comment-id="${escapeHtml(comment.id)}">编辑</button>
              <button class="link-button comment-delete" type="button" data-item-id="${escapeHtml(item.stableId)}" data-comment-id="${escapeHtml(comment.id)}">删除</button>
            </div>
          </div>
        </div>
      `,
    )
    .join("");

  return `
    <section class="thread-panel" aria-label="本地讨论">
      <div class="thread-head">
        <span>讨论 ${comments.length}</span>
        <span>${comments.length > 0 ? "本地保存" : "等待观点"}</span>
      </div>
      <div class="comment-list">
        ${commentHtml || '<p class="thread-empty">还没有观点。</p>'}
      </div>
      <form class="comment-form" data-item-id="${escapeHtml(item.stableId)}">
        <label class="sr-only" for="comment-${escapeHtml(item.stableId)}">写观点</label>
        <textarea id="comment-${escapeHtml(item.stableId)}" name="comment" rows="2" maxlength="800" placeholder="写下判断、疑问或后续追踪意见"></textarea>
        <button class="button comment-submit" type="submit">发表</button>
      </form>
    </section>
  `;
}

function renderFeed() {
  const items = filteredItems();
  const savedCount = getSavedItems().length;
  renderControls(items, savedCount);
  renderFilterHint(items, savedCount);

  emptyState.hidden = items.length > 0;
  if (!emptyState.hidden) {
    emptyState.textContent =
      state.savedOnly && savedCount === 0
        ? "还没有收藏文献。"
        : "没有匹配的文献。";
  }

  feedList.innerHTML = items
    .map((item, index) => {
      const score = getScore(item);
      const saved = isItemSaved(item) ? " active" : "";
      const voted = state.votes[item.id] ? " active" : "";
      const discussionCount = getDiscussionCount(item);
      const primaryTopic = item.topics[0] || item.tag;
      const topicLabel = item.topics.join(" / ");
      const tone =
        primaryTopic === "Plasmodium" || primaryTopic === "Malaria parasite"
          ? " amber"
          : primaryTopic === "Toxoplasma"
            ? " indigo"
            : "";
      const authors = item.authors.slice(0, 3).join(", ");
      const meta = [
        `<span class="badge${tone}">${escapeHtml(topicLabel)}</span>`,
        item.pubDate ? `<span>${escapeHtml(item.pubDate)}</span>` : "",
        item.journal ? `<span>${escapeHtml(item.journal)}</span>` : "",
        authors ? `<span>${escapeHtml(authors)}</span>` : "",
        item.pmid ? `<span>PMID ${escapeHtml(item.pmid)}</span>` : "",
        `<span>${discussionCount} 条讨论</span>`,
        `<span>${escapeHtml(formatAge(item))}</span>`,
      ]
        .filter(Boolean)
        .join("");

      return `
        <li class="feed-item">
          <div class="score-control" aria-label="rank and score">
            <span class="rank-number">${index + 1}.</span>
            <button class="icon-button vote-button${voted}" type="button" title="标记重点" aria-label="标记重点 ${escapeHtml(item.title)}" data-id="${escapeHtml(item.id)}">▲</button>
            <span class="score">${score}</span>
          </div>

          <article class="item-main">
            <div class="item-topline">
              <span class="badge${tone}">${escapeHtml(topicLabel)}</span>
              <span>${escapeHtml(item.source)}</span>
            </div>
            <h3 class="item-heading">
              <a class="item-title" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
            </h3>
            <p class="why">${escapeHtml(item.why)}</p>
            <div class="meta">${meta}</div>
            ${renderDiscussionThread(item)}
          </article>

          <button class="icon-button save-button${saved}" type="button" title="收藏到日报导出" aria-label="收藏到日报导出 ${escapeHtml(item.title)}" data-id="${escapeHtml(item.stableId)}">★</button>
        </li>
      `;
    })
    .join("");
}

function render() {
  renderFreshness();
  renderTags();
  renderFeed();
}

function findItemBySaveId(id) {
  return state.items.find((item) => item.stableId === id || item.id === id);
}

function groupByTopic(items) {
  const groups = new Map();
  items.forEach((item) => {
    const topic = item.topics[0] || item.tag || "Research";
    if (!groups.has(topic)) groups.set(topic, []);
    groups.get(topic).push(item);
  });

  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function tagToYaml(value) {
  return (
    normalizeKey(value)
      .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-")
      .replace(/^-+|-+$/g, "") || "research"
  );
}

function buildMarkdown(items) {
  const exportDate = formatLocalDate();
  const exportedAt = new Date().toLocaleString();
  const dataUpdated = window.researchLastUpdated || "unknown";
  const yamlTags = [
    "parasite-signal",
    "literature",
    ...new Set(items.flatMap((item) => item.topics.map(tagToYaml))),
  ];

  const lines = [
    "---",
    `title: ${escapeYamlString("Parasite Signal Daily Research Notes")}`,
    `date: ${exportDate}`,
    "source: ai-feed-page",
    "type: literature-digest",
    `count: ${items.length}`,
    "tags:",
    ...yamlTags.map((tag) => `  - ${tag}`),
    "---",
    "",
    "# Parasite Signal Daily Research Notes",
    "",
    `- Data updated: ${cleanMarkdownText(dataUpdated) || "unknown"}`,
    `- Exported at: ${cleanMarkdownText(exportedAt)}`,
    `- Saved items: ${items.length}`,
    "",
  ];

  groupByTopic(items).forEach(([topic, groupItems]) => {
    lines.push(`## ${escapeMarkdownHeading(topic)}`, "");

    groupItems.forEach((item) => {
      const topicLabel = item.topics.join(" / ") || item.tag || "Research";
      const urlLabel = item.pmid ? "PubMed" : "URL";
      const comments = getDiscussionItems(item);
      lines.push(
        `### ${escapeMarkdownHeading(item.title)}`,
        "",
        `- PMID: ${cleanMarkdownText(item.pmid) || "not available"}`,
        `- DOI: ${cleanMarkdownText(item.doi) || "not available"}`,
        `- Journal: ${cleanMarkdownText(item.journal) || "not available"}`,
        `- Date: ${cleanMarkdownText(item.pubDate) || "not available"}`,
        `- Authors: ${cleanMarkdownText(item.authors.join(", ")) || "not available"}`,
        `- ${urlLabel}: ${cleanMarkdownText(item.url) || "not available"}`,
        `- Topic: ${cleanMarkdownText(topicLabel)}`,
        "- Why it matters: 待补充",
        `- Abstract excerpt: ${cleanMarkdownText(item.why) || "not available"}`,
        "",
        "Notes:",
        "",
      );

      if (comments.length > 0) {
        lines.push("Local discussion:", "");
        comments.forEach((comment) => {
          lines.push(`- ${cleanMarkdownText(comment.body)}`);
        });
        lines.push("");
      }
    });
  });

  return `${lines.join("\n").trim()}\n`;
}

function downloadMarkdown() {
  const items = getSavedItems();
  if (items.length === 0) return;

  const date = formatLocalDate();
  const filename = `parasite-signal-saved-${date}-${items.length}-items.md`;
  const blob = new Blob([buildMarkdown(items)], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function clearFilters() {
  state.activeTag = "All";
  state.query = "";
  state.savedOnly = false;
  searchInput.value = "";
  render();
}

document.addEventListener("click", (event) => {
  const tagButton = event.target.closest("[data-tag]");
  if (tagButton) {
    state.activeTag = tagButton.dataset.tag;
    render();
    return;
  }

  const sortButton = event.target.closest("[data-sort]");
  if (sortButton) {
    state.sort = sortButton.dataset.sort;
    document.querySelectorAll("[data-sort]").forEach((button) => {
      button.classList.toggle("active", button === sortButton);
    });
    renderFeed();
    return;
  }

  const voteButton = event.target.closest(".vote-button");
  if (voteButton) {
    const id = voteButton.dataset.id;
    state.votes[id] = state.votes[id] ? 0 : 1;
    persist();
    renderFeed();
    return;
  }

  const saveButton = event.target.closest(".save-button");
  if (saveButton) {
    const item = findItemBySaveId(saveButton.dataset.id);
    if (!item) return;
    toggleSaved(item);
    render();
    return;
  }

  const editButton = event.target.closest(".comment-edit");
  if (editButton) {
    const item = findItemBySaveId(editButton.dataset.itemId);
    if (!item) return;
    const comment = getDiscussionItems(item).find(
      (entry) => entry.id === editButton.dataset.commentId,
    );
    if (!comment) return;
    const nextBody = window.prompt("编辑观点", comment.body);
    if (nextBody === null) return;
    editDiscussionItem(item, comment.id, nextBody);
    renderFeed();
    return;
  }

  const deleteButton = event.target.closest(".comment-delete");
  if (deleteButton) {
    const item = findItemBySaveId(deleteButton.dataset.itemId);
    if (!item) return;
    if (!window.confirm("删除这条观点？")) return;
    deleteDiscussionItem(item, deleteButton.dataset.commentId);
    renderFeed();
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest(".comment-form");
  if (!form) return;

  event.preventDefault();
  const item = findItemBySaveId(form.dataset.itemId);
  const textarea = form.querySelector("textarea");
  if (!item || !textarea) return;

  addDiscussionItem(item, textarea.value);
  textarea.value = "";
  render();
});

searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  renderFeed();
});

savedOnlyToggle.addEventListener("change", (event) => {
  state.savedOnly = event.target.checked;
  renderFeed();
});

exportSavedButton.addEventListener("click", downloadMarkdown);
clearFiltersButton.addEventListener("click", clearFilters);

document.querySelector("#openSubmit").addEventListener("click", () => {
  submitDialog.showModal();
});

submitForm.addEventListener("submit", (event) => {
  if (event.submitter?.value !== "submit") return;

  event.preventDefault();
  const formData = new FormData(submitForm);
  const title = String(formData.get("title") || "").trim();
  const url = String(formData.get("url") || "").trim();
  const tag = String(formData.get("tag") || "Research");

  if (!title || !url) return;

  state.items.unshift(
    normalizeItem({
      id: `submitted-${Date.now()}`,
      title,
      url,
      source: new URL(url).hostname.replace(/^www\./, ""),
      tag,
      topics: [tag],
      type: "submitted",
      editor: "You",
      ageHours: 0,
      score: 1,
      journal: "",
      pubDate: formatLocalDate(),
      authors: [],
      pmid: "",
      doi: "",
      why: "手动添加的条目。",
    }),
  );

  state.activeTag = "All";
  state.savedOnly = false;
  submitForm.reset();
  submitDialog.close();
  render();
});

migrateSavedState();
render();

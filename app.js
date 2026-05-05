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

const loadedResearchItems =
  Array.isArray(window.researchItems) && window.researchItems.length > 0
    ? window.researchItems
    : fallbackItems;

const state = {
  items: loadedResearchItems.map(normalizeItem),
  activeTag: "All",
  sort: "hot",
  query: "",
  votes: JSON.parse(localStorage.getItem("parasiteSignalVotes") || "{}"),
  saved: JSON.parse(localStorage.getItem("parasiteSignalSaved") || "{}"),
};

const feedList = document.querySelector("#feedList");
const tagList = document.querySelector("#tagList");
const emptyState = document.querySelector("#emptyState");
const searchInput = document.querySelector("#feedSearch");
const submitDialog = document.querySelector("#submitDialog");
const submitForm = document.querySelector("#submitForm");
const dataFreshness = document.querySelector("#dataFreshness");

function normalizeItem(item) {
  const topics = Array.isArray(item.topics)
    ? item.topics
    : String(item.tag || item.topic || "Research")
        .split("/")
        .map((topic) => topic.trim())
        .filter(Boolean);

  return {
    id: item.id || `item-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    title: item.title || "Untitled",
    url: item.url || "#",
    source: item.source || "PubMed",
    tag: topics[0] || "Research",
    topics,
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
}

function persist() {
  localStorage.setItem("parasiteSignalVotes", JSON.stringify(state.votes));
  localStorage.setItem("parasiteSignalSaved", JSON.stringify(state.saved));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getScore(item) {
  return item.score + (state.votes[item.id] || 0);
}

function formatAge(item) {
  if (item.ageHours < 24) return `${Math.max(0, Math.round(item.ageHours))}h`;
  if (item.ageHours < 24 * 14) return `${Math.round(item.ageHours / 24)}d`;
  return item.pubDate || "unknown date";
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

function filteredItems() {
  const query = state.query.trim().toLowerCase();

  return state.items
    .filter((item) => state.activeTag === "All" || item.topics.includes(state.activeTag))
    .filter((item) => {
      if (!query) return true;
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
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    })
    .sort((a, b) => {
      if (state.sort === "recent") return a.ageHours - b.ageHours;
      if (state.sort === "top") return getScore(b) - getScore(a);
      return getScore(b) / Math.sqrt(b.ageHours + 2) - getScore(a) / Math.sqrt(a.ageHours + 2);
    });
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

function renderFeed() {
  const items = filteredItems();
  emptyState.hidden = items.length > 0;

  feedList.innerHTML = items
    .map((item) => {
      const score = getScore(item);
      const saved = state.saved[item.id] ? " active" : "";
      const voted = state.votes[item.id] ? " active" : "";
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
        `<span>${escapeHtml(formatAge(item))}</span>`,
      ]
        .filter(Boolean)
        .join("");

      return `
        <li class="feed-item">
          <div class="score-control">
            <button class="icon-button vote-button${voted}" type="button" title="标记重点" aria-label="标记重点 ${escapeHtml(item.title)}" data-id="${escapeHtml(item.id)}">▲</button>
            <span class="score">${score}</span>
          </div>

          <article class="item-main">
            <a class="item-title" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
            <span class="source">${escapeHtml(item.source)}</span>
            <p class="why">${escapeHtml(item.why)}</p>
            <div class="meta">${meta}</div>
          </article>

          <button class="icon-button save-button${saved}" type="button" title="收藏" aria-label="收藏 ${escapeHtml(item.title)}" data-id="${escapeHtml(item.id)}">★</button>
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
    const id = saveButton.dataset.id;
    state.saved[id] = !state.saved[id];
    persist();
    renderFeed();
  }
});

searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  renderFeed();
});

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

  state.items.unshift({
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
    pubDate: new Date().toISOString().slice(0, 10),
    authors: [],
    pmid: "",
    doi: "",
    why: "手动添加的条目。",
  });

  state.activeTag = "All";
  submitForm.reset();
  submitDialog.close();
  render();
});

render();

import fs from "fs";
import { execSync } from "child_process";
import story from "manga-lib";

// ==== CẤU HÌNH ====
const START_PAGE = 4;
const END_PAGE = 14;
const STORIES_FILE = "./stories.json";

const TOKEN = process.env.TOKEN;
const USERNAME = process.env.USERNAME;
const REPO = process.env.REPO;
const BRANCH = process.env.BRANCH;

// ==== HÀM LẤY DANH SÁCH TRUYỆN ====
async function fetchStoryList(page) {
  try {
    const list = await story.fetchList({
      page,
      status: 0,
      sort: "last_update"
    });
    return list || [];
  } catch (e) {
    console.log(`[WARN] Failed page ${page}: ${e}`);
    return [];
  }
}

// ==== HÀM LẤY CHI TIẾT TRUYỆN ====
async function fetchStoryData(url) {
  try {
    const data = await story.fetchStory({ url });
    const chapters = [];

    for (let i = 1; i <= data.totalChapter; i++) {
      try {
        const imgs = await story.fetchChapter({
          url,
          chapter: i
        });
        chapters.push({
          name: `Chapter ${i}`,
          images: imgs
        });
      } catch {}
    }

    return {
      id: data.slug,
      title: data.title,
      author: data.author || "Không rõ",
      description: data.description || "",
      thumbnail: data.thumbnail || "",
      chapters
    };
  } catch (e) {
    console.log(`[WARN] Failed story ${url}: ${e}`);
    return null;
  }
}

// ==== HÀM LƯU JSON ====
function saveStories(data) {
  fs.writeFileSync(STORIES_FILE, JSON.stringify(data, null, 2), "utf-8");
  console.log(`Saved ${data.length} stories to ${STORIES_FILE}`);
}

// ==== HÀM PUSH GITHUB ====
function pushToGitHub() {
  try {
    execSync(`git config --global user.name "${USERNAME}"`);
    execSync(`git config --global user.email "actions@github.com"`);
    execSync(`git add ${STORIES_FILE}`);
    execSync(`git commit -m "Update stories.json" || echo "No changes"`);
    execSync(`git push https://${TOKEN}@github.com/${USERNAME}/${REPO}.git ${BRANCH}`);
    console.log("Pushed to GitHub successfully!");
  } catch (e) {
    console.log("Failed to push to GitHub:", e.message);
  }
}

// ==== CHẠY SCRAPER ====
async function runScraper() {
  const allStories = [];

  for (let page = START_PAGE; page <= END_PAGE; page++) {
    console.log(`Fetching list page: ${page}`);
    const list = await fetchStoryList(page);

    for (const item of list) {
      console.log(`Scraping ${item.url}`);
      const storyData = await fetchStoryData(item.url);
      if (storyData) allStories.push(storyData);
    }
  }

  saveStories(allStories);
  pushToGitHub();
}

runScraper();

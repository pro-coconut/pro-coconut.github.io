import axios from "axios";
import cheerio from "cheerio";
import fs from "fs";

const START_PAGE = 4;
const END_PAGE = 14;
const STORIES_FILE = "./stories.json";

// Lấy danh sách truyện từ 1 page
async function fetchStoryList(page) {
  const url = `https://nettruyen0209.com/danh-sach-truyen/${page}/?sort=last_update&status=0`;
  try {
    const res = await axios.get(url);
    const $ = cheerio.load(res.data);
    const links = [];
    $(".col-truyen-list .list-truyen-item a").each((i, el) => {
      const href = $(el).attr("href");
      if (href) links.push(href);
    });
    return links;
  } catch (e) {
    console.warn(`[WARN] Failed page ${page}: ${e.message}`);
    return [];
  }
}

// Lấy thông tin chi tiết 1 truyện
async function fetchStoryData(storyUrl) {
  try {
    const res = await axios.get(storyUrl);
    const $ = cheerio.load(res.data);

    const title = $("h1.title-detail").text().trim() || "Không rõ";
    const author = $(".author span").text().trim() || "Không rõ";
    const description = $(".summary_content").text().trim() || "";
    const slug = storyUrl.split("/").filter(Boolean).pop();
    const thumbnail = $(".info-image img").attr("src") || "";

    // Lấy chapters (giả lập từ chapter 1 → 100)
    const chapters = [];
    for (let i = 1; i <= 100; i++) {
      const chapUrl = `${storyUrl}/chapter-${i}`;
      try {
        const chapRes = await axios.get(chapUrl);
        const $$ = cheerio.load(chapRes.data);
        const imgs = [];
        $$(".reading-detail img").each((j, img) => {
          const src = $$(img).attr("data-src") || $$(img).attr("src");
          if (src) imgs.push(src);
        });
        if (imgs.length > 0) {
          chapters.push({ name: `Chapter ${i}`, images: imgs });
        } else {
          break;
        }
      } catch {
        break;
      }
    }

    return { id: slug, title, author, description, thumbnail, chapters };
  } catch (e) {
    console.warn(`[WARN] Failed ${storyUrl}: ${e.message}`);
    return null;
  }
}

async function runScraper() {
  const allStories = [];

  for (let page = START_PAGE; page <= END_PAGE; page++) {
    console.log(`Fetching list page: ${page}`);
    const storyLinks = await fetchStoryList(page);
    for (const link of storyLinks) {
      console.log(`Scraping ${link}`);
      const story = await fetchStoryData(link);
      if (story) allStories.push(story);
    }
  }

  fs.writeFileSync(STORIES_FILE, JSON.stringify(allStories, null, 2), "utf-8");
  console.log(`Saved ${allStories.length} stories to ${STORIES_FILE}`);
}

runScraper();

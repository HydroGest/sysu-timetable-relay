const SERVER = "http://127.0.0.1:8123";
const SYNC_ALARM = "sync-cookie";

function collectCookie() {
  return chrome.cookies.getAll({}).then((cookies) => {
    const keep = cookies.filter((c) => /(^|\.)sysu\.edu\.cn$/.test(c.domain || ""));
    return keep.map((c) => `${c.name}=${c.value}`).join("; ");
  });
}

function setBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

async function pushCookie() {
  try {
    const cookie = await collectCookie();
    if (!cookie) {
      setBadge("!", "#c0392b");
      return;
    }
    await fetch(SERVER + "/cookie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie, at: Date.now() }),
    });
    setBadge("OK", "#2e8b57");
  } catch (e) {
    setBadge("!", "#c0392b");
  }
}

function scheduleSync() {
  chrome.alarms.create(SYNC_ALARM, { periodInMinutes: 1 });
}

chrome.runtime.onInstalled.addListener(() => {
  scheduleSync();
  pushCookie();
});

chrome.runtime.onStartup.addListener(() => {
  scheduleSync();
  pushCookie();
});

chrome.action.onClicked.addListener(() => {
  pushCookie();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === SYNC_ALARM) pushCookie();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (
    changeInfo.status === "complete" &&
    tab.url &&
    /jwxt\.sysu\.edu\.cn|cas\.sysu\.edu\.cn/.test(tab.url)
  ) {
    setTimeout(pushCookie, 1200);
  }
});

chrome.cookies.onChanged.addListener((changeInfo) => {
  const c = changeInfo.cookie || {};
  if (/(^|\.)sysu\.edu\.cn$/.test(c.domain || "")) {
    setTimeout(pushCookie, 300);
  }
});

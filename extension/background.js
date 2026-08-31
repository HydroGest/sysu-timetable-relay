const SERVER = "http://127.0.0.1:8123";
const SYNC_ALARM = "sync-cookie";

function collectCookie() {
  return chrome.cookies.getAll({}).then((cookies) => {
    const keep = cookies.filter((c) => /(^|\.)sysu\.edu\.cn$/.test(c.domain || ""));
    return keep.map((c) => `${c.name}=${c.value}`).join("; ");
  });
}

async function pushCookie() {
  try {
    const cookie = await collectCookie();
    if (!cookie) return;
    await fetch(SERVER + "/cookie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie, at: Date.now() }),
    });
  } catch (e) {
    // 本地服务未启动时静默重试
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

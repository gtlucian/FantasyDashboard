document.getElementById('openDashboardBtn').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://gtlucian.github.io/FantasyDashboard/' });
});
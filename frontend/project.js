document.getElementById("searchBtn").addEventListener("click", () => {
  const query = document.getElementById("searchInput").value.trim();
  const duration = document.getElementById("durationSelect") ? document.getElementById("durationSelect").value : "medium";
  
  if (!query) {
    alert("Please enter a search query.");
    return;
  }

  // Redirect to results page with query, user, and duration
  window.location.href = `/results?query=${encodeURIComponent(query)}&user=guest&duration=${duration}`;
});

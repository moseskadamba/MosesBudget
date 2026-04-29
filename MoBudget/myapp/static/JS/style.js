/* License ID: DEVOMATE-SRC-20260112-CAEBJ01FWQ | bobjunior297@gmail.com | 2026-01-12 01:15:55 */
const sidebar = document.getElementById("sidebar");
const main = document.getElementById("main-content");
const toggleBtn = document.getElementById("toggleSidebar");
const closeBtn = document.getElementById("closeSidebar");
const overlay = document.getElementById("sidebarOverlay");

toggleBtn.addEventListener("click", () => {
    if (window.innerWidth <= 991) {
        sidebar.classList.add("active");
        overlay.classList.add("show");
        document.body.style.overflow = "hidden";
    } else {
        sidebar.classList.toggle("collapsed");
        main.classList.toggle("expanded");
    }
});

closeBtn.addEventListener("click", () => {
    sidebar.classList.remove("active");
    overlay.classList.remove("show");
    document.body.style.overflow = "";
});

overlay.addEventListener("click", () => {
    sidebar.classList.remove("active");
    overlay.classList.remove("show");
    document.body.style.overflow = "";
});

window.addEventListener("resize", () => {
    if (window.innerWidth > 991) {
        sidebar.classList.remove("active");
        overlay.classList.remove("show");
        document.body.style.overflow = "";
    }
});






// icons


// List of Bootstrap Icons (subset for example, can extend to 200+)
  // Full list of Bootstrap Icons (replace with full official list)
const icons = [
  "house-door-fill","gear-fill","person-fill","bell-fill","envelope-fill","chat-dots-fill",
  "cart-fill","calendar-fill","clock-fill","star-fill","heart-fill","cloud-fill","bookmark-fill",
  "camera-fill","chat-left-fill","folder-fill","file-earmark-fill","file-text-fill","flag-fill",
  "gift-fill","globe","hand-thumbs-up-fill","hand-thumbs-down-fill","headphones","inbox-fill",
  "key-fill","lightning-fill","link-45deg","lock-fill","music-note-beamed","pause-fill","play-fill",
  "printer-fill","puzzle-fill","record-fill","shield-fill","star","trash-fill","unlock-fill",
  "wifi","x-circle-fill","zoom-in","zoom-out"
  // Extend this array with all official Bootstrap Icons for hundreds of icons
];

const iconsGrid = document.getElementById("iconsGrid");

// Dynamically generate icon cards
icons.forEach(icon => {
  const col = document.createElement("div");
  col.className = "col-2 icon-card";
  col.innerHTML = `
    <i class="bi bi-${icon} fs-2"></i>
    <div class="icon-name">${icon}</div>
    <button class="icon-copy-btn" onclick="copyIcon('${icon}')">Copy</button>
  `;
  iconsGrid.appendChild(col);
});

// Copy icon function
function copyIcon(iconName) {
  navigator.clipboard.writeText(`<i class="bi bi-${iconName}"></i>`)
    .then(() => alert(`Copied: <i class="bi bi-${iconName}"></i>`))
    .catch(() => alert("Failed to copy!"));
}

// Search functionality
document.getElementById('iconSearch').addEventListener('keyup', function() {
  let filter = this.value.toLowerCase();
  document.querySelectorAll('#iconsGrid .icon-card').forEach(card => {
    let name = card.querySelector('.icon-name').innerText.toLowerCase();
    card.style.display = name.includes(filter) ? '' : 'none';
  });
});
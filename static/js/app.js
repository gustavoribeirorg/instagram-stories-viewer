let currentProfile = null;

// Tab Management
function switchTab(tabName) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.remove("bg-slate-800", "text-white", "shadow");
    btn.classList.add("text-slate-400");
  });

  const targetTab = document.getElementById(`tab-${tabName}`);
  const targetBtn = document.getElementById(`tab-btn-${tabName}`);

  if (targetTab && targetBtn) {
    targetTab.classList.remove("hidden");
    targetBtn.classList.add("bg-slate-800", "text-white", "shadow");
    targetBtn.classList.remove("text-slate-400");
  }

  if (tabName === "monitored") {
    loadMonitoredProfiles();
    loadStats();
  } else if (tabName === "downloads") {
    loadDownloadedFiles();
  }
}

// Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");

  const bgColors = {
    success: "bg-emerald-900/90 border-emerald-700 text-emerald-100",
    error: "bg-red-900/90 border-red-700 text-red-100",
    info: "bg-slate-800/95 border-slate-700 text-slate-100"
  };

  const icons = {
    success: '<i class="fa-solid fa-circle-check text-emerald-400"></i>',
    error: '<i class="fa-solid fa-circle-xmark text-red-400"></i>',
    info: '<i class="fa-solid fa-circle-info text-pink-400"></i>'
  };

  toast.className = `pointer-events-auto border rounded-xl p-4 shadow-xl backdrop-blur flex items-center gap-3 text-sm transition-all duration-300 transform translate-y-4 opacity-0 ${bgColors[type] || bgColors.info}`;
  toast.innerHTML = `
    ${icons[type] || icons.info}
    <div class="flex-1 font-medium">${message}</div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.remove("translate-y-4", "opacity-0");
  }, 10);

  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-y-4");
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Search Stories
async function handleSearch(event) {
  event.preventDefault();
  const input = document.getElementById("username-input");
  const username = input.value.trim().replace(/^@/, "");
  if (!username) return;

  const loading = document.getElementById("viewer-loading");
  const errorBox = document.getElementById("viewer-error");
  const errorText = document.getElementById("viewer-error-text");
  const resultsBox = document.getElementById("viewer-results");
  const searchBtn = document.getElementById("search-button");

  loading.classList.remove("hidden");
  errorBox.classList.add("hidden");
  resultsBox.classList.add("hidden");
  searchBtn.disabled = true;

  try {
    const res = await fetch(`/api/stories/${encodeURIComponent(username)}`);
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Não foi possível carregar os stories.");
    }

    currentProfile = data;
    renderProfileStories(data);
  } catch (err) {
    errorText.innerText = err.message;
    errorBox.classList.remove("hidden");
  } finally {
    loading.classList.add("hidden");
    searchBtn.disabled = false;
  }
}

function renderProfileStories(profile) {
  const resultsBox = document.getElementById("viewer-results");
  const grid = document.getElementById("stories-grid");
  const avatar = document.getElementById("profile-avatar");
  const usernameEl = document.getElementById("profile-username");
  const nameEl = document.getElementById("profile-name");
  const badge = document.getElementById("profile-story-badge");

  avatar.src = profile.avatar_url ? `/api/proxy-media?url=${encodeURIComponent(profile.avatar_url)}` : 'https://placehold.co/100x100?text=@';
  usernameEl.innerHTML = `@${profile.username} ${profile.is_private ? '<i class="fa-solid fa-lock text-xs text-amber-400"></i>' : ''}`;
  nameEl.innerText = profile.display_name || "Perfil Público";
  badge.innerText = profile.story_count;

  grid.innerHTML = "";

  if (!profile.stories || profile.stories.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-16 text-center text-slate-400 bg-slate-900/50 rounded-2xl border border-slate-800">
        <i class="fa-regular fa-clock text-4xl mb-3 block text-slate-600"></i>
        <p class="font-medium text-slate-300">Nenhum story ativo no momento</p>
        <p class="text-xs text-slate-500 mt-1">Este perfil não publicou stories nas últimas 24 horas.</p>
      </div>
    `;
  } else {
    profile.stories.forEach((story, index) => {
      const card = document.createElement("div");
      card.className = "bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col shadow-lg transition-transform hover:-translate-y-1";

      const proxyMediaUrl = `/api/proxy-media?url=${encodeURIComponent(story.media_url)}`;

      let mediaHtml = "";
      if (story.media_type === "video") {
        mediaHtml = `
          <div class="relative w-full story-aspect bg-black flex items-center justify-center">
            <video 
              src="${proxyMediaUrl}" 
              controls 
              playsinline
              preload="metadata"
              class="w-full h-full object-cover"
            ></video>
            <span class="absolute top-2.5 left-2.5 bg-black/60 backdrop-blur text-white text-xs px-2 py-0.5 rounded-md flex items-center gap-1 pointer-events-none">
              <i class="fa-solid fa-video text-pink-400 text-xs"></i> Vídeo
            </span>
          </div>
        `;
      } else {
        mediaHtml = `
          <div class="relative w-full story-aspect bg-black flex items-center justify-center">
            <img 
              src="${proxyMediaUrl}" 
              alt="Story ${index + 1}" 
              class="w-full h-full object-cover" 
              loading="lazy"
            >
            <span class="absolute top-2.5 left-2.5 bg-black/60 backdrop-blur text-white text-xs px-2 py-0.5 rounded-md flex items-center gap-1 pointer-events-none">
              <i class="fa-solid fa-image text-orange-400 text-xs"></i> Foto
            </span>
          </div>
        `;
      }

      card.innerHTML = `
        ${mediaHtml}
        <div class="p-3.5 flex items-center justify-between border-t border-slate-800/80 bg-slate-900/90">
          <span class="text-xs text-slate-400 font-mono">#${index + 1}</span>
          <button 
            onclick='downloadSingleStory(${JSON.stringify(story).replace(/'/g, "&apos;")}, "${profile.username}")'
            class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 border border-slate-700"
          >
            <i class="fa-solid fa-download text-pink-400"></i>
            <span>Baixar</span>
          </button>
        </div>
      `;
      grid.appendChild(card);
    });
  }

  resultsBox.classList.remove("hidden");
}

// Download Single Story
async function downloadSingleStory(story, username) {
  showToast("Iniciando download da mídia...", "info");
  try {
    const res = await fetch("/api/download-single", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, story })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao baixar.");
    
    showToast(`Story salvo: ${data.filename}`, "success");
    
    // Forçar trigger do download no navegador do usuário
    const a = document.createElement("a");
    a.href = data.url;
    a.download = data.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    showToast(`Falha no download: ${err.message}`, "error");
  }
}

// Download All Current Stories
async function downloadAllCurrentStories() {
  if (!currentProfile || !currentProfile.username) return;
  const btn = document.getElementById("btn-download-all");
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Baixando...`;

  showToast(`Baixando todos os stories de @${currentProfile.username}...`, "info");
  try {
    const res = await fetch(`/api/download-all/${encodeURIComponent(currentProfile.username)}`, {
      method: "POST"
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erro ao baixar todos.");

    showToast(`Sucesso! ${data.downloaded_count} stories salvos na pasta downloads/${currentProfile.username}`, "success");
  } catch (err) {
    showToast(`Erro: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-cloud-arrow-down"></i> <span>Baixar Todos</span>`;
  }
}

// Add Current Profile to Monitored
async function addCurrentToMonitored() {
  if (!currentProfile) return;
  await addProfileToMonitoredAPI(currentProfile.username, currentProfile.display_name, currentProfile.avatar_url);
}

async function handleAddMonitored(event) {
  event.preventDefault();
  const input = document.getElementById("new-monitored-user");
  const username = input.value.trim().replace(/^@/, "");
  if (!username) return;

  await addProfileToMonitoredAPI(username);
  input.value = "";
}

async function addProfileToMonitoredAPI(username, displayName = "", avatarUrl = "") {
  try {
    const res = await fetch("/api/monitored", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, display_name: displayName, avatar_url: avatarUrl })
    });
    if (!res.ok) throw new Error("Erro ao adicionar perfil.");

    showToast(`@${username} agora é monitorado a cada 24h!`, "success");
    loadMonitoredProfiles();
    loadStats();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Load Monitored Profiles
async function loadMonitoredProfiles() {
  const tbody = document.getElementById("monitored-table-body");
  tbody.innerHTML = `<tr><td colspan="4" class="px-6 py-8 text-center text-slate-500">Carregando perfis...</td></tr>`;

  try {
    const res = await fetch("/api/monitored");
    const profiles = await res.json();

    if (profiles.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" class="px-6 py-8 text-center text-slate-500">Nenhum perfil cadastrado ainda.</td></tr>`;
      return;
    }

    tbody.innerHTML = profiles.map(p => `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="px-6 py-4 flex items-center gap-3">
          <img src="${p.avatar_url ? `/api/proxy-media?url=${encodeURIComponent(p.avatar_url)}` : 'https://placehold.co/80x80?text=@'}" class="w-9 h-9 rounded-full object-cover border border-slate-700 bg-slate-900">
          <div>
            <span class="font-semibold text-white block">@${p.username}</span>
            <span class="text-xs text-slate-400">${p.display_name || ''}</span>
          </div>
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${p.is_active ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-400'}">
            <span class="w-1.5 h-1.5 rounded-full ${p.is_active ? 'bg-emerald-400' : 'bg-slate-500'}"></span>
            ${p.is_active ? 'Ativo' : 'Pausado'}
          </span>
        </td>
        <td class="px-6 py-4 text-xs text-slate-400">
          ${p.last_checked_at ? new Date(p.last_checked_at).toLocaleString('pt-BR') : 'Ainda não verificado'}
        </td>
        <td class="px-6 py-4 text-right space-x-2">
          <button onclick="toggleMonitoredStatus('${p.username}', ${!p.is_active})" class="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition" title="${p.is_active ? 'Pausar' : 'Retomar'}">
            <i class="fa-solid ${p.is_active ? 'fa-pause' : 'fa-play'}"></i>
          </button>
          <button onclick="deleteMonitored('${p.username}')" class="p-1.5 hover:bg-red-950/60 text-slate-400 hover:text-red-400 rounded-lg transition" title="Remover">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="px-6 py-4 text-center text-red-400">Erro ao carregar lista.</td></tr>`;
  }
}

async function toggleMonitoredStatus(username, isActive) {
  try {
    await fetch(`/api/monitored/${encodeURIComponent(username)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive })
    });
    loadMonitoredProfiles();
  } catch (err) {
    showToast("Erro ao alterar status.", "error");
  }
}

async function deleteMonitored(username) {
  if (!confirm(`Deseja parar de monitorar @${username}?`)) return;
  try {
    await fetch(`/api/monitored/${encodeURIComponent(username)}`, { method: "DELETE" });
    showToast(`@${username} removido dos monitorados.`, "info");
    loadMonitoredProfiles();
    loadStats();
  } catch (err) {
    showToast("Erro ao remover perfil.", "error");
  }
}

// Trigger Manual Sync
async function triggerSyncNow() {
  const btn = document.getElementById("btn-sync-now");
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>Sincronizando...</span>`;

  try {
    const res = await fetch("/api/sync-now", { method: "POST" });
    const data = await res.json();
    showToast("Varredura iniciada em segundo plano na VM!", "info");
    setTimeout(() => {
      loadMonitoredProfiles();
      loadStats();
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-bolt"></i> <span>Sincronizar Agora</span>`;
    }, 4000);
  } catch (err) {
    showToast("Erro ao disparar sincronização.", "error");
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-bolt"></i> <span>Sincronizar Agora</span>`;
  }
}

// Stats & Scheduler info
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    document.getElementById("stat-monitored").innerText = data.total_monitored;
    document.getElementById("stat-downloads").innerText = data.total_downloads;

    const nextEl = document.getElementById("stat-next-run");
    if (data.scheduler && data.scheduler.next_run_time) {
      const dt = new Date(data.scheduler.next_run_time);
      nextEl.innerText = `Próx: ${dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
    } else {
      nextEl.innerText = "A cada 24h";
    }
  } catch (e) {
    console.error("Erro ao carregar estatísticas:", e);
  }
}

// Load Downloaded Files Gallery
async function loadDownloadedFiles() {
  const grid = document.getElementById("downloads-grid");
  const empty = document.getElementById("downloads-empty");
  grid.innerHTML = `<div class="col-span-full text-center py-12 text-slate-500">Carregando mídias salvas...</div>`;

  try {
    const res = await fetch("/api/downloads");
    const files = await res.json();

    if (files.length === 0) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }

    empty.classList.add("hidden");
    grid.innerHTML = files.map(file => {
      let mediaPreview = "";
      if (file.media_type === "video") {
        mediaPreview = `
          <div class="relative w-full story-aspect bg-black">
            <video src="${file.web_url}" controls preload="metadata" class="w-full h-full object-cover"></video>
            <span class="absolute top-2 left-2 bg-black/60 backdrop-blur text-white text-xs px-2 py-0.5 rounded-md pointer-events-none">
              <i class="fa-solid fa-video text-pink-400"></i> Vídeo
            </span>
          </div>
        `;
      } else {
        mediaPreview = `
          <div class="relative w-full story-aspect bg-black">
            <img src="${file.web_url}" alt="${file.filename}" class="w-full h-full object-cover" loading="lazy">
            <span class="absolute top-2 left-2 bg-black/60 backdrop-blur text-white text-xs px-2 py-0.5 rounded-md pointer-events-none">
              <i class="fa-solid fa-image text-orange-400"></i> Foto
            </span>
          </div>
        `;
      }

      const sizeMB = (file.size_bytes / (1024 * 1024)).toFixed(2);
      const dateStr = new Date(file.created_at).toLocaleString('pt-BR');

      return `
        <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col shadow-lg">
          ${mediaPreview}
          <div class="p-4 border-t border-slate-800/80 bg-slate-900/90 flex flex-col gap-2">
            <div class="flex items-center justify-between">
              <span class="font-semibold text-sm text-white">@${file.username}</span>
              <span class="text-xs text-slate-500">${sizeMB} MB</span>
            </div>
            <p class="text-xs text-slate-400 truncate" title="${file.filename}">${file.filename}</p>
            <div class="flex items-center justify-between pt-1">
              <span class="text-[11px] text-slate-500">${dateStr}</span>
              <a href="${file.web_url}" download="${file.filename}" class="text-xs text-pink-400 hover:text-pink-300 font-medium flex items-center gap-1">
                <i class="fa-solid fa-download"></i> Baixar
              </a>
            </div>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    grid.innerHTML = `<div class="col-span-full text-center py-12 text-red-400">Erro ao listar downloads.</div>`;
  }
}

// Initial stats load
document.addEventListener("DOMContentLoaded", () => {
  loadStats();
});

// State
let currentAnime = null;
let currentEpisode = null;
let currentEpisodesList = [];
let currentStreams = [];
let currentDownloads = [];
let activePlayerMode = 'artplayer'; // 'artplayer' | 'kwik' | 'inspector'
let artInstance = null;
let currentPage = 1;
let totalPages = 1;

// Image proxy helper to avoid CORP / net::ERR_BLOCKED_BY_RESPONSE.NotSameOrigin
function getProxiedImageUrl(url) {
    if (!url) return '';
    if (url.startsWith('/stream/image') || url.startsWith('data:') || url.startsWith('blob:')) return url;
    return `/stream/image?url=${encodeURIComponent(url)}`;
}

// DOM Elements
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const animeCardsGrid = document.getElementById('animeCardsGrid');
const catalogLoading = document.getElementById('catalogLoading');
const searchCounter = document.getElementById('searchCounter');
const resultsCount = document.getElementById('resultsCount');

const episodeSection = document.getElementById('episodeSection');
const episodesGrid = document.getElementById('episodesGrid');
const currentAnimePoster = document.getElementById('currentAnimePoster');
const currentAnimeTitle = document.getElementById('currentAnimeTitle');
const currentAnimeDetails = document.getElementById('currentAnimeDetails');
const episodesPagination = document.getElementById('episodesPagination');
const prevPageBtn = document.getElementById('prevPageBtn');
const nextPageBtn = document.getElementById('nextPageBtn');
const pageInfoText = document.getElementById('pageInfoText');

const playerSection = document.getElementById('playerSection');
const playerAnimeTitle = document.getElementById('playerAnimeTitle');
const playerEpisodeBadge = document.getElementById('playerEpisodeBadge');
const playerDurationBadge = document.getElementById('playerDurationBadge');
const playerAudioBadge = document.getElementById('playerAudioBadge');
const qualityPillsList = document.getElementById('qualityPillsList');
const downloadsMenu = document.getElementById('downloadsMenu');

const kwikContainer = document.getElementById('kwikContainer');
const kwikIframe = document.getElementById('kwikIframe');
const artplayerContainer = document.getElementById('artplayerContainer');
const inspectorContainer = document.getElementById('inspectorContainer');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    // Search listeners
    searchBtn.addEventListener('click', () => performSearch());
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Pagination listeners
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) loadEpisodes(currentAnime.anime_session, currentPage - 1);
    });
    nextPageBtn.addEventListener('click', () => {
        if (currentPage < totalPages) loadEpisodes(currentAnime.anime_session, currentPage + 1);
    });

    // Initial search to populate catalog on launch
    performSearch('Demon Slayer');
});

// Quick Search trigger
function quickSearch(title) {
    searchInput.value = title;
    performSearch(title);
}

// 1. Search Anime
async function performSearch(customQuery = null) {
    const query = (customQuery || searchInput.value).trim();
    if (!query) return;

    catalogLoading.classList.remove('hidden');
    animeCardsGrid.innerHTML = '';
    searchCounter.classList.add('hidden');

    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        catalogLoading.classList.add('hidden');

        if (data.status === 'success' && data.results.length > 0) {
            resultsCount.innerText = data.total_results;
            searchCounter.classList.remove('hidden');
            renderAnimeCards(data.results);
        } else {
            animeCardsGrid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
                    <i class="fa-solid fa-face-frown" style="font-size: 36px; margin-bottom: 12px; display: block;"></i>
                    No anime found matching "<strong>${escapeHtml(query)}</strong>". Try searching another title.
                </div>
            `;
        }
    } catch (err) {
        catalogLoading.classList.add('hidden');
        animeCardsGrid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--red);">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 36px; margin-bottom: 12px; display: block;"></i>
                Failed to fetch search results. Make sure backend server is running.
            </div>
        `;
    }
}

// Render Anime Cards
function renderAnimeCards(animeList) {
    animeCardsGrid.innerHTML = '';
    animeList.forEach(anime => {
        const card = document.createElement('div');
        card.className = 'anime-card';
        card.onclick = () => selectAnime(anime);

        const score = anime.score ? `★ ${anime.score}` : 'N/A';
        const type = anime.type || 'TV';
        const eps = anime.total_episodes ? `${anime.total_episodes} eps` : '? eps';
        const seasonYear = anime.season || anime.year || '';

        card.innerHTML = `
            <div class="anime-poster-wrapper">
                <img class="anime-poster" src="${getProxiedImageUrl(anime.poster_image)}" alt="${escapeHtml(anime.title)}" loading="lazy">
                <span class="anime-type-pill">${escapeHtml(type)}</span>
                <span class="anime-score-pill">${escapeHtml(score)}</span>
            </div>
            <div class="anime-card-info">
                <h4 class="anime-card-title" title="${escapeHtml(anime.title)}">${escapeHtml(anime.title)}</h4>
                <div class="anime-card-meta">
                    <span>${escapeHtml(seasonYear)}</span>
                    <span>${escapeHtml(eps)}</span>
                </div>
            </div>
        `;
        animeCardsGrid.appendChild(card);
    });
}

// 2. Select Anime & Load Episodes
async function selectAnime(anime) {
    currentAnime = anime;
    currentAnimePoster.src = getProxiedImageUrl(anime.poster_image);
    currentAnimeTitle.innerText = anime.title;
    currentAnimeDetails.innerText = `${anime.type || 'TV'} · ${anime.season || anime.year || ''} · ${anime.total_episodes || '?'} Episodes`;

    episodeSection.classList.remove('hidden');
    episodeSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    await loadEpisodes(anime.anime_session, 1);
}

// Load Episodes Page
async function loadEpisodes(animeSession, page = 1) {
    episodesGrid.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
            <div class="spinner" style="margin: 0 auto 16px;"></div>
            Loading episodes...
        </div>
    `;

    try {
        const res = await fetch(`/api/episodes?session=${animeSession}&page=${page}`);
        const data = await res.json();

        if (data.status === 'success') {
            currentPage = data.current_page || page;
            totalPages = data.last_page || 1;
            currentEpisodesList = data.episodes || [];

            // Update pagination
            if (totalPages > 1) {
                episodesPagination.classList.remove('hidden');
                pageInfoText.innerText = `Page ${currentPage} of ${totalPages} (${data.total_episodes} Total Episodes)`;
                prevPageBtn.disabled = currentPage <= 1;
                nextPageBtn.disabled = currentPage >= totalPages;
            } else {
                episodesPagination.classList.add('hidden');
            }

            renderEpisodesGrid(currentEpisodesList);

            // Auto-select episode 1 if available
            if (currentEpisodesList.length > 0) {
                selectEpisode(currentEpisodesList[0]);
            }
        }
    } catch (err) {
        episodesGrid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; color: var(--red); padding: 30px;">
                Failed to load episodes.
            </div>
        `;
    }
}

// Render Episodes Grid
function renderEpisodesGrid(episodes) {
    episodesGrid.innerHTML = '';
    episodes.forEach(ep => {
        const card = document.createElement('div');
        card.className = `episode-card ${currentEpisode && currentEpisode.episode_session === ep.episode_session ? 'active' : ''}`;
        card.id = `ep-card-${ep.episode_session}`;
        card.onclick = () => selectEpisode(ep);

        const duration = ep.duration || '24m';
        const audio = ep.audio ? ep.audio.toUpperCase() : 'SUB';
        const rawSnapshot = ep.snapshot_url || (currentAnime ? currentAnime.poster_image : '');
        const snapshot = getProxiedImageUrl(rawSnapshot);

        card.innerHTML = `
            <div class="ep-thumb-wrap">
                <img src="${snapshot}" alt="Ep ${ep.episode_number}" loading="lazy">
                <span class="ep-audio-tag">${escapeHtml(audio)}</span>
                <span class="ep-duration-tag">${escapeHtml(duration)}</span>
            </div>
            <div class="ep-details">
                <div class="ep-number">Episode ${ep.episode_number}</div>
                <div class="ep-air-date">${ep.created_at ? ep.created_at.split(' ')[0] : 'Available'}</div>
            </div>
        `;
        episodesGrid.appendChild(card);
    });
}

// Filter Episodes (All / Sub / Dub)
function filterEpisodes(type) {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    event.target.classList.add('active');

    if (type === 'all') {
        renderEpisodesGrid(currentEpisodesList);
    } else if (type === 'sub') {
        const filtered = currentEpisodesList.filter(e => !e.audio || e.audio.toLowerCase() !== 'eng');
        renderEpisodesGrid(filtered);
    } else if (type === 'dub') {
        const filtered = currentEpisodesList.filter(e => e.audio && e.audio.toLowerCase() === 'eng');
        renderEpisodesGrid(filtered);
    }
}

// 3. Select Episode & Load Stream Options
async function selectEpisode(ep) {
    currentEpisode = ep;

    // Highlight active card
    document.querySelectorAll('.episode-card').forEach(c => c.classList.remove('active'));
    const activeEl = document.getElementById(`ep-card-${ep.episode_session}`);
    if (activeEl) activeEl.classList.add('active');

    // Show Player Section
    playerSection.classList.remove('hidden');
    playerAnimeTitle.innerText = currentAnime.title;
    playerEpisodeBadge.innerText = `Episode ${ep.episode_number}`;
    playerDurationBadge.innerHTML = `<i class="fa-regular fa-clock"></i> ${ep.duration || '24m'}`;
    playerAudioBadge.innerText = (ep.audio || 'SUB').toUpperCase();

    // Scroll to player
    playerSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Fetch Stream & Download Options
    qualityPillsList.innerHTML = `<span class="loading-shimmer">Fetching stream qualities from AnimePahe...</span>`;
    downloadsMenu.innerHTML = '';

    try {
        const res = await fetch(`/api/streams?anime_session=${currentAnime.anime_session}&episode_session=${ep.episode_session}`);
        const data = await res.json();

        if (data.status === 'success') {
            currentStreams = data.streams || [];
            currentDownloads = data.downloads || [];

            renderQualityPills(currentStreams);
            renderDownloadsMenu(currentDownloads);

            // Default: pick 1080p BD or 720p BD, or first available
            let defaultStream = currentStreams.find(s => s.quality.includes('1080p') && !s.quality.includes('eng')) ||
                                currentStreams.find(s => s.quality.includes('720p') && !s.quality.includes('eng')) ||
                                currentStreams[0];

            if (defaultStream) {
                activateStreamQuality(defaultStream);
            } else if (data.default_embed) {
                activateStreamQuality({ quality: 'Default', embed_url: data.default_embed });
            }
        }
    } catch (err) {
        qualityPillsList.innerHTML = `<span style="color: var(--red);">Failed to load stream qualities.</span>`;
    }
}

// Render Quality Pills (360p, 720p, 1080p, Sub/Dub)
function renderQualityPills(streams) {
    qualityPillsList.innerHTML = '';
    if (streams.length === 0) {
        qualityPillsList.innerHTML = `<span style="color: var(--text-muted); font-size: 13px;">No stream links available</span>`;
        return;
    }

    streams.forEach(stream => {
        const pill = document.createElement('div');
        pill.className = 'quality-pill';
        pill.innerText = stream.quality;
        pill.onclick = () => activateStreamQuality(stream);
        qualityPillsList.appendChild(pill);
    });
}

// Render Downloads Menu
function renderDownloadsMenu(downloads) {
    downloadsMenu.innerHTML = '';
    if (downloads.length === 0) {
        downloadsMenu.innerHTML = `<div style="padding: 10px; color: var(--text-muted); font-size: 12px;">No direct downloads</div>`;
        return;
    }

    downloads.forEach(d => {
        const item = document.createElement('a');
        item.className = 'download-item';
        item.href = d.download_page;
        item.target = '_blank';
        item.innerHTML = `
            <span><i class="fa-solid fa-file-arrow-down" style="margin-right: 6px;"></i> ${escapeHtml(d.quality)}</span>
            <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 11px; opacity: 0.6;"></i>
        `;
        downloadsMenu.appendChild(item);
    });
}

function toggleDownloadsMenu() {
    downloadsMenu.classList.toggle('hidden');
}

// Close downloads menu when clicking outside
document.addEventListener('click', (e) => {
    const wrapper = document.getElementById('downloadDropdownWrapper');
    if (wrapper && !wrapper.contains(e.target)) {
        downloadsMenu.classList.add('hidden');
    }
});

// Activate Stream Quality
function activateStreamQuality(stream) {
    // Highlight pill
    document.querySelectorAll('.quality-pill').forEach(p => {
        if (p.innerText === stream.quality) {
            p.classList.add('active');
        } else {
            p.classList.remove('active');
        }
    });

    // 1. Update Kwik Iframe and external fallback link
    kwikIframe.src = stream.embed_url;
    const kwikExtLink = document.getElementById('kwikExternalLink');
    if (kwikExtLink) kwikExtLink.href = stream.embed_url;

    // 2. If ArtPlayer active, re-initialize with direct m3u8
    if (activePlayerMode === 'artplayer') {
        resolveAndPlayArtPlayer(stream.quality, stream.embed_url);
    }
}

// 4. Resolve Direct CDN Details for Inspector
async function resolveDirectCdnDetails(ep, qualityLabel = null, embedUrl = null) {
    const inspectHost = document.getElementById('inspectHost');
    const inspectSegmentsCount = document.getElementById('inspectSegmentsCount');
    const inspectM3u8 = document.getElementById('inspectM3u8');
    const inspectKey = document.getElementById('inspectKey');
    const inspectCommand = document.getElementById('inspectCommand');

    inspectHost.innerText = 'Resolving CDN...';
    inspectM3u8.value = 'Resolving .m3u8 master playlist...';
    inspectSegmentsCount.innerText = 'Counting segments...';

    try {
        let url = `/api/resolve?anime_session=${currentAnime.anime_session}&episode_session=${ep.episode_session}`;
        if (qualityLabel) url += `&quality=${encodeURIComponent(qualityLabel)}`;
        if (embedUrl) url += `&embed_url=${encodeURIComponent(embedUrl)}`;

        const res = await fetch(url);
        const data = await res.json();

        if (data.status === 'success') {
            inspectHost.innerText = data.cdn_host || 'Direct CDN Host';
            inspectSegmentsCount.innerText = `${data.total_segments || 0} Video Chunks (.jpg TS segments)`;
            inspectM3u8.value = data.stream_m3u8 || 'Unavailable';
            inspectKey.value = data.encryption_key || 'None (Unencrypted or internal)';

            const vlcCmd = `vlc "${data.stream_m3u8}" :http-referrer="https://kwik.cx/"`;
            inspectCommand.innerHTML = `<code>${escapeHtml(vlcCmd)}</code>`;

            return data;
        }
    } catch (err) {
        inspectM3u8.value = 'Failed to resolve stream';
    }
    return null;
}

// ArtPlayer Integration
async function resolveAndPlayArtPlayer(qualityLabel = null, embedUrl = null) {
    if (artInstance) {
        try {
            if (artInstance.hls) {
                artInstance.hls.destroy();
            }
            artInstance.destroy(true);
        } catch (e) {
            console.warn('ArtPlayer cleanup warning:', e);
        }
        artInstance = null;
    }

    artplayerContainer.innerHTML = `
        <div class="player-loader">
            <div class="spinner"></div>
            <p>Resolving direct HLS Master Stream from CDN...</p>
        </div>
    `;

    const cdnData = await resolveDirectCdnDetails(currentEpisode, qualityLabel, embedUrl);
    if (!cdnData || !cdnData.stream_m3u8) {
        artplayerContainer.innerHTML = `
            <div style="height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--red); gap: 12px; padding: 20px; text-align: center;">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 32px;"></i>
                <div>Could not resolve direct HLS stream. You can switch to Kwik Embed mode or check the Inspector.</div>
            </div>
        `;
        return;
    }

    // Reset container and create clean wrapper for ArtPlayer
    artplayerContainer.innerHTML = '';
    const playerHolder = document.createElement('div');
    playerHolder.id = 'artplayerHolder';
    playerHolder.style.width = '100%';
    playerHolder.style.height = '100%';
    artplayerContainer.appendChild(playerHolder);

    // Route M3U8 through local zero-bandwidth proxy to bypass browser Referer & CORS blocks
    const localStreamUrl = `/stream/m3u8?url=${encodeURIComponent(cdnData.stream_m3u8)}`;

    artInstance = new Artplayer({
        container: playerHolder,
        url: localStreamUrl,
        type: 'm3u8',
        customType: {
            m3u8: function (video, url, art) {
                if (Hls.isSupported()) {
                    if (art.hls) art.hls.destroy();
                    const hls = new Hls({
                        maxBufferLength: 30,
                        maxMaxBufferLength: 60,
                        enableWorker: true
                    });
                    hls.loadSource(url);
                    hls.attachMedia(video);
                    art.hls = hls;
                    art.on('destroy', () => {
                        hls.destroy();
                    });
                } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                    video.src = url;
                } else {
                    art.notice.show = 'Unsupported playback format: m3u8';
                }
            }
        },
        theme: '#8b5cf6',
        autoplay: true,
        playbackRate: true,
        aspectRatio: true,
        setting: true,
        pip: true,
        fullscreen: true,
        fullscreenWeb: true
    });
}

// Switch Player Mode Tab
function switchPlayerMode(mode) {
    activePlayerMode = mode;

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    kwikContainer.classList.add('hidden');
    artplayerContainer.classList.add('hidden');
    inspectorContainer.classList.add('hidden');

    if (mode === 'artplayer') {
        document.getElementById('tabArt').classList.add('active');
        artplayerContainer.classList.remove('hidden');
        if (!artInstance && currentEpisode) {
            resolveAndPlayArtPlayer();
        }
    } else if (mode === 'kwik') {
        document.getElementById('tabKwik').classList.add('active');
        kwikContainer.classList.remove('hidden');
    } else if (mode === 'inspector') {
        document.getElementById('tabInspector').classList.add('active');
        inspectorContainer.classList.remove('hidden');
    }
}

// Copy to clipboard helper
function copyToClipboard(elementId) {
    const input = document.getElementById(elementId);
    if (!input) return;
    input.select();
    navigator.clipboard.writeText(input.value);

    const btn = event.currentTarget;
    const origText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
    setTimeout(() => {
        btn.innerHTML = origText;
    }, 1500);
}

// Escape HTML helper
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

let tg = window.Telegram.WebApp;
let user = null;
let currentProfileId = null;
let prevProfileId = null;
let currentProfileIndex = 0;
let currentPage = 'feed';
let currentFilters = {
    gender: 'all',
    goal: '',
    interests: [],
    apply_height: false,
    search_height: null
};
//let feedData = [];
//let feedIndex = 0;
let currentTheme = localStorage.getItem('theme') || 'cyberpunk';
const ALL_INTERESTS = ["юмор", "музыка", "игры", "путешествия", "спорт", "кино", "книги", "кулинария", "искусство", "технологии", "прогулки", "животные", "sex"];

async function init() {
    tg.expand();
    tg.ready();

    // Telegram всегда предоставляет initDataUnsafe при открытии через WebApp
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        user = tg.initDataUnsafe.user;
    } else {
        // Fallback для локальной разработки/тестирования вне Telegram
        const urlParams = new URLSearchParams(window.location.search);
        const tg_id = urlParams.get('tg_id');
        if (tg_id) {
            user = { id: parseInt(tg_id) };
        } else {
            document.getElementById('content').innerHTML = `
                <div class="card">
                    <p>❌ Откройте приложение через Telegram-бота</p>
                    <button onclick="window.open('https://t.me/GAZznakomitsya_bot', '_blank')">
                        📱 Открыть бота
                    </button>
                </div>`;
            return;
        }
    }

    renderHeader();
    renderBottomNav();
    navigateTo(window.location.hash || '#feed');
    window.addEventListener('hashchange', () => navigateTo(window.location.hash));
}

function renderHeader() {
    document.getElementById('header').innerHTML = `
        <div class="logo">GAZ</div>

        <div class="filter-area">
            <span class="filter-text">Фильтры →</span>
            <span class="filter-icon" onclick="toggleFilters()">🔍</span>
        </div>
    `;

    const header = document.getElementById('header');

    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';
    header.style.padding = '10px 14px';
}

function handleHash() {
    const hash = window.location.hash;
    if (hash === '#likes') {
        navigateTo('#likes');
    } else if (hash === '#feed') {
        navigateTo('#feed');
    } else if (hash === '#profile') {
        navigateTo('#profile');
    } else if (hash === '#events') {
        navigateTo('#events');
    }
}

handleHash();
window.addEventListener('hashchange', handleHash);

function renderBottomNav() {
    const nav = document.getElementById('bottomNav');
    nav.innerHTML = `
        <div class="nav-item" data-page="feed">🔥 Поиск</div>
        <div class="nav-item" data-page="incoming_likes">❤️ Входящие</div>
        <div class="nav-item" data-page="matches">💞 Матчи</div>
        <div class="nav-item" data-page="events">👥 События</div>
        <div class="nav-item" data-page="profile">👤 Профиль</div>
    `;
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', () => navigateTo('#' + el.dataset.page));
    });
}

async function loadMatches() {
    const content = document.getElementById('content');
    content.innerHTML = '<p>Загрузка...</p>';
    const data = await apiCall('/matches');
    if (!data.matches || data.matches.length === 0) {
        content.innerHTML = '<p>😔 У вас пока нет взаимных симпатий. Лайкайте анкеты, чтобы они появились!</p>';
        return;
    }
    let html = '';
    for (const match of data.matches) {
        const u = match.user;
        const telegramLink = u.username ? `https://t.me/${u.username}` : `https://t.me/GAZznakomitsya_bot?start=user_${u.tg_id}`;
        const photoUrl = u.photos?.[0]?.file_id
            ? `/api/photo/${u.photos[0].file_id}`
            : 'https://placehold.co/300x300?text=Нет+фото';
        html += `
            <div class="card" onclick="showProfileFromMatch(${u.tg_id})" style="cursor:pointer;">
                <div class="card-image" style="background-image: url('${photoUrl}'); height:150px; background-size:cover;"></div>
                <div class="name-age">${u.name}, ${u.age} ${u.is_verified ? '✅' : ''}</div>
                <div class="city">📍 ${u.city || '—'}</div>
                <div class="contact"><a href="${telegramLink}" target="_blank">✉️ Написать в Telegram</a></div>
            </div>
        `;
    }
    content.innerHTML = html;
}

function showProfileFromMatch(tg_id) {
    localStorage.setItem('return_to', 'matches');
    window.location.hash = `profile/${tg_id}`;
}

async function showForeignProfile(tg_id) {
    const content = document.getElementById('content');
    content.innerHTML = '<p>Загрузка...</p>';
    const data = await apiCall(`/profile/${tg_id}`);
    if (!data) {
        content.innerHTML = '<p>Профиль не найден</p>';
        return;
    }
    const photoUrl = data.photos?.[0]?.file_id
        ? `/api/photo/${data.photos[0].file_id}`
        : 'https://placehold.co/300x300?text=Нет+фото';
    const telegramLink = data.username ? `https://t.me/${data.username}` : `https://t.me/GAZznakomitsya_bot?start=user_${data.tg_id}`;

    const returnTo = localStorage.getItem('return_to') || 'likes';

    let actionsHtml = '';
    if (returnTo === 'matches') {
        actionsHtml = `
            <div class="actions">
                <button class="back-btn" onclick="backToMatches()">🔙 Назад</button>
            </div>
        `;
    } else {
        const likedUsers = JSON.parse(localStorage.getItem('liked_users') || '[]');
        const alreadyLiked = likedUsers.includes(tg_id);
        const contactHtml = alreadyLiked
            ? `<div class="contact"><a href="${telegramLink}" target="_blank">✉️ Написать в Telegram</a></div>`
            : '';

        actionsHtml = `
            ${contactHtml}
            <div class="actions">
                <button class="like-btn" onclick="replyFromProfile(${data.tg_id})">❤️ Лайк</button>
                <button class="skip-btn" onclick="skipFromProfile(${data.tg_id})">⏭ Пропуск</button>
                <button class="back-btn" onclick="backToLikes()">🔙 Назад</button>
            </div>
        `;
    }

    content.innerHTML = `
        <div class="card">
            <div class="card-image" style="background-image: url('${photoUrl}'); height:300px; background-size:cover;"></div>
            <div class="name-age">${data.name}, ${data.age} ${data.is_verified ? '✅' : ''}</div>
            <div class="city">📍 ${data.city || '—'}</div>
            ${data.height ? `<div class="height">📏 ${data.height} см</div>` : ''}
            <div class="goal">🎯 ${data.goal || 'не указана'}</div>
            <div class="tags">${(data.tags||[]).map(t=>`<span class="tag">#${t}</span>`).join('')}</div>
            <div class="bio">${data.bio || ''}</div>
            ${actionsHtml}
        </div>
    `;
}

function backToMatches() {
    localStorage.removeItem('return_to');
    window.location.hash = '#matches';
}

async function skipFromProfile(tg_id) {
    const returnTo = localStorage.getItem('return_to') || 'likes';
    if (returnTo === 'matches') {
        backToMatches();
    } else {
        backToLikes();
    }
    const like_id = localStorage.getItem('current_like_id');
    if (like_id) {
        await apiCall(`/incoming_likes/${like_id}`, 'DELETE');
        localStorage.removeItem('current_like_id');
    }
    let likedUsers = JSON.parse(localStorage.getItem('liked_users') || '[]');
    likedUsers = likedUsers.filter(id => id != tg_id);
    localStorage.setItem('liked_users', JSON.stringify(likedUsers));
    backToLikes();
}

async function replyFromProfile(to_tg_id) {
    const response = await apiCall('/like', 'POST', {
        from_user_id: user.id,
        to_user_id: to_tg_id,
        type: 'like'
    });
    if (response.already_match) {
        tg.showAlert('💞 У вас уже взаимная симпатия! Напишите ему в разделе «Матчи».');
        return;
    }
    if (response && response.is_match) {
        tg.showAlert('🎉 У вас взаимная симпатия!');
        const like_id = localStorage.getItem('current_like_id');
        if (like_id) {
            await apiCall(`/incoming_likes/${like_id}`, 'DELETE');
            localStorage.removeItem('current_like_id');
        }
        let likedUsers = JSON.parse(localStorage.getItem('liked_users') || '[]');
        if (!likedUsers.includes(to_tg_id)) {
            likedUsers.push(to_tg_id);
            localStorage.setItem('liked_users', JSON.stringify(likedUsers));
        }
        setTimeout(() => backToLikes(), 500);
    } else {
        const returnTo = localStorage.getItem('return_to') || 'likes';
        if (returnTo === 'matches') {
            backToMatches();
        } else {
            backToLikes();
        }
        tg.showAlert('❤️ Лайк отправлен!');
        const like_id = localStorage.getItem('current_like_id');
        if (like_id) {
            await apiCall(`/incoming_likes/${like_id}`, 'DELETE');
            localStorage.removeItem('current_like_id');
        }
        backToLikes();
    }
}

function backToLikes() {
    localStorage.removeItem('return_to');
    window.location.hash = '#incoming_likes';
}

function navigateTo(hash) {
    closeFilters();
    if (hash.startsWith('#profile/')) {
        const tg_id = hash.split('/')[1];
        currentPage = 'profile_view';
        showForeignProfile(tg_id);
        return;
    }
    currentPage = hash.slice(1) || 'feed';
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === currentPage);
    });
    if (currentPage === 'feed') loadFeed();
    else if (currentPage === 'likes' || currentPage === 'incoming_likes') loadLikes();
    else if (currentPage === 'matches') loadMatches();
    else if (currentPage === 'events') loadEvents();
    else if (currentPage === 'profile') loadMyProfile();
    else loadFeed();
}

function toggleFilters() {
    if (document.getElementById('filterPanel')) {
        closeFilters();
        return;
    }
    const panel = document.createElement('div');
    panel.id = 'filterPanel';
    panel.style.cssText = `
        position: fixed; top: 60px; left: 0; right: 0;
        background: var(--tg-theme-secondary-bg-color, #1e1e1e);
        padding: 20px; border-radius: 0 0 20px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3); z-index: 200;
        display: flex; flex-direction: column; gap: 16px;
        max-height: 80vh; overflow-y: auto;
    `;

    let interestsHtml = '';
    ALL_INTERESTS.forEach(interest => {
        const isSelected = currentFilters.interests.includes(interest);
        interestsHtml += `<button class="interest-btn ${isSelected ? 'selected' : ''}" data-interest="${interest}">#${interest}</button>`;
    });

    panel.innerHTML = `
        <h3 style="margin:0;">🔍 Настройки поиска</h3>

        <div>
            <label>👫 Кто:</label>
            <select id="filterGender" style="width:100%; padding:10px; border-radius:12px; margin-top:5px;">
                <option value="all" ${currentFilters.gender === 'all' ? 'selected' : ''}>Все</option>
                <option value="M" ${currentFilters.gender === 'M' ? 'selected' : ''}>Мужчины</option>
                <option value="F" ${currentFilters.gender === 'F' ? 'selected' : ''}>Женщины</option>
            </select>
        </div>

        <div>
            <label>🎯 Цель:</label>
            <select id="filterGoal" style="width:100%; padding:10px; border-radius:12px; margin-top:5px;">
                <option value="" ${!currentFilters.goal ? 'selected' : ''}>Любая</option>
                <option value="relationship" ${currentFilters.goal === 'relationship' ? 'selected' : ''}>Отношения 🥰</option>
                <option value="friendship" ${currentFilters.goal === 'friendship' ? 'selected' : ''}>Дружба 🤝</option>
                <option value="night" ${currentFilters.goal === 'night' ? 'selected' : ''}>Провести ночь 🔞</option>
            </select>
        </div>

        <div>
            <label>📏 Желаемый рост (см):</label>
            <div style="display:flex; gap:10px; margin-top:5px;">
                <input type="checkbox" id="applyHeight" ${currentFilters.apply_height ? 'checked' : ''}> Применить
                <input type="number" id="searchHeight" value="${currentFilters.search_height || ''}" placeholder="175" style="flex:1; padding:10px; border-radius:12px;">
            </div>
            <small style="color:#888;">Будет показывать ±5 см, потом уберём этот фильтр</small>
        </div>

        <div>
            <label>🏷️ Интересы (можно выбрать несколько):</label>
            <div id="interestsContainer" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:10px;">
                ${interestsHtml}
            </div>
            <small style="color:#888;">Нажмите на интерес, чтобы добавить/убрать</small>
        </div>

        <div style="display:flex; gap:12px; margin-top:8px;">
            <button id="applyFilterBtn" style="flex:1; background:#00d4ff; border:none; border-radius:30px; padding:12px; font-weight:bold;">🔍 Искать</button>
            <button id="closeFilterBtn" style="flex:1; background:#2a2a2a; border:none; border-radius:30px; padding:12px; color:#fff;">✖️ Закрыть</button>
        </div>
    `;
    document.body.appendChild(panel);

    document.querySelectorAll('.interest-btn').forEach(btn => {
        btn.onclick = () => {
            btn.classList.toggle('selected');
        };
    });

    document.getElementById('applyFilterBtn').onclick = () => applyFilters();
    document.getElementById('closeFilterBtn').onclick = () => closeFilters();
}

function closeFilters() {
    document.getElementById('filterPanel')?.remove();
}

async function applyFilters() {
    const applyHeight = document.getElementById('applyHeight').checked;
    let searchHeight = null;
    if (applyHeight) {
        const rawHeight = parseInt(document.getElementById('searchHeight').value);
        if (!isNaN(rawHeight) && rawHeight >= 100 && rawHeight <= 250) {
            searchHeight = rawHeight;
        }
    }
    const selectedInterests = [];
    document.querySelectorAll('.interest-btn.selected').forEach(btn => {
        selectedInterests.push(btn.dataset.interest);
    });

    currentFilters = {
        gender: document.getElementById('filterGender').value,
        goal: document.getElementById('filterGoal').value || null,
        interests: selectedInterests,
        apply_height: applyHeight,
        search_height: searchHeight
    };
    closeFilters();
//    feedData = [];
//    feedIndex = 0;
    await loadFeed();
}

async function loadFeed() {
    const content = document.getElementById('content');
    content.innerHTML = '<p>Загрузка...</p>';

    const params = new URLSearchParams();
    params.append('tg_id', user.id);
    params.append('limit', 1);
    params.append('gender', currentFilters.gender);
    if (currentFilters.goal) params.append('search_goal', currentFilters.goal);
    if (currentFilters.apply_height && currentFilters.search_height) {
        params.append('apply_height', currentFilters.apply_height);
        params.append('search_height', currentFilters.search_height);
    }
    if (currentFilters.interests.length) {
        params.append('search_interests', currentFilters.interests.join(','));
    }

    const resp = await fetch(`/api/feed?${params.toString()}`);
    const data = await resp.json();
    if (!data.profiles || data.profiles.length === 0) {
        content.innerHTML = '<p>😔 Анкеты закончились. Измените фильтры. Анкеты обновятся через 1 час!</p>';
        return;
    }

    const p = data.profiles[0];
    currentProfileId = p.id;
    const photoUrl = p.photos?.[0]?.file_id
        ? `/api/photo/${p.photos[0].file_id}`
        : 'https://placehold.co/300x300?text=Нет+фото';
    content.innerHTML = `
        <div class="card">
            <div class="card-image" style="background-image: url('${photoUrl}'); height:300px; background-size:cover; background-position:center;"></div>
            <div class="name-age">${p.name}, ${p.age} ${p.is_verified ? '✅' : ''} ${p.has_premium ? '⭐' : ''}</div>
            <div class="city">📍 ${p.city || '—'}</div>
            ${p.height ? `<div class="height">📏 ${p.height} см</div>` : ''}
            <div class="goal">🎯 ${p.goal || 'не указана'}</div>
            <div class="tags">${(p.tags||[]).map(t=>`<span class="tag">#${t}</span>`).join('')}</div>
            <div class="bio">${p.bio || ''}</div>
            <div class="actions">
                ${prevProfileId ? `<button class="undo-btn" onclick="undoSkip()">↩️ Вернуться</button>` : ''}
                <button class="like-btn" onclick="likeProfile(${p.tg_id})">❤️ Лайк</button>
                <button class="super-btn" onclick="superLike(${p.tg_id})">⭐ Супер</button>
                <button class="skip-btn" onclick="skipProfile(${p.id})">⏭ Пропуск</button>
            </div>
        </div>
    `;
}

async function showProfileById(profileId) {
    const content = document.getElementById('content');
    content.innerHTML = '<p>Загрузка...</p>';

    const profile = await apiCall(`/profile_by_id/${profileId}`);

    if (!profile) {
        content.innerHTML = '<p>❌ Профиль не найден</p>';
        return;
    }

    currentProfileId = profile.id;

    const photoUrl = profile.photos?.[0]?.file_id
        ? `/api/photo/${profile.photos[0].file_id}`
        : 'https://placehold.co/300x300?text=Нет+фото';

    content.innerHTML = `
        <div class="card">
            <div class="card-image" style="background-image: url('${photoUrl}'); height:300px; background-size:cover; background-position:center;"></div>
            <div class="name-age">${profile.name}, ${profile.age} ${profile.is_verified ? '✅' : ''} ${profile.has_premium ? '⭐' : ''}</div>
            <div class="city">📍 ${profile.city || '—'}</div>
            ${profile.height ? `<div class="height">📏 ${profile.height} см</div>` : ''}
            <div class="goal">🎯 ${profile.goal || 'не указана'}</div>
            <div class="tags">${(profile.tags||[]).map(t=>`<span class="tag">#${t}</span>`).join('')}</div>
            <div class="bio">${profile.bio || ''}</div>
            <div class="actions">
                <button class="like-btn" onclick="likeProfile(${profile.tg_id})">❤️ Лайк</button>
                <button class="super-btn" onclick="superLike(${profile.tg_id})">⭐ Супер</button>
                <button class="skip-btn" onclick="skipProfile(${profile.id})">⏭ Пропуск</button>
            </div>
        </div>
    `;
}

async function undoSkip() {
    if (!prevProfileId) {
        tg.showAlert('❌ Нет предыдущей анкеты');
        return;
    }

    const me = await apiCall('/premium/status');
    if (me) {
        user.has_premium = me.has_premium;
    }

    if (!user.has_premium) {
        tg.showAlert('🔒 Возврат к анкете доступен только с премиум-подпиской');
        return;
    }

    const response = await apiCall('/undo_skip', 'POST');
    if (response && response.success) {
        await showProfileById(response.profile_id);
        tg.showAlert('✅ Анкета возвращена!');
    } else if (response && response.detail === "Premium required") {
        tg.showAlert('⭐ Требуется премиум-подписка для возврата анкеты');
    } else {
        tg.showAlert('❌ Не удалось вернуть анкету');
    }
}

async function likeProfile(tg_id) {
    prevProfileId = currentProfileId;
    await apiCall(`/viewed/${currentProfileId}`, 'POST');
    const response = await apiCall('/like', 'POST', { from_user_id: user.id, to_user_id: tg_id, type: 'like' });
    if (response && response.already_match) {
        tg.showAlert('💞 У вас уже взаимная симпатия! Напишите ему в разделе «Матчи».');
    } else {
        tg.showAlert('❤️ Лайк!');
    }
    await loadFeed();
}

async function superLike(id) {
    prevProfileId = currentProfileId;
    await apiCall(`/viewed/${currentProfileId}`, 'POST');
    const response = await apiCall('/like', 'POST', { from_user_id: user.id, to_user_id: id, type: 'super' });
    if (response?.limit_reached) {
        tg.showAlert('⭐ Суперлайк уже использован сегодня');
    } else {
        tg.showAlert('⭐ Суперлайк!');
    }
    await loadFeed();
}

async function skipProfile(id) {
    prevProfileId = currentProfileId;
    await apiCall(`/viewed/${id}`, 'POST');
    await loadFeed();
}

async function apiCall(endpoint, method = 'GET', body = null) {
    let url = `/api${endpoint}`;
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (body) opts.body = JSON.stringify(body);

    const separator = url.includes('?') ? '&' : '?';
    url += `${separator}tg_id=${user.id}`;

    const resp = await fetch(url, opts);
    if (!resp.ok) {
        console.error('API error', resp.status, await resp.text());
        return null;
    }
    return await resp.json();
}

async function loadLikes() {
    const content = document.getElementById('content');
    content.innerHTML = '<p>Загрузка...</p>';
    const data = await apiCall('/incoming_likes');
    if (!data.likes || data.likes.length === 0) {
        content.innerHTML = '<p>😔 Никто не лайкнул вас пока.</p>';
        return;
    }
    let html = '';
    for (const like of data.likes) {
        const u = like.user;
        html += `
            <div class="card" onclick="showProfileFromLike(${u.tg_id}, ${like.like_id})" style="cursor:pointer;">
                <div class="name-age">${u.name}, ${u.age}</div>
                <div class="city">📍 ${u.city}</div>
            </div>
        `;
    }
    content.innerHTML = html;
}

async function showProfileFromLike(tg_id, like_id) {
    localStorage.setItem('current_like_id', like_id);
    localStorage.setItem('return_to', 'likes');
    window.location.hash = `profile/${tg_id}`;
}

async function replyLike(id) {
    await apiCall(`/reply_like?like_id=${id}&tg_id=${user.id}`, 'POST');
    tg.showAlert('❤️ Ответ отправлен');
    loadLikes();
}

async function loadEvents() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="card">
            <p>👥 Функция «Найти компанию» временно доступна только в боте.</p>
            <button onclick="openBot()">📱 Открыть бота</button>
        </div>
    `;
}

function createEvent() { alert('Функция в разработке'); }
function contactEventCreator(id) { alert('Функция в разработке'); }

async function loadMyProfile() {
    const data = await apiCall('/me');
    const photoUrl = data.photos?.[0]?.file_id
        ? `/api/photo/${data.photos[0].file_id}`
        : 'https://placehold.co/300x300?text=Нет+фото';

    document.getElementById('content').innerHTML = `
        <div class="card">
            <div class="card-image" style="background-image: url('${photoUrl}'); height:300px; background-size:cover; background-position:center;"></div>
            <div class="name-age">${data.name}, ${data.age} ${data.is_verified ? '✅' : ''} ${data.has_premium ? '⭐' : ''}</div>
            <div class="city">📍 ${data.city || '—'}</div>
            ${data.height ? `<div class="height">📏 ${data.height} см</div>` : ''}
            <div class="goal">🎯 ${data.goal || 'не указана'}</div>
            ${data.tags && data.tags.length ? `<div class="tags">${data.tags.map(t => `<span class="tag">#${t}</span>`).join('')}</div>` : ''}
            <div class="bio">${data.bio || ''}</div>
            <div class="actions">
                <button onclick="openBot()">📱 Редактировать</button>
                <button onclick="showThemeSelector()">🎨 Выбрать тему</button>
            </div>
        </div>
    `;
}

function openCompanyMode() {
    window.open('https://t.me/GAZznakomitsya_bot?start=company', '_blank');
}

function openBot() {
    window.open('https://t.me/GAZznakomitsya_bot?start=profile', '_blank');
}

// Тематические настройки — полная смена атмосферы
const THEMES = {
    cyberpunk: {
        name: '🌆 Киберпанк',
        css: `
            --cyan: #00ffe7;
            --green: #39ff14;
            --magenta: #ff00c8;
            --violet: #7b00ff;
            --gold: #ffd60a;
            --void: #020509;
            --void2: #05080f;
            --panel: #070c18;
            --panel2: #0b1120;
            --seam: rgba(0, 255, 231, 0.25);
            --seam-green: rgba(57, 255, 20, 0.2);
            --text-hi: #d4f5ff;
            --text-lo: #3a5060;
        `,
        // Градиенты неба и звёзд для этой темы
        nebula: `
            radial-gradient(ellipse 90% 55% at 50% -5%,  rgba(0,255,231,0.2) 0%, transparent 55%),
            radial-gradient(ellipse 70% 45% at 100% 100%, rgba(57,255,20,0.15) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 0% 70%, rgba(123,0,255,0.12) 0%, transparent 50%),
            radial-gradient(ellipse 50% 30% at 80% 20%, rgba(255,0,200,0.1) 0%, transparent 45%)
        `,
        stars: `
            radial-gradient(1px 1px at 8% 15%, rgba(255,255,255,0.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 22% 72%, rgba(0,255,231,0.7) 0%, transparent 100%),
            radial-gradient(2px 2px at 37% 8%, rgba(255,255,255,0.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 53% 88%, rgba(57,255,20,0.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 68% 32%, rgba(255,255,255,0.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 83% 60%, rgba(0,255,231,0.5) 0%, transparent 100%),
            radial-gradient(2px 2px at 91% 12%, rgba(255,255,255,0.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 4% 95%, rgba(57,255,20,0.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 61% 45%, rgba(123,0,255,0.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 76% 82%, rgba(255,255,255,0.6) 0%, transparent 100%)
        `
    },
    sakura: {
        name: '🌸 Сакура / Аниме',
        css: `
            --cyan: #ff9acb;
            --green: #ffb7d2;
            --magenta: #ff4d8c;
            --violet: #c1548c;
            --gold: #ffde9e;
            --void: #1e0b1a;
            --void2: #2d1225;
            --panel: #2a1422;
            --panel2: #3b1c2e;
            --seam: rgba(255, 105, 180, 0.35);
            --seam-green: rgba(255, 183, 210, 0.25);
            --text-hi: #fff0f5;
            --text-lo: #b87c9c;
        `,
        nebula: `
            radial-gradient(ellipse 90% 55% at 50% -5%, rgba(255,105,180,0.2) 0%, transparent 55%),
            radial-gradient(ellipse 70% 45% at 100% 100%, rgba(255,183,210,0.15) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 0% 70%, rgba(193,84,140,0.12) 0%, transparent 50%),
            radial-gradient(ellipse 50% 30% at 80% 20%, rgba(255,77,140,0.1) 0%, transparent 45%)
        `,
        stars: `
            radial-gradient(1px 1px at 8% 15%, rgba(255,240,245,0.9) 0%, transparent 100%),
            radial-gradient(2px 2px at 22% 72%, rgba(255,154,203,0.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 37% 8%, rgba(255,240,245,0.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 53% 88%, rgba(255,183,210,0.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 68% 32%, rgba(255,240,245,0.7) 0%, transparent 100%),
            radial-gradient(2px 2px at 83% 60%, rgba(255,154,203,0.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 4% 95%, rgba(255,183,210,0.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 61% 45%, rgba(193,84,140,0.6) 0%, transparent 100%)
        `
    },
    acid: {
        name: '🧪 Кислотная зелень',
        css: `
            --cyan: #00ff88;
            --green: #ccff00;
            --magenta: #ff007f;
            --violet: #aa00ff;
            --gold: #ffee00;
            --void: #0a1a0a;
            --void2: #0f2a0f;
            --panel: #0d2012;
            --panel2: #1a381a;
            --seam: rgba(0, 255, 136, 0.4);
            --seam-green: rgba(204, 255, 0, 0.3);
            --text-hi: #e0ffe0;
            --text-lo: #6aaa6a;
        `,
        nebula: `
            radial-gradient(ellipse 90% 55% at 50% -5%, rgba(0,255,136,0.25) 0%, transparent 55%),
            radial-gradient(ellipse 70% 45% at 100% 100%, rgba(204,255,0,0.2) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 0% 70%, rgba(170,0,255,0.1) 0%, transparent 50%),
            radial-gradient(ellipse 50% 30% at 80% 20%, rgba(255,0,127,0.08) 0%, transparent 45%)
        `,
        stars: `
            radial-gradient(1px 1px at 8% 15%, rgba(224,255,224,0.9) 0%, transparent 100%),
            radial-gradient(2px 2px at 22% 72%, rgba(0,255,136,0.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 37% 8%, rgba(204,255,0,0.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 53% 88%, rgba(0,255,136,0.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 68% 32%, rgba(224,255,224,0.7) 0%, transparent 100%),
            radial-gradient(2px 2px at 83% 60%, rgba(204,255,0,0.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 4% 95%, rgba(0,255,136,0.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 61% 45%, rgba(170,0,255,0.4) 0%, transparent 100%)
        `
    },
    prism: {
        name: '🌈 Призма / Градиент',
        css: `
            --cyan: #00f0ff;
            --green: #7aff7a;
            --magenta: #ff66cc;
            --violet: #b266ff;
            --gold: #ffdd66;
            --void: #0b0b1a;
            --void2: #12122b;
            --panel: #151530;
            --panel2: #1e1e40;
            --seam: linear-gradient(45deg, #ff66cc, #7aff7a, #00f0ff);
            --seam-green: rgba(122, 255, 122, 0.2);
            --text-hi: #ffffff;
            --text-lo: #b0b0e0;
        `,
        nebula: `
            radial-gradient(ellipse 90% 55% at 50% -5%, rgba(0,240,255,0.2) 0%, transparent 55%),
            radial-gradient(ellipse 70% 45% at 100% 100%, rgba(122,255,122,0.15) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 0% 70%, rgba(178,102,255,0.12) 0%, transparent 50%),
            radial-gradient(ellipse 50% 30% at 80% 20%, rgba(255,102,204,0.1) 0%, transparent 45%)
        `,
        stars: `
            radial-gradient(1px 1px at 8% 15%, rgba(255,255,255,0.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 22% 72%, rgba(0,240,255,0.7) 0%, transparent 100%),
            radial-gradient(2px 2px at 37% 8%, rgba(122,255,122,0.8) 0%, transparent 100%),
            radial-gradient(1px 1px at 53% 88%, rgba(178,102,255,0.6) 0%, transparent 100%),
            radial-gradient(1px 1px at 68% 32%, rgba(255,255,255,0.7) 0%, transparent 100%),
            radial-gradient(1px 1px at 83% 60%, rgba(255,102,204,0.5) 0%, transparent 100%),
            radial-gradient(2px 2px at 91% 12%, rgba(122,255,122,0.9) 0%, transparent 100%),
            radial-gradient(1px 1px at 4% 95%, rgba(0,240,255,0.5) 0%, transparent 100%),
            radial-gradient(1px 1px at 61% 45%, rgba(255,102,204,0.6) 0%, transparent 100%)
        `
    },
    graphite: {
        name: '⚫ Графит (тёмный)',
        css: `
            --cyan: #708090;
            --green: #a9a9a9;
            --magenta: #808080;
            --violet: #696969;
            --gold: #d3d3d3;
            --void: #121212;
            --void2: #1e1e1e;
            --panel: #2a2a2a;
            --panel2: #333333;
            --seam: rgba(160, 160, 160, 0.2);
            --seam-green: rgba(180, 180, 180, 0.15);
            --text-hi: #f5f5f5;
            --text-lo: #909090;
        `,
        nebula: `
            radial-gradient(ellipse 90% 55% at 50% -5%, rgba(128,128,128,0.15) 0%, transparent 55%),
            radial-gradient(ellipse 70% 45% at 100% 100%, rgba(160,160,160,0.1) 0%, transparent 50%),
            radial-gradient(ellipse 60% 40% at 0% 70%, rgba(105,105,105,0.08) 0%, transparent 50%),
            radial-gradient(ellipse 50% 30% at 80% 20%, rgba(180,180,180,0.05) 0%, transparent 45%)
        `,
        stars: `
            radial-gradient(1px 1px at 8% 15%, rgba(245,245,245,0.3) 0%, transparent 100%),
            radial-gradient(1px 1px at 22% 72%, rgba(128,128,128,0.4) 0%, transparent 100%),
            radial-gradient(2px 2px at 37% 8%, rgba(245,245,245,0.2) 0%, transparent 100%),
            radial-gradient(1px 1px at 53% 88%, rgba(160,160,160,0.3) 0%, transparent 100%),
            radial-gradient(1px 1px at 68% 32%, rgba(245,245,245,0.25) 0%, transparent 100%),
            radial-gradient(1px 1px at 83% 60%, rgba(128,128,128,0.35) 0%, transparent 100%),
            radial-gradient(1px 1px at 4% 95%, rgba(160,160,160,0.2) 0%, transparent 100%),
            radial-gradient(1px 1px at 61% 45%, rgba(105,105,105,0.3) 0%, transparent 100%)
        `
    }
};

// Функция обновления фоновых эффектов (небо, звёзды)
function updateBackgroundEffects(themeName) {
    const theme = THEMES[themeName];
    if (!theme) return;

    // Обновляем body::before (туманности)
    let styleTag = document.getElementById('dynamic-nebula');
    if (!styleTag) {
        styleTag = document.createElement('style');
        styleTag.id = 'dynamic-nebula';
        document.head.appendChild(styleTag);
    }
    styleTag.textContent = `
        body::before {
            background: ${theme.nebula}, var(--void) !important;
        }
        #app::before {
            background-image: ${theme.stars} !important;
        }
    `;

    // Для градиентной темы особый border
    if (themeName === 'prism') {
        const seamGradient = "linear-gradient(45deg, #ff66cc, #7aff7a, #00f0ff)";
        document.documentElement.style.setProperty('--seam', seamGradient);
    } else {
        // Возвращаем обычный цвет для других тем
        document.documentElement.style.setProperty('--seam', theme.css.match(/--seam:\s*([^;]+)/)?.[1] || 'rgba(0, 255, 231, 0.18)');
    }
}

// Функция показа панели выбора темы
function showThemeSelector() {
    if (document.getElementById('themePanel')) return;

    const panel = document.createElement('div');
    panel.id = 'themePanel';
    panel.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: var(--panel);
        border: 1px solid var(--seam);
        border-radius: 12px;
        padding: 20px;
        z-index: 1000;
        min-width: 260px;
        box-shadow: 0 0 40px rgba(0,0,0,0.5);
        backdrop-filter: blur(20px);
        animation: fadeInScale 0.2s ease-out;
    `;

    let themesHtml = '';
    for (const [key, theme] of Object.entries(THEMES)) {
        const isActive = currentTheme === key;
        themesHtml += `
            <button
                onclick="selectTheme('${key}')"
                style="
                    display: block;
                    width: 100%;
                    margin: 8px 0;
                    padding: 12px;
                    background: ${isActive ? 'var(--seam)' : 'transparent'};
                    border: 1px solid var(--seam);
                    border-radius: 8px;
                    color: var(--text-hi);
                    cursor: pointer;
                    transition: all 0.2s;
                    font-family: var(--mono);
                    font-size: 14px;
                "
                onmouseover="this.style.transform='scale(1.02)'"
                onmouseout="this.style.transform='scale(1)'"
            >
                ${theme.name} ${isActive ? ' ✓' : ''}
            </button>
        `;
    }

    panel.innerHTML = `
        <h3 style="margin: 0 0 15px 0; text-align: center;">🎨 Выбери тему</h3>
        ${themesHtml}
        <button
            onclick="closeThemeSelector()"
            style="
                display: block;
                width: 100%;
                margin-top: 12px;
                padding: 10px;
                background: rgba(255,255,255,0.1);
                border: 1px solid var(--seam);
                border-radius: 8px;
                color: var(--text-lo);
                cursor: pointer;
                font-family: var(--mono);
                font-size: 12px;
            "
        >
            ✖️ Закрыть
        </button>
    `;

    document.body.appendChild(panel);
}

function closeThemeSelector() {
    document.getElementById('themePanel')?.remove();
}

function selectTheme(themeName) {
    applyTheme(themeName);
    closeThemeSelector();
    tg.showAlert(`🎨 Тема "${THEMES[themeName].name}" применена!`);
    // Обновить текущую страницу, чтобы перерисовать кнопки с новыми цветами
    if (currentPage === 'profile') loadMyProfile();
    else if (currentPage === 'feed') loadFeed();
}

// Функция применения темы (переопределена)
function applyTheme(themeName) {
    const theme = THEMES[themeName];
    if (!theme) return;

    const root = document.documentElement;
    const cssVars = theme.css;

    // Применяем CSS переменные
    const lines = cssVars.split('\n');
    for (const line of lines) {
        const match = line.match(/^(\s*--[\w-]+):\s*(.+);?$/);
        if (match) {
            const varName = match[1].trim();
            let varValue = match[2].trim().replace(/;$/, '');
            root.style.setProperty(varName, varValue);
        }
    }

    // Обновляем фоновые эффекты
    updateBackgroundEffects(themeName);

    currentTheme = themeName;
    localStorage.setItem('theme', themeName);

    // Небольшая анимация перехода
    document.body.style.transition = 'background 0.4s ease';
    setTimeout(() => {
        document.body.style.transition = '';
    }, 400);
}

applyTheme(currentTheme);

init();
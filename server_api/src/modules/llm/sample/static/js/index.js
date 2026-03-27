    const chatBox = document.getElementById('chat-box');
    const messageInput = document.getElementById('messageInput');
    const welcomeScreen = document.getElementById('welcome-screen');
    const themeSelect = document.getElementById('themeSelect');
    const providerSelect = document.getElementById('providerSelect');
    const empathySelect = document.getElementById('empathySelect');
    const webSearchToggle = document.getElementById('webSearchToggle');
    const ttsToggle = document.getElementById('ttsToggle');
    const newChatBtn = document.getElementById('newChatBtn');
    const railMenuBtn = document.getElementById('railMenuBtn');
    const railNewChatBtn = document.getElementById('railNewChatBtn');
    const railSettingsBtn = document.getElementById('railSettingsBtn');
    const railSettingsPopover = document.getElementById('railSettingsPopover');
    const quickThemeSelect = document.getElementById('quickThemeSelect');
    const quickProviderSelect = document.getElementById('quickProviderSelect');
    const quickWebSearchToggle = document.getElementById('quickWebSearchToggle');
    const quickTtsToggle = document.getElementById('quickTtsToggle');
    const quickSttToggle = document.getElementById('quickSttToggle');
    const quickOpenSidebarBtn = document.getElementById('quickOpenSidebarBtn');
    const settingsToggleBtn = document.getElementById('settingsToggleBtn');
    const settingsPanel = document.getElementById('settingsPanel');
    const micBtn = document.getElementById('micBtn');
    const stopTtsBtn = document.getElementById('stopTtsBtn');
    const sttToggle = document.getElementById('sttToggle');
    const topicHistoryEl = document.getElementById('topicHistory');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    const sidebarContainer = document.getElementById('sidebarContainer');
    const sidebar = document.querySelector('.sidebar');
    let touchStartX = 0;
    let touchEndX = 0;
    const CHAT_TOPICS_KEY = 'bao_chat_topics';
    const CHAT_TOPICS_LIMIT = 20;
    const EMPATHY_LEVEL_KEY = 'bao_empathy_level';
    const STT_ENABLED_KEY = 'bao_stt_enabled';
    const TTS_MODE_KEY = 'bao_tts_mode';
    const IMAGE_INTENT_KEYWORDS = [
        '이미지', '그림', '일러스트', '포스터', '배경화면', '사진',
        'image', 'picture', 'illustration', 'poster',
    ];
    const IMAGE_INTENT_ACTIONS = [
        '만들어', '생성', '그려', '그려줘', '제작', '뽑아', '보여줘', '올려줘',
        'generate', 'create', 'draw', 'make',
    ];

    let mediaRecorder = null;
    let currentMicStream = null;
    let audioChunks = [];
    let currentTtsAudio = null;
    let ttsQueue = Promise.resolve();
    let ttsSessionToken = 0;
    let ttsMode = localStorage.getItem(TTS_MODE_KEY) || 'server';
    let sttAudioContext = null;
    let sttAnalyser = null;
    let sttMonitorId = null;
    let sttLastVoiceAt = 0;
    let sttRecordStartedAt = 0;
    let chatTopics = [];
    let activeTopicId = null;
    let sttEnabled = true;
    let skipNextStt = false;
    let activeChatController = null;
    let chatSessionToken = 0;
    let citationModal = null;
    let citationModalList = null;
    let citationAnchorButton = null;
    let citationCloseTimer = null;

    function isTtsActive() {
        return !!currentTtsAudio || ('speechSynthesis' in window && window.speechSynthesis.speaking);
    }

    function syncTtsStopButton() {
        if (!stopTtsBtn) return;
        const active = isTtsActive();
        stopTtsBtn.disabled = !active;
        stopTtsBtn.classList.toggle('stt-off', !active);
    }

    function stopSpeech() {
        ttsSessionToken += 1;
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        if (currentTtsAudio) {
            currentTtsAudio.pause();
            currentTtsAudio.src = '';
            currentTtsAudio = null;
        }
        ttsQueue = Promise.resolve();
        syncTtsStopButton();
    }

    function stopActiveChat() {
        if (activeChatController) {
            activeChatController.abort();
            activeChatController = null;
        }
    }

    function stopSttMonitoring() {
        if (sttMonitorId) {
            cancelAnimationFrame(sttMonitorId);
            sttMonitorId = null;
        }
        if (sttAudioContext) {
            sttAudioContext.close();
            sttAudioContext = null;
        }
        sttAnalyser = null;
        sttLastVoiceAt = 0;
        sttRecordStartedAt = 0;
    }

    function startSttMonitoring(stream) {
        stopSttMonitoring();
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;

        sttAudioContext = new AudioCtx();
        const source = sttAudioContext.createMediaStreamSource(stream);
        sttAnalyser = sttAudioContext.createAnalyser();
        sttAnalyser.fftSize = 1024;
        source.connect(sttAnalyser);
        const data = new Uint8Array(sttAnalyser.frequencyBinCount);
        sttLastVoiceAt = Date.now();

        const monitor = () => {
            if (!mediaRecorder || mediaRecorder.state !== 'recording' || !sttAnalyser) return;
            sttAnalyser.getByteFrequencyData(data);
            let sum = 0;
            for (let i = 0; i < data.length; i += 1) sum += data[i];
            const avg = sum / data.length;
            if (avg > 10) {
                sttLastVoiceAt = Date.now();
            } else if (
                Date.now() - sttLastVoiceAt > 1400 &&
                Date.now() - sttRecordStartedAt > 1200
            ) {
                mediaRecorder.stop();
                return;
            }
            sttMonitorId = requestAnimationFrame(monitor);
        };
        sttMonitorId = requestAnimationFrame(monitor);
    }

    function stopRecording(discard = false) {
        if (!mediaRecorder) return;
        if (discard) skipNextStt = true;
        if (mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
        stopSttMonitoring();
        if (currentMicStream) {
            currentMicStream.getTracks().forEach(track => track.stop());
            currentMicStream = null;
        }
        micBtn.classList.remove('recording');
    }

    function stopAllVoice(discardRecording = true) {
        stopSpeech();
        stopActiveChat();
        stopRecording(discardRecording);
        chatSessionToken += 1;
    }

    function setSttEnabled(enabled) {
        sttEnabled = !!enabled;
        if (sttToggle) {
            sttToggle.checked = sttEnabled;
        }
        if (quickSttToggle) {
            quickSttToggle.checked = sttEnabled;
        }
        if (micBtn) {
            micBtn.disabled = !sttEnabled;
            micBtn.classList.toggle('stt-off', !sttEnabled);
            micBtn.title = sttEnabled ? '음성 입력' : '음성 인식 OFF';
        }
        if (!sttEnabled) {
            stopRecording(true);
        }
        localStorage.setItem(STT_ENABLED_KEY, sttEnabled ? 'true' : 'false');
    }

    function applyTheme(theme) {
        const selected = theme || 'light';
        document.body.setAttribute('data-theme', selected);
        if (themeSelect) {
            themeSelect.value = selected;
        }
        if (quickThemeSelect) {
            quickThemeSelect.value = selected;
        }
        localStorage.setItem('bao_theme', selected);
    }

    function applyEmpathyLevel(level) {
        const selected = level || 'balanced';
        if (empathySelect) empathySelect.value = selected;
        localStorage.setItem(EMPATHY_LEVEL_KEY, selected);
    }

    function hideWelcome() {
        if (welcomeScreen) welcomeScreen.style.display = 'none';
    }

    function showWelcome() {
        if (welcomeScreen) welcomeScreen.style.display = 'block';
    }

    function formatTime(isoText) {
        const d = new Date(isoText);
        if (Number.isNaN(d.getTime())) return '';
        return d.toLocaleString('ko-KR', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    function normalizeTopic(text) {
        return (text || '').replace(/\s+/g, ' ').trim();
    }

    function truncateTopic(text, max = 48) {
        if (text.length <= max) return text;
        return `${text.slice(0, max)}...`;
    }

    function renderTopicHistory() {
        if (!topicHistoryEl) return;
        topicHistoryEl.innerHTML = '';

        if (!chatTopics.length) {
            const empty = document.createElement('div');
            empty.className = 'history-empty';
            empty.innerText = '아직 기록이 없습니다.';
            topicHistoryEl.appendChild(empty);
            return;
        }

        for (const item of chatTopics) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'history-item';
            btn.title = item.topic;
            const main = document.createElement('div');
            main.className = 'history-main';
            main.textContent = truncateTopic(item.topic);
            const small = document.createElement('small');
            small.textContent = formatTime(item.at);
            main.appendChild(small);
            btn.appendChild(main);

            const delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'history-delete-btn';
            delBtn.innerText = '삭제';
            delBtn.title = '이 기록 삭제';
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteSingleHistory(item.id);
            });
            btn.appendChild(delBtn);

            btn.addEventListener('click', () => {
                openTopic(item.id);
            });
            topicHistoryEl.appendChild(btn);
        }
    }


    function saveTopicHistory() {
        localStorage.setItem(CHAT_TOPICS_KEY, JSON.stringify(chatTopics));
    }


    function loadTopicHistory() {
        try {
            const raw = localStorage.getItem(CHAT_TOPICS_KEY);
            chatTopics = raw ? JSON.parse(raw) : [];
            if (!Array.isArray(chatTopics)) chatTopics = [];
        } catch (e) {
            chatTopics = [];
        }
        renderTopicHistory();
    }


    function getActiveTopic() {
        if (!activeTopicId) return null;
        return chatTopics.find((item) => item.id === activeTopicId) || null;
    }

    function createTopicIfNeeded(firstQuestion) {
        if (activeTopicId) return getActiveTopic();
        const topic = normalizeTopic(firstQuestion);
        if (!topic) return null;
        const newTopic = {
            id: `topic-${Date.now()}`,
            topic,
            at: new Date().toISOString(),
            messages: [],
        };
        chatTopics.unshift(newTopic);
        chatTopics = chatTopics.slice(0, CHAT_TOPICS_LIMIT);
        activeTopicId = newTopic.id;
        saveTopicHistory();
        renderTopicHistory();
        return newTopic;
    }

    function appendMessageToActiveTopic(role, text) {
        const topic = getActiveTopic();
        const normalized = normalizeTopic(text);
        if (!topic || !normalized) return;
        topic.messages.push({ role, text: normalized, at: new Date().toISOString() });
        topic.at = new Date().toISOString();
        saveTopicHistory();
        renderTopicHistory();
    }

    function openTopic(topicId) {
        const topic = chatTopics.find((item) => item.id === topicId);
        if (!topic) return;

        stopAllVoice(true);
        resetServerMemorySilently();
        activeTopicId = topic.id;
        chatBox.innerHTML = '';
        if (!topic.messages || !topic.messages.length) {
            if (welcomeScreen) {
                chatBox.appendChild(welcomeScreen);
            }
            showWelcome();
        } else {
            hideWelcome();
            for (const message of topic.messages) {
                const imagePayload = unpackImageHistory(message.text);
                if (message.role === 'assistant' && imagePayload && imagePayload.src) {
                    addImageMsg(imagePayload.src, imagePayload.caption, false);
                    continue;
                }
                addMsg(
                    message.role === 'assistant' ? 'ai' : 'user',
                    message.text,
                    false,
                    { editable: message.role !== 'assistant' },
                );
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        messageInput.focus();
    }

    function deleteSingleHistory(topicId) {
        stopSpeech();
        const target = chatTopics.find((item) => item.id === topicId);
        if (!target) return;

        const ok = confirm(`"${truncateTopic(target.topic, 60)}" 이 기록 삭제하시겠습니까?`);
        if (!ok) return;

        chatTopics = chatTopics.filter((item) => item.id !== topicId);
        if (activeTopicId === topicId) {
            activeTopicId = null;
            startNewChat();
        }
        saveTopicHistory();
        renderTopicHistory();
    }

    async function resetServerMemorySilently() {
        try {
            await fetch('/api/memory/reset', { method: 'POST' });
        } catch (e) {
            console.error('메모리 초기화 요청 실패:', e);
        }
    }


    function attachUserMessageActions(messageDiv, originalText) {
        const actions = document.createElement('div');
        actions.className = 'msg-actions';
        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'msg-action-btn';
        editBtn.innerText = '수정 후 재질문';
        editBtn.title = '메시지를 입력창으로 불러와 수정 후 다시 보냅니다';
        editBtn.addEventListener('click', () => {
            stopSpeech();
            messageInput.value = originalText || '';
            messageInput.focus();
            messageInput.setSelectionRange(messageInput.value.length, messageInput.value.length);
        });
        actions.appendChild(editBtn);
        messageDiv.appendChild(actions);
    }

    function ensureCitationModal() {
        if (citationModal) return;
        citationModal = document.createElement('div');
        citationModal.className = 'citation-popover';
        citationModal.innerHTML = `
            <div class="citation-popover-head">
                <strong>출처</strong>
                <button type="button" class="citation-close-btn" data-role="close" aria-label="닫기">✕</button>
            </div>
            <div class="citation-popover-body">
                <ul class="citation-list"></ul>
            </div>
        `;
        document.body.appendChild(citationModal);
        citationModalList = citationModal.querySelector('.citation-list');
        citationModal.addEventListener('click', (e) => {
            const target = e.target;
            if (target && target.dataset && target.dataset.role === 'close') {
                closeCitationModal();
            }
        });
        citationModal.addEventListener('mouseenter', () => {
            if (citationCloseTimer) {
                clearTimeout(citationCloseTimer);
                citationCloseTimer = null;
            }
        });
        citationModal.addEventListener('mouseleave', () => {
            closeCitationModal();
        });
    }

    function positionCitationPopover(anchorButton) {
        if (!citationModal || !anchorButton) return;
        const gap = 10;
        const margin = 12;
        const anchorRect = anchorButton.getBoundingClientRect();
        const popRect = citationModal.getBoundingClientRect();
        let left = anchorRect.right + gap;
        let top = anchorRect.top - 8;

        if (left + popRect.width > window.innerWidth - margin) {
            left = anchorRect.left - popRect.width - gap;
        }
        if (left < margin) {
            left = Math.max(margin, window.innerWidth - popRect.width - margin);
        }
        if (top + popRect.height > window.innerHeight - margin) {
            top = window.innerHeight - popRect.height - margin;
        }
        if (top < margin) {
            top = margin;
        }

        citationModal.style.left = `${left}px`;
        citationModal.style.top = `${top}px`;
    }

    function closeCitationModal() {
        if (citationCloseTimer) {
            clearTimeout(citationCloseTimer);
            citationCloseTimer = null;
        }
        if (!citationModal) return;
        citationModal.classList.remove('open');
        citationAnchorButton = null;
    }

    function openCitationModal(sources = [], anchorButton = null) {
        ensureCitationModal();
        if (!citationModalList) return;
        citationModalList.innerHTML = '';
        for (const source of sources) {
            const item = document.createElement('li');
            item.className = 'citation-item';
            const link = document.createElement('a');
            link.href = source.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = source.title || source.url;
            item.appendChild(link);
            citationModalList.appendChild(item);
        }
        citationModal.classList.add('open');
        citationAnchorButton = anchorButton;
        requestAnimationFrame(() => positionCitationPopover(anchorButton));
    }

    function scheduleCitationClose(delay = 120) {
        if (citationCloseTimer) {
            clearTimeout(citationCloseTimer);
        }
        citationCloseTimer = setTimeout(() => {
            closeCitationModal();
        }, delay);
    }

    function parseSourcesBlock(text) {
        const raw = text || '';
        const marker = /\[(?:sources|source|\uCD9C\uCC98)\]/i;
        const match = marker.exec(raw);
        if (!match) return { answer: raw.trim(), sources: [] };

        const answer = raw.slice(0, match.index).trim();
        const block = raw.slice(match.index + match[0].length).trim();
        const lines = block.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        const results = [];
        const seen = new Set();

        for (const line of lines) {
            const cleaned = line.replace(/^\s*(?:[-*]|\d+\.)\s*/, '').trim();
            if (!cleaned) continue;

            const mdMatches = [...cleaned.matchAll(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi)];
            for (const md of mdMatches) {
                const title = (md[1] || '').trim();
                const url = (md[2] || '').trim();
                if (!url || seen.has(url)) continue;
                seen.add(url);
                results.push({ title: title || url, url });
            }

            const plainText = cleaned.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi, ' ').trim();
            const urlMatches = [...plainText.matchAll(/https?:\/\/[^\s\])]+/gi)];
            for (const matchUrl of urlMatches) {
                const url = (matchUrl[0] || '').trim();
                if (!url || seen.has(url)) continue;
                seen.add(url);
                const title = plainText.replace(url, '').replace(/^[:\-]\s*/, '').trim() || url;
                results.push({ title, url });
            }
        }

        return { answer, sources: results };
    }

    function renderAiMessage(div, rawText) {
        if (!div._contentEl) {
            const contentEl = document.createElement('div');
            contentEl.className = 'ai-content';
            const textEl = document.createElement('div');
            textEl.className = 'ai-text';
            const citationBtn = document.createElement('button');
            citationBtn.type = 'button';
            citationBtn.className = 'citation-chip';
            citationBtn.style.display = 'none';
            citationBtn.addEventListener('mouseenter', (e) => {
                if (Array.isArray(div._sources) && div._sources.length) {
                    if (citationCloseTimer) {
                        clearTimeout(citationCloseTimer);
                        citationCloseTimer = null;
                    }
                    openCitationModal(div._sources, e.currentTarget);
                }
            });
            citationBtn.addEventListener('mouseleave', () => {
                scheduleCitationClose(140);
            });
            citationBtn.addEventListener('click', (e) => {
                if (Array.isArray(div._sources) && div._sources.length) {
                    const isSameAnchor = citationModal
                        && citationModal.classList.contains('open')
                        && citationAnchorButton === citationBtn;
                    if (isSameAnchor) {
                        closeCitationModal();
                        return;
                    }
                    openCitationModal(div._sources, e.currentTarget);
                }
            });
            contentEl.appendChild(textEl);
            contentEl.appendChild(citationBtn);
            div.appendChild(contentEl);
            div._contentEl = contentEl;
            div._textEl = textEl;
            div._citationBtn = citationBtn;
            div._sources = [];
        }

        const parsed = parseSourcesBlock(rawText);
        const text = parsed.answer || '';
        div._textEl.innerText = text || 'Thinking';
        div._sources = parsed.sources;
        if (parsed.sources.length) {
            const count = parsed.sources.length;
            div._citationBtn.innerText = `출처 ${count}개 보기`;
            div._citationBtn.style.display = 'inline-flex';
        } else {
            div._citationBtn.style.display = 'none';
        }
    }

    function addMsg(who, text, autoScroll = true, options = {}) {
        const div = document.createElement('div');
        div.className = 'message ' + who;
        if (who === 'ai') {
            renderAiMessage(div, text);
        } else {
            div.innerText = text;
        }
        if (who === 'user' && options.editable) {
            attachUserMessageActions(div, text);
        }
        chatBox.appendChild(div);
        if (autoScroll) chatBox.scrollTop = chatBox.scrollHeight;
        return div;
    }

    function addLoadingMsg(id) {
        const div = document.createElement('div');
        div.id = id;
        div.className = 'typing-container';
        div.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeLoadingMsg(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function addImageMsg(imageSrc, caption = '', autoScroll = true) {
        if (!imageSrc) return;
        const wrap = document.createElement('div');
        wrap.className = 'image-card';
        const img = document.createElement('img');
        img.src = imageSrc;
        img.alt = '생성된 이미지';
        img.loading = 'lazy';
        wrap.appendChild(img);
        if (caption) {
            const cap = document.createElement('div');
            cap.className = 'image-caption';
            cap.innerText = caption;
            wrap.appendChild(cap);
        }
        chatBox.appendChild(wrap);
        if (autoScroll) chatBox.scrollTop = chatBox.scrollHeight;
    }

    function isImageGenerationRequest(text) {
        const q = (text || '').toLowerCase().trim();
        if (!q) return false;
        const hasKeyword = IMAGE_INTENT_KEYWORDS.some((token) => q.includes(token));
        const hasAction = IMAGE_INTENT_ACTIONS.some((token) => q.includes(token));
        return hasKeyword && hasAction;
    }

    function packImageHistory(imageSrc, caption = '') {
        return `[[IMAGE]]${imageSrc}||${(caption || '').replace(/\n/g, ' ')}`;
    }

    function unpackImageHistory(text) {
        const raw = (text || '');
        if (!raw.startsWith('[[IMAGE]]')) return null;
        const body = raw.slice('[[IMAGE]]'.length);
        const parts = body.split('||');
        return {
            src: parts[0] || '',
            caption: parts.slice(1).join('||') || '',
        };
    }

    async function generateImageFromPrompt(promptText) {
        const fd = new FormData();
        fd.append('prompt', promptText);
        fd.append('provider', 'openai');
        fd.append('size', '1024x1024');

        const res = await fetch('/api/image', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok || data.error) {
            throw new Error(data.error || '이미지 생성 실패');
        }
        return data;
    }

    function stripSourcesForTts(text) {
        return parseSourcesBlock(text).answer;
    }

    function queueTtsText(rawText) {
        const text = stripSourcesForTts(rawText);
        if (!text || !ttsToggle.checked) return;
        const token = ttsSessionToken;
        ttsQueue = ttsQueue.then(async () => {
            if (token !== ttsSessionToken || !ttsToggle.checked) return;
            await speak(text, token);
        }).catch(() => {});
    }

    function splitSpeakableChunk(text, force = false) {
        if (!text) return { speak: '', rest: '' };
        const match = text.match(/[\.\!\?]\s|\n/g);
        if (!match && !force) return { speak: '', rest: text };
        if (!match && force) return { speak: text, rest: '' };

        let idx = -1;
        const punct = /[\.\!\?]\s|\n/g;
        let m;
        while ((m = punct.exec(text)) !== null) {
            idx = m.index + m[0].length;
        }
        if (idx < 0) {
            return force ? { speak: text, rest: '' } : { speak: '', rest: text };
        }
        return { speak: text.slice(0, idx), rest: text.slice(idx) };
    }

    async function speakViaServer(text) {
        const fd = new FormData();
        fd.append('text', text);
        fd.append('provider', 'openai');
        fd.append('voice', 'alloy');
        fd.append('audio_format', 'mp3');
        const res = await fetch('/api/tts', { method: 'POST', body: fd });
        if (!res.ok) throw new Error('TTS 서버 오류');
        const contentType = res.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            const data = await res.json();
            throw new Error(data.error || 'TTS 실패');
        }
        const blob = await res.blob();
        if (!blob.size) return;

        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        currentTtsAudio = audio;
        syncTtsStopButton();
        await new Promise((resolve, reject) => {
            audio.onended = () => {
                URL.revokeObjectURL(url);
                if (currentTtsAudio === audio) currentTtsAudio = null;
                syncTtsStopButton();
                resolve();
            };
            audio.onerror = () => {
                URL.revokeObjectURL(url);
                if (currentTtsAudio === audio) currentTtsAudio = null;
                syncTtsStopButton();
                reject(new Error('오디오 재생 실패'));
            };
            audio.play().catch(reject);
        });
    }

    async function speakViaBrowser(text) {
        if (!('speechSynthesis' in window)) return;
        syncTtsStopButton();
        await new Promise((resolve) => {
            const utter = new SpeechSynthesisUtterance(text);
            utter.lang = 'ko-KR';
            utter.rate = 1;
            utter.pitch = 1;
            utter.onend = () => {
                syncTtsStopButton();
                resolve();
            };
            utter.onerror = () => {
                syncTtsStopButton();
                resolve();
            };
            window.speechSynthesis.speak(utter);
        });
    }

    async function speak(text, token = null) {
        if (token !== null && token !== ttsSessionToken) return;
        if (!ttsToggle.checked) return;
        const content = stripSourcesForTts(text);
        if (!content) return;
        if (ttsMode === 'server') {
            try {
                await speakViaServer(content);
                if (token !== null && token !== ttsSessionToken) return;
                return;
            } catch (e) {
                console.warn('서버 TTS 실패, 브라우저 TTS로 폴백:', e);
                ttsMode = 'browser';
                localStorage.setItem(TTS_MODE_KEY, ttsMode);
            }
        }
        if (token !== null && token !== ttsSessionToken) return;
        await speakViaBrowser(content);
    }

    async function sendMessage() {
        const text = messageInput.value.trim();
        if (!text) return;
        stopSpeech();
        const requestToken = chatSessionToken;
        const sendBtn = document.getElementById('sendBtn');

        if (!activeTopicId) {
            createTopicIfNeeded(text);
            await resetServerMemorySilently();
        }

        if (isImageGenerationRequest(text)) {
            hideWelcome();
            addMsg('user', text, true, { editable: true });
            appendMessageToActiveTopic('user', text);
            messageInput.value = '';

            const loadingId = 'loading-' + Date.now();
            addLoadingMsg(loadingId);
            if (sendBtn) sendBtn.disabled = true;
            try {
                const imageResult = await generateImageFromPrompt(text);
                removeLoadingMsg(loadingId);
                const imageSrc = imageResult.image_data_url || imageResult.image_url || '';
                if (!imageSrc) {
                    throw new Error('이미지 URL이 비어 있습니다.');
                }
                addMsg('ai', '요청하신 이미지입니다.');
                addImageMsg(imageSrc, text);
                // data URL은 localStorage를 크게 쓰므로 기록에는 URL만 저장하고 data URL이면 텍스트만 남김.
                const historyImageSrc = imageSrc.startsWith('data:') ? '' : imageSrc;
                appendMessageToActiveTopic('assistant', historyImageSrc ? packImageHistory(historyImageSrc, text) : '이미지 생성 완료');
            } catch (e) {
                removeLoadingMsg(loadingId);
                addMsg('ai', '이미지 생성 오류: ' + e.message);
            } finally {
                if (sendBtn) sendBtn.disabled = false;
            }
            return;
        }

        hideWelcome();
        addMsg('user', text, true, { editable: true });
        appendMessageToActiveTopic('user', text);
        messageInput.value = '';

        const loadingId = 'loading-' + Date.now();
        addLoadingMsg(loadingId);
        if (sendBtn) sendBtn.disabled = true;

        const fd = new FormData();
        fd.append('message', text);
        fd.append('provider', providerSelect.value);
        fd.append('empathy_level', empathySelect ? empathySelect.value : 'balanced');
        fd.append('web_search', webSearchToggle.checked ? 'true' : 'false');
        const controller = new AbortController();
        activeChatController = controller;

        try {
            const res = await fetch('/api/chat', { method: 'POST', body: fd, signal: controller.signal });
            if (!res.ok) throw new Error('서버 연결 실패');

            removeLoadingMsg(loadingId);
            const aiDiv = document.createElement('div');
            aiDiv.className = 'message ai';
            chatBox.appendChild(aiDiv);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let resultText = '';
            let ttsCursor = 0;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                if (requestToken !== chatSessionToken) return;
                const chunk = decoder.decode(value, { stream: true });
                resultText += chunk;
                renderAiMessage(aiDiv, resultText || 'Thinking');
                chatBox.scrollTop = chatBox.scrollHeight;

                if (ttsToggle && ttsToggle.checked) {
                    const pending = stripSourcesForTts(resultText).slice(ttsCursor);
                    const { speak: speakable, rest } = splitSpeakableChunk(pending, false);
                    if (speakable && speakable.trim()) {
                        queueTtsText(speakable);
                        ttsCursor += speakable.length;
                    } else if (rest.length > 200) {
                        queueTtsText(rest);
                        ttsCursor += rest.length;
                    }
                }
            }

            if (requestToken !== chatSessionToken) return;
            if (!resultText.trim()) {
                renderAiMessage(aiDiv, '응답을 받지 못했습니다. 다시 시도해 주세요.');
            }
            if (ttsToggle && ttsToggle.checked) {
                const remaining = stripSourcesForTts(resultText).slice(ttsCursor);
                const { speak: lastSpeakable } = splitSpeakableChunk(remaining, true);
                if (lastSpeakable && lastSpeakable.trim()) {
                    queueTtsText(lastSpeakable);
                }
            }
            appendMessageToActiveTopic('assistant', resultText.trim());
        } catch (e) {
            if (e.name === 'AbortError') {
                removeLoadingMsg(loadingId);
                return;
            }
            removeLoadingMsg(loadingId);
            addMsg('ai', '오류가 발생했습니다: ' + e.message);
        } finally {
            if (sendBtn) sendBtn.disabled = false;
            if (activeChatController === controller) {
                activeChatController = null;
            }
        }
    }

    async function uploadFile() {
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];
        if (!file) return;

        const fd = new FormData();
        fd.append('file', file);

        try {
            const res = await fetch('/api/upload', { method: 'POST', body: fd });
            const data = await res.json();
            alert(data.message || '업로드 완료');
            hideWelcome();
            fileInput.value = '';
        } catch (e) {
            alert('업로드 실패: ' + e.message);
        }
    }

    async function resetMemory() {
        stopSpeech();
        try {
            const res = await fetch('/api/memory/reset', { method: 'POST' });
            const data = await res.json();
            addMsg('ai', data.message || '메모리를 초기화했습니다.');
        } catch (e) {
            addMsg('ai', '메모리 초기화 실패: ' + e.message);
        }
    }

    async function startNewChat() {
        stopAllVoice(true);
        await resetServerMemorySilently();

        chatBox.innerHTML = '';
        activeTopicId = null;
        if (welcomeScreen) {
            chatBox.appendChild(welcomeScreen);
        }
        showWelcome();
        messageInput.value = '';
        messageInput.focus();
    }

    async function toggleRecording() {
        if (!sttEnabled) return;
        stopSpeech();
        if (typeof MediaRecorder === 'undefined') {
            alert('이 브라우저는 MediaRecorder를 지원하지 않습니다.');
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('이 브라우저는 음성 녹음을 지원하지 않습니다.');
            return;
        }

        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            currentMicStream = stream;
            audioChunks = [];
            skipNextStt = false;
            const mimeTypeCandidates = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/ogg;codecs=opus',
            ];
            const mimeType = mimeTypeCandidates.find((m) => MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) || '';
            mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
            startSttMonitoring(stream);
            sttRecordStartedAt = Date.now();

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                micBtn.classList.remove('recording');
                stopSttMonitoring();
                if (skipNextStt) {
                    skipNextStt = false;
                    if (currentMicStream) {
                        currentMicStream.getTracks().forEach(track => track.stop());
                        currentMicStream = null;
                    }
                    mediaRecorder = null;
                    return;
                }
                const blobType = mediaRecorder && mediaRecorder.mimeType ? mediaRecorder.mimeType : 'audio/webm';
                const ext = blobType.includes('mp4') ? 'mp4' : 'webm';
                const audioBlob = new Blob(audioChunks, { type: blobType });
                if (audioBlob.size < 1500) {
                    addMsg('ai', '음성이 너무 짧거나 작아서 인식하지 못했습니다. 1~2초 이상 말한 뒤 다시 시도해 주세요.');
                    if (currentMicStream) {
                        currentMicStream.getTracks().forEach(track => track.stop());
                        currentMicStream = null;
                    }
                    mediaRecorder = null;
                    return;
                }
                const fd = new FormData();
                fd.append('file', audioBlob, `speech.${ext}`);
                fd.append('provider', 'openai');
                fd.append('language', 'ko');

                try {
                    const res = await fetch('/api/stt', { method: 'POST', body: fd });
                    const data = await res.json();
                    if (data.error) {
                        addMsg('ai', 'STT 오류: ' + data.error);
                        return;
                    }
                    if (data.text) {
                        messageInput.value = data.text;
                        messageInput.focus();
                    }
                } catch (e) {
                    addMsg('ai', 'STT 요청 실패: ' + e.message);
                } finally {
                    stopSttMonitoring();
                    if (currentMicStream) {
                        currentMicStream.getTracks().forEach(track => track.stop());
                        currentMicStream = null;
                    }
                    mediaRecorder = null;
                }
            };

            mediaRecorder.start(300);
            micBtn.classList.add('recording');
        } catch (e) {
            addMsg('ai', '마이크 접근 실패: ' + e.message);
        }
    }

    function toggleSidebar() {
        if (!sidebarContainer) return;
        const isOpen = sidebarContainer.classList.toggle('open');
        if (railMenuBtn) {
            railMenuBtn.innerText = isOpen ? '✕' : '☰';
            railMenuBtn.setAttribute('aria-label', isOpen ? '메뉴 닫기' : '메뉴 열기');
        }
        syncRailActionButtons(isOpen);
    }

    function closeSidebar() {
        if (!sidebarContainer) return;
        sidebarContainer.classList.remove('open');
        if (railMenuBtn) {
            railMenuBtn.innerText = '☰';
            railMenuBtn.setAttribute('aria-label', '메뉴 열기');
        }
        syncRailActionButtons(false);
        closeRailSettingsPopover();
    }

    function syncRailActionButtons(isOpen) {
        if (railNewChatBtn) railNewChatBtn.classList.toggle('hidden', isOpen);
        if (railSettingsBtn) railSettingsBtn.classList.toggle('hidden', isOpen);
    }

    function openSettingsFromRail() {
        if (!railSettingsPopover) return;
        syncQuickSettingsFromMain();
        railSettingsPopover.classList.toggle('show');
    }

    function closeRailSettingsPopover() {
        if (railSettingsPopover) railSettingsPopover.classList.remove('show');
    }

    function syncQuickSettingsFromMain() {
        if (quickThemeSelect && themeSelect) quickThemeSelect.value = themeSelect.value;
        if (quickProviderSelect && providerSelect) quickProviderSelect.value = providerSelect.value;
        if (quickWebSearchToggle && webSearchToggle) quickWebSearchToggle.checked = webSearchToggle.checked;
        if (quickTtsToggle && ttsToggle) quickTtsToggle.checked = ttsToggle.checked;
        if (quickSttToggle && sttToggle) quickSttToggle.checked = sttToggle.checked;
    }

    function applyQuickSettingsToMain() {
        if (themeSelect && quickThemeSelect) {
            themeSelect.value = quickThemeSelect.value;
            applyTheme(themeSelect.value);
        }
        if (providerSelect && quickProviderSelect) {
            providerSelect.value = quickProviderSelect.value;
        }
        if (webSearchToggle && quickWebSearchToggle) {
            webSearchToggle.checked = quickWebSearchToggle.checked;
        }
        if (ttsToggle && quickTtsToggle) {
            ttsToggle.checked = quickTtsToggle.checked;
            if (!ttsToggle.checked) stopSpeech();
        }
        if (sttToggle && quickSttToggle) {
            setSttEnabled(quickSttToggle.checked);
        }
    }

    function toggleSettingsPanel() {
        if (!settingsPanel) return;
        const collapsed = settingsPanel.classList.toggle('collapsed');
        settingsToggleBtn.setAttribute('aria-label', collapsed ? '설정 열기' : '설정 닫기');
    }

    function handleSidebarSwipe() {
        const deltaX = touchEndX - touchStartX;
        // Close when user swipes left enough while drawer is open.
        if (deltaX < -60 && sidebarContainer.classList.contains('open')) {
            closeSidebar();
        }
    }

    function isEventInsideElement(event, element) {
        if (!event || !element) return false;
        const path = event.composedPath ? event.composedPath() : [];
        return path.includes(element);
    }

    document.getElementById('resetMemoryBtn').addEventListener('click', resetMemory);
    newChatBtn.addEventListener('click', startNewChat);
    if (railNewChatBtn) {
        railNewChatBtn.addEventListener('click', async () => {
            await startNewChat();
        });
    }
    if (quickOpenSidebarBtn) {
        quickOpenSidebarBtn.addEventListener('click', () => {
            closeRailSettingsPopover();
            if (!sidebarContainer.classList.contains('open')) {
                toggleSidebar();
            }
            if (settingsPanel && settingsPanel.classList.contains('collapsed')) {
                settingsPanel.classList.remove('collapsed');
            }
        });
    }
    clearHistoryBtn.addEventListener('click', () => {
        const ok = confirm('전체 기록 삭제하시겠습니까?');
        if (!ok) return;
        chatTopics = [];
        activeTopicId = null;
        saveTopicHistory();
        renderTopicHistory();
        startNewChat();
    });
    settingsToggleBtn.addEventListener('click', toggleSettingsPanel);
    micBtn.addEventListener('click', toggleRecording);
    if (stopTtsBtn) {
        stopTtsBtn.addEventListener('click', () => stopSpeech());
    }
    if (sttToggle) {
        sttToggle.addEventListener('change', (e) => setSttEnabled(e.target.checked));
    }
    if (railMenuBtn) railMenuBtn.addEventListener('click', toggleSidebar);
    if (railSettingsBtn) {
        railSettingsBtn.addEventListener('click', () => {
            openSettingsFromRail();
        });
    }
    if (quickThemeSelect) {
        quickThemeSelect.addEventListener('change', () => applyQuickSettingsToMain());
    }
    if (quickProviderSelect) {
        quickProviderSelect.addEventListener('change', () => applyQuickSettingsToMain());
    }
    if (quickWebSearchToggle) {
        quickWebSearchToggle.addEventListener('change', () => applyQuickSettingsToMain());
    }
    if (quickTtsToggle) {
        quickTtsToggle.addEventListener('change', () => applyQuickSettingsToMain());
    }
    if (quickSttToggle) {
        quickSttToggle.addEventListener('change', () => applyQuickSettingsToMain());
    }
    if (themeSelect) {
        themeSelect.addEventListener('change', (e) => applyTheme(e.target.value));
    }
    if (empathySelect) {
        empathySelect.addEventListener('change', (e) => applyEmpathyLevel(e.target.value));
    }
    if (ttsToggle) {
        ttsToggle.addEventListener('change', () => {
            if (!ttsToggle.checked) stopSpeech();
            if (quickTtsToggle) quickTtsToggle.checked = ttsToggle.checked;
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            stopSpeech();
            closeSidebar();
            closeRailSettingsPopover();
            closeCitationModal();
        }
    });
    document.addEventListener('pointerdown', (e) => {
        const target = e.target;
        if (!target) return;

        if (
            sidebarContainer &&
            sidebarContainer.classList.contains('open') &&
            !isEventInsideElement(e, sidebar) &&
            !isEventInsideElement(e, railMenuBtn)
        ) {
            closeSidebar();
        }
    });

    document.addEventListener('click', (e) => {
        const target = e.target;
        if (!target) return;

        if (
            railSettingsPopover &&
            railSettingsPopover.classList.contains('show') &&
            !railSettingsPopover.contains(target) &&
            target !== railSettingsBtn
        ) {
            closeRailSettingsPopover();
        }

        if (
            citationModal &&
            citationModal.classList.contains('open') &&
            !citationModal.contains(target) &&
            !(target.closest && target.closest('.citation-chip'))
        ) {
            closeCitationModal();
        }
    });
    sidebar.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });
    sidebar.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        handleSidebarSwipe();
    }, { passive: true });
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    window.addEventListener('beforeunload', () => stopAllVoice(true));
    window.addEventListener('pagehide', () => stopAllVoice(true));
    window.addEventListener('resize', () => {
        if (citationModal && citationModal.classList.contains('open') && citationAnchorButton) {
            positionCitationPopover(citationAnchorButton);
        }
    });
    window.addEventListener('scroll', () => {
        if (citationModal && citationModal.classList.contains('open') && citationAnchorButton) {
            positionCitationPopover(citationAnchorButton);
        }
    }, true);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
            stopAllVoice(true);
        }
    });

    const savedTheme = localStorage.getItem('bao_theme') || 'light';
    applyTheme(savedTheme);
    const savedEmpathy = localStorage.getItem(EMPATHY_LEVEL_KEY) || 'balanced';
    applyEmpathyLevel(savedEmpathy);
    loadTopicHistory();
    syncRailActionButtons(sidebarContainer && sidebarContainer.classList.contains('open'));
    const savedSttEnabled = localStorage.getItem(STT_ENABLED_KEY);
    setSttEnabled(savedSttEnabled !== 'false');
    syncTtsStopButton();

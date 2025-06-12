const video = document.getElementById('webcam');
const messageBox = document.getElementById('message-box');
const detectBtn = document.getElementById('detect-btn');
const speakBtn = document.getElementById('speak-btn');
const clearBtn = document.getElementById('clear-btn');
const suggestedArea = document.getElementById('suggested-area');
const detectedWordDisplay = document.getElementById('detected-word-display');
const modelSelect = document.getElementById('model-select');

const dictionary = ['halo', 'apa', 'kabar', 'terima', 'kasih', 'selamat', 'datang', 'sampai', 'jumpa', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'];

let socket = null;
let isDetecting = false;
let signDetectionInterval;
const BASE_BACKEND_URL = "wss://signbridge-app-backend.onrender.com/ws"; // Ganti dengan URL Render Anda saat deploy

const captureCanvas = document.createElement('canvas');
const captureCtx = captureCanvas.getContext('2d');
let lastPrediction = "-";

// --- Fungsi Inisialisasi ---
async function setupCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;
        video.addEventListener('loadedmetadata', () => {
            captureCanvas.width = video.videoWidth;
            captureCanvas.height = video.videoHeight;
        });
    } catch (err) {
        alert('Akses webcam error: ' + err.message);
    }
}

// --- Fungsi Deteksi Bahasa Isyarat ---
function sendFrameForSignDetection() {
    if (socket && socket.readyState === WebSocket.OPEN && isDetecting) {
        captureCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
        const frameData = captureCanvas.toDataURL('image/jpeg', 0.8);
        socket.send(frameData);
    }
}

function showDetectedWord(word) {
    detectedWordDisplay.textContent = word;
}

function toggleDetection() {
    if (!isDetecting) {
        const selectedModel = modelSelect.value;
        // Pada saat deploy, ganti "localhost:8001" dengan URL dari Render
        const backendUrlWithMode = `ws://localhost:8001/ws/${selectedModel}`; 
        // CONTOH DEPLOY: const backendUrlWithMode = `wss://nama-anda.onrender.com/ws/${selectedModel}`;
        
        console.log(`Menghubungkan ke: ${backendUrlWithMode}`);
        socket = new WebSocket(backendUrlWithMode);

        socket.onopen = () => {
            console.log("Koneksi deteksi isyarat berhasil.");
            isDetecting = true;
            detectBtn.textContent = 'Hentikan Deteksi';
            modelSelect.disabled = true;
            detectBtn.style.backgroundColor = '#ff4242';
            signDetectionInterval = setInterval(sendFrameForSignDetection, 250);
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.error) {
                alert(`Error dari server: ${data.error}`);
                toggleDetection();
                return;
            }
            showDetectedWord(data.prediction);
            if (data.prediction && data.prediction !== "-" && data.prediction !== lastPrediction) {
                if (messageBox.value.slice(-1) !== " " && messageBox.value.length > 0) {
                    messageBox.value += " " + data.prediction;
                } else {
                    messageBox.value += data.prediction;
                }
                lastPrediction = data.prediction;
                setTimeout(() => {
                    if (lastPrediction !== "-") {
                        messageBox.value += " ";
                        lastPrediction = "-";
                    }
                }, 500);
            } else if (data.prediction === "-") {
                lastPrediction = "-";
            }
        };

        socket.onclose = () => { console.log("Koneksi deteksi isyarat ditutup."); stopDetection(); };
        socket.onerror = (error) => { console.error("WebSocket error:", error); alert("Gagal terhubung ke server deteksi."); stopDetection(); };
    } else {
        stopDetection();
    }
}

function stopDetection() {
    isDetecting = false;
    if (socket) {
        socket.close();
        socket = null;
    }
    clearInterval(signDetectionInterval);
    detectBtn.textContent = 'Mulai Deteksi';
    modelSelect.disabled = false;
    detectBtn.style.backgroundColor = 'var(--primary-color)';
    showDetectedWord('');
}

// --- Event Listeners ---
detectBtn.addEventListener('click', toggleDetection);
clearBtn.addEventListener('click', () => { messageBox.value = ''; lastPrediction = "-"; });
speakBtn.addEventListener('click', () => {
    const text = messageBox.value.trim();
    if (!text) { alert('Tidak ada pesan untuk diucapkan'); return; }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'id-ID';
    speechSynthesis.speak(utterance);
});

messageBox.addEventListener('input', () => {
    const words = messageBox.value.trim().split(' ');
    const last = words[words.length - 1].toLowerCase();
    if (!last) { suggestedArea.innerHTML = ''; return; }
    const filtered = dictionary.filter(w => w.startsWith(last) && w !== last);
    showSuggestions(filtered);
});

function showSuggestions(words) {
    suggestedArea.innerHTML = '';
    words.forEach(word => {
        const span = document.createElement('span');
        span.textContent = word;
        span.classList.add('suggested-word');
        span.onclick = () => {
            let text = messageBox.value;
            let lastSpace = text.lastIndexOf(' ');
            if (lastSpace === -1) { messageBox.value = word + ' '; } else { messageBox.value = text.slice(0, lastSpace + 1) + word + ' '; }
            messageBox.focus();
            suggestedArea.innerHTML = '';
        };
        suggestedArea.appendChild(span);
    });
}

// --- Jalankan Aplikasi ---
setupCamera();
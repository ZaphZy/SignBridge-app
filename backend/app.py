# backend/app.py

import os
import cv2
import numpy as np
import mediapipe as mp
import tensorflow as tf
from transformers import pipeline, AutoProcessor
import gradio as gr
import torch

# --- 1. PEMUATAN SEMUA MODEL (HANYA SEKALI SAAT APLIKASI DIMULAI) ---

print("Memulai pemuatan semua model. Proses ini mungkin memakan waktu lama...")

# --- Konfigurasi Perangkat (Device) ---
# Gunakan GPU jika tersedia (Hugging Face Spaces menyediakan GPU gratis di beberapa tier)
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

print(f"Menggunakan perangkat: {device}")

# --- Konfigurasi Path ---
SIBI_MODEL_PATH = os.path.join('models_sibi', 'final_hybrid_sign_language_model_augmented_sibi.h5')
SIBI_CLASS_NAMES_PATH = os.path.join('data_sibi', 'class_names.txt')
BISINDO_MODEL_PATH = os.path.join('models_bisindo', 'final_hybrid_sign_language_model_augmented_bisindo.h5') 
BISINDO_CLASS_NAMES_PATH = os.path.join('data_bisindo', 'class_names.txt')
IMAGE_HEIGHT, IMAGE_WIDTH = 224, 224

# --- Fungsi Pemuatan ---
def load_tf_model(path, type_name):
    try:
        model = tf.keras.models.load_model(path)
        print(f"Model {type_name} berhasil dimuat.")
        return model
    except Exception as e:
        print(f"ERROR memuat model {type_name}: {e}")
        return None

def load_class_names(path, type_name):
    try:
        with open(path, 'r') as f:
            names = [line.strip() for line in f.readlines()]
            print(f"Nama kelas {type_name} berhasil dimuat.")
            return names
    except Exception as e:
        print(f"ERROR memuat nama kelas {type_name}: {e}")
        return []

# --- Muat semua model ---
sibi_model = load_tf_model(SIBI_MODEL_PATH, "SIBI")
sibi_class_names = load_class_names(SIBI_CLASS_NAMES_PATH, "SIBI")
bisindo_model = load_tf_model(BISINDO_MODEL_PATH, "BISINDO")
bisindo_class_names = load_class_names(BISINDO_CLASS_NAMES_PATH, "BISINDO")

stt_pipeline = None
try:
    print("Memuat pipeline Whisper 'large-v3' (STT)... Ini akan mengunduh >3GB saat pertama kali.")
    stt_pipeline = pipeline(
        "automatic-speech-recognition", 
        model="openai/whisper-large-v3",
        torch_dtype=torch_dtype,
        device=device
    )
    print("Pipeline Whisper (STT) 'large-v3' berhasil dimuat.")
except Exception as e:
    print(f"Gagal memuat pipeline Whisper: {e}")

mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.5)

print("Semua model telah siap.")

# --- 2. FUNGSI LOGIKA UTAMA UNTUK GRADIO ---
def signbridge_interface(mode, sign_language_image, speech_audio):
    sign_result = "Tidak ada input gambar."
    stt_result = "Tidak ada input suara."

    # --- Logika Deteksi Bahasa Isyarat ---
    if sign_language_image is not None:
        active_model = sibi_model if mode == "SIBI" else bisindo_model
        active_class_names = sibi_class_names if mode == "SIBI" else bisindo_class_names
        if active_model:
            img_bgr = cv2.cvtColor(sign_language_image, cv2.COLOR_RGB2BGR)
            image_rgb_for_mp = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            results = hands_detector.process(image_rgb_for_mp)
            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                landmarks_list = [lm.x for lm in hand_landmarks.landmark] + [lm.y for lm in hand_landmarks.landmark]
                interleaved = []
                for i in range(21): interleaved.extend([landmarks_list[i], landmarks_list[i+21]])
                base_x, base_y = interleaved[0], interleaved[1]
                normalized = [val - (base_x if i % 2 == 0 else base_y) for i, val in enumerate(interleaved)]
                max_val = np.max(np.abs(normalized)); scaled = np.array(normalized) / (max_val if max_val != 0 else 1)
                landmark_input = np.expand_dims(scaled, axis=0)
                img_resized = cv2.resize(img_bgr, (IMAGE_WIDTH, IMAGE_HEIGHT))
                img_normalized = img_resized.astype('float32') / 255.0
                img_input = np.expand_dims(img_normalized, axis=0)
                prediction = active_model.predict({'image_input': img_input, 'landmark_input': landmark_input}, verbose=0)
                idx = np.argmax(prediction)
                confidence = prediction[0][idx] * 100
                sign_result = f"Hasil Deteksi Isyarat ({mode}): {active_class_names[idx]} (Keyakinan: {confidence:.2f}%)"
            else:
                sign_result = "Tangan tidak terdeteksi pada gambar."
        else:
            sign_result = f"Model untuk mode {mode} tidak dapat dimuat."

    # --- Logika Speech-to-Text ---
    if speech_audio is not None and stt_pipeline is not None:
        sampling_rate, audio_data = speech_audio
        audio_float = audio_data.astype(np.float32) / 32768.0
        result = stt_pipeline({"sampling_rate": sampling_rate, "raw": audio_float}, generate_kwargs={"language": "indonesian"})
        stt_result = result.get("text", "Gagal melakukan transkripsi.").strip()
        if not stt_result: stt_result = "Tidak ada ucapan yang terdeteksi."

    return f"{sign_result}\n\n---\n\nHasil Transkripsi Suara:\n{stt_result}"

# --- 3. MEMBUAT ANTARMUKA GRADIO ---
demo = gr.Interface(
    fn=signbridge_interface,
    inputs=[
        gr.Radio(["SIBI", "BISINDO"], label="Mode Deteksi Bahasa Isyarat", value="SIBI"),
        gr.Image(sources=["webcam", "upload"], type="numpy", label="Input Gambar Isyarat"),
        gr.Audio(sources=["microphone"], type="numpy", label="Input Suara")
    ],
    outputs=gr.Textbox(label="Hasil Kombinasi", lines=6),
    title="SignBridge",
    description="Aplikasi Demo Terpadu. Pilih mode, lalu berikan input gambar (dari webcam/upload) ATAU input suara (dari mikrofon). Klik 'Submit' untuk melihat hasilnya.",
    allow_flagging="never"
)

if __name__ == "__main__":
    demo.launch()
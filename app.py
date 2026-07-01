import os
import threading
import time
from pathlib import Path

import cv2
import dlib
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from scipy.spatial import distance as dist
from tkinter import filedialog, messagebox

try:
    import winsound
except ImportError:
    winsound = None


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

MODEL_DIR = Path("models")
LANDMARK_MODEL = MODEL_DIR / "shape_predictor_68_face_landmarks.dat"
CNN_FACE_MODEL = MODEL_DIR / "mmod_human_face_detector.dat"

LEFT_EYE = list(range(42, 48))
RIGHT_EYE = list(range(36, 42))


def eye_aspect_ratio(eye_points):
    a = dist.euclidean(eye_points[1], eye_points[5])
    b = dist.euclidean(eye_points[2], eye_points[4])
    c = dist.euclidean(eye_points[0], eye_points[3])
    return (a + b) / (2.0 * c)


def shape_to_np(shape, dtype="int"):
    coords = np.zeros((68, 2), dtype=dtype)
    for i in range(68):
        coords[i] = (shape.part(i).x, shape.part(i).y)
    return coords


class BlinkDetectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Otomatik Göz Kırpma Tespiti")
        self.root.geometry("1050x650")
        self.root.minsize(980, 620)
        self.root.configure(bg="#f7f9fc")

        self.video_size = (640, 400)
        self.video_capture = None
        self.running = False
        self.after_id = None

        self.blink_count = 0
        self.frame_counter = 0
        self.closed_eye_started_at = None
        self.last_alarm_sound_at = 0

        self.EAR_THRESHOLD = tk.DoubleVar(value=0.22)
        self.CONSEC_FRAMES = tk.IntVar(value=3)
        self.ALARM_SECONDS = tk.DoubleVar(value=2.0)

        self.status_text = tk.StringVar(value="Hazır")
        self.ear_text = tk.StringVar(value="EAR: -")
        self.blink_text = tk.StringVar(value="Göz Kırpma Sayısı: 0")
        self.face_text = tk.StringVar(value="Yüz Durumu: -")
        self.eye_state_text = tk.StringVar(value="Göz Durumu: -")
        self.alert_text = tk.StringVar(value="Uyarı Durumu: Yok")

        self.predictor = None
        self.face_detector = None
        self.using_cnn = False

        self.build_ui()
        self.load_models()

    def build_ui(self):
        tk.Label(
            self.root,
            text="Otomatik Göz Kırpma Tespiti",
            font=("Arial", 22, "bold"),
            bg="#f7f9fc",
            fg="#111827",
        ).pack(pady=(10, 8))

        content = tk.Frame(self.root, bg="#f7f9fc")
        content.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        content.grid_columnconfigure(0, weight=1, minsize=720)
        content.grid_columnconfigure(1, weight=0, minsize=280)
        content.grid_rowconfigure(0, weight=1)

        self.build_center_panel(content)
        self.build_right_panel(content)

    def build_center_panel(self, parent):
        center = tk.Frame(parent, bg="#f7f9fc")
        center.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        center.grid_columnconfigure(0, weight=1)

        self.video_label = tk.Label(center, bg="#0f172a", fg="white", font=("Arial", 12))
        self.video_label.grid(row=0, column=0, sticky="nsew", pady=(28, 0))
        self.set_placeholder_frame("Kamera veya video başlatınız")

    def build_right_panel(self, parent):
        right = tk.Frame(parent, bg="#f7f9fc", width=280)
        right.grid(row=0, column=1, sticky="ns", padx=(0, 0))
        right.grid_propagate(False)

        controls = self.card(right)
        controls.pack(fill="x", pady=(18, 10))
        self.card_title(controls, "KONTROL BUTONLARI").pack(anchor="w", padx=12, pady=(10, 6))
        self.make_button(controls, "Kamerayı Başlat", self.start_camera, "#2563eb").pack(fill="x", padx=12, pady=3)
        self.make_button(controls, "Video Seç", self.open_video, "#4f46e5").pack(fill="x", padx=12, pady=3)
        self.make_button(controls, "Durdur", self.stop, "#dc2626").pack(fill="x", padx=12, pady=3)
        self.make_button(controls, "Sayaç Sıfırla", self.reset_counter, "#6b7280").pack(fill="x", padx=12, pady=(3, 10))

        settings = self.card(right)
        settings.pack(fill="x", pady=10)
        self.card_title(settings, "EAR EŞİK DEĞERİ").pack(anchor="w", padx=12, pady=(10, 2))
        tk.Scale(
            settings,
            from_=0.15,
            to=0.35,
            resolution=0.01,
            orient="horizontal",
            variable=self.EAR_THRESHOLD,
            bg="white",
            highlightthickness=0,
            length=220,
        ).pack(padx=8)
        self.card_title(settings, "ARDIŞIK KARE SAYISI").pack(anchor="w", padx=12, pady=(4, 2))
        tk.Scale(
            settings,
            from_=1,
            to=8,
            orient="horizontal",
            variable=self.CONSEC_FRAMES,
            bg="white",
            highlightthickness=0,
            length=220,
        ).pack(padx=8)
        self.card_title(settings, "UYARI SÜRESİ").pack(anchor="w", padx=12, pady=(4, 2))
        tk.Scale(
            settings,
            from_=0.5,
            to=5.0,
            resolution=0.5,
            orient="horizontal",
            variable=self.ALARM_SECONDS,
            bg="white",
            highlightthickness=0,
            length=220,
        ).pack(padx=8, pady=(0, 8))

        results = self.card(right)
        results.pack(fill="x", pady=10)
        self.card_title(results, "SONUÇ BİLGİLERİ").pack(anchor="w", padx=12, pady=(10, 6))
        self.make_value_label(results, self.blink_text).pack(fill="x", padx=12, pady=3)
        self.make_value_label(results, self.ear_text).pack(fill="x", padx=12, pady=3)
        self.make_value_label(results, self.face_text).pack(fill="x", padx=12, pady=3)
        self.alert_label = self.make_value_label(results, self.alert_text)
        self.alert_label.pack(fill="x", padx=12, pady=(3, 10))

    def card(self, parent):
        return tk.Frame(parent, bg="white", relief="solid", bd=1)

    def card_title(self, parent, text):
        return tk.Label(parent, text=text, bg="white", fg="#0f2a5f", font=("Arial", 9, "bold"))

    def make_value_label(self, parent, variable):
        return tk.Label(
            parent,
            textvariable=variable,
            font=("Arial", 9, "bold"),
            bg="#eef2ff",
            fg="#111827",
            anchor="w",
            padx=8,
            pady=6,
        )

    def make_button(self, parent, text, command, color):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            relief="flat",
            font=("Arial", 9, "bold"),
            height=1,
        )

    def set_placeholder_frame(self, text):
        image = Image.new("RGB", self.video_size, "#0f172a")
        self.show_image(image, text=text)

    def load_models(self):
        if not LANDMARK_MODEL.exists():
            self.status_text.set("Model bulunamadı")
            messagebox.showerror(
                "Model Eksik",
                "models/shape_predictor_68_face_landmarks.dat dosyası bulunamadı.",
            )
            return

        try:
            self.predictor = dlib.shape_predictor(str(LANDMARK_MODEL))
        except RuntimeError as exc:
            self.status_text.set("Model yüklenemedi")
            messagebox.showerror("Model Hatası", f"Landmark modeli okunamadı:\n{exc}")
            return

        if CNN_FACE_MODEL.exists():
            try:
                self.face_detector = dlib.cnn_face_detection_model_v1(str(CNN_FACE_MODEL))
                self.using_cnn = True
                self.status_text.set("CNN yüz dedektörü yüklendi")
            except RuntimeError:
                self.face_detector = dlib.get_frontal_face_detector()
                self.using_cnn = False
                self.status_text.set("CNN okunamadı, HOG kullanılıyor")
        else:
            self.face_detector = dlib.get_frontal_face_detector()
            self.using_cnn = False
            self.status_text.set("HOG yüz dedektörü kullanılıyor")

    def start_camera(self):
        if not self.ensure_model_ready():
            return
        self.stop()
        self.video_capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.video_capture.isOpened():
            self.video_capture = cv2.VideoCapture(0)
        self.start_processing("Kamera başlatıldı")

    def open_video(self):
        if not self.ensure_model_ready():
            return
        file_path = filedialog.askopenfilename(
            title="Video Seç",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv"), ("All Files", "*.*")],
        )
        if not file_path:
            return
        self.stop()
        self.video_capture = cv2.VideoCapture(file_path)
        self.start_processing("Video başlatıldı")

    def ensure_model_ready(self):
        if self.predictor is None or self.face_detector is None:
            messagebox.showerror("Hata", "Landmark modeli yüklenmedi.")
            return False
        return True

    def start_processing(self, status):
        if not self.video_capture or not self.video_capture.isOpened():
            messagebox.showerror("Hata", "Video/kamera açılamadı.")
            return
        self.running = True
        self.status_text.set(status)
        self.schedule_next_frame()

    def schedule_next_frame(self):
        if self.running:
            self.after_id = self.root.after(15, self.process_next_frame)

    def stop(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        self.clear_alarm_state()
        self.status_text.set("Durduruldu")
        self.set_placeholder_frame("Kamera veya video başlatınız")

    def reset_counter(self):
        self.blink_count = 0
        self.frame_counter = 0
        self.blink_text.set("Göz Kırpma Sayısı: 0")
        self.clear_alarm_state()

    def clear_alarm_state(self):
        self.closed_eye_started_at = None
        self.last_alarm_sound_at = 0
        self.alert_text.set("Uyarı Durumu: Yok")
        if hasattr(self, "alert_label"):
            self.alert_label.configure(bg="#eef2ff", fg="#111827")

    def detect_faces(self, gray, frame):
        if self.using_cnn:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return [d.rect for d in self.face_detector(rgb, 0)]
        return self.face_detector(gray, 0)

    def process_next_frame(self):
        if not self.running or self.video_capture is None:
            return

        ret, frame = self.video_capture.read()
        if not ret:
            self.status_text.set("Video bitti veya kare okunamadı")
            self.stop()
            return

        frame = cv2.resize(frame, self.video_size)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        rects = self.detect_faces(gray, frame)
        self.face_text.set(f"Yüz Durumu: {len(rects)} yüz tespit edildi")

        if len(rects) == 0:
            self.ear_text.set("EAR: -")
            self.eye_state_text.set("Göz Durumu: -")
            self.frame_counter = 0
            self.clear_alarm_state()
        else:
            self.process_face(frame, gray, rects[0])

        self.show_frame(frame)
        self.schedule_next_frame()

    def process_face(self, frame, gray, rect):
        shape = self.predictor(gray, rect)
        landmarks = shape_to_np(shape)

        left_eye = landmarks[LEFT_EYE]
        right_eye = landmarks[RIGHT_EYE]
        ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0

        self.ear_text.set(f"EAR: {ear:.3f}")
        self.draw_tracking(frame, left_eye, right_eye, rect, ear)

        if ear < self.EAR_THRESHOLD.get():
            self.handle_closed_eye(frame)
        else:
            self.handle_open_eye(frame)

    def draw_tracking(self, frame, left_eye, right_eye, rect, ear):
        cv2.drawContours(frame, [cv2.convexHull(left_eye)], -1, (0, 255, 0), 1)
        cv2.drawContours(frame, [cv2.convexHull(right_eye)], -1, (0, 255, 0), 1)
        cv2.rectangle(frame, (rect.left(), rect.top()), (rect.right(), rect.bottom()), (255, 180, 0), 2)
        cv2.putText(frame, f"EAR: {ear:.3f}", (24, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Blinks: {self.blink_count}", (24, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    def handle_closed_eye(self, frame):
        self.frame_counter += 1
        if self.closed_eye_started_at is None:
            self.closed_eye_started_at = time.time()

        closed_seconds = time.time() - self.closed_eye_started_at
        self.eye_state_text.set("Göz Durumu: Kapalı")
        cv2.putText(frame, "GOZ KAPALI", (24, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        if closed_seconds >= self.ALARM_SECONDS.get():
            self.trigger_alarm(frame, closed_seconds)
        else:
            self.alert_text.set(f"Uyarı Durumu: Bekleniyor ({closed_seconds:.1f} sn)")
            self.alert_label.configure(bg="#eef2ff", fg="#111827")

    def handle_open_eye(self, frame):
        if self.frame_counter >= self.CONSEC_FRAMES.get():
            self.blink_count += 1
            self.blink_text.set(f"Göz Kırpma Sayısı: {self.blink_count}")
        self.frame_counter = 0
        self.eye_state_text.set("Göz Durumu: Açık")
        self.clear_alarm_state()
        cv2.putText(frame, "GOZ ACIK", (24, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 180, 0), 2)

    def trigger_alarm(self, frame, closed_seconds):
        self.alert_text.set(f"UYARI: Göz {closed_seconds:.1f} sn kapalı!")
        self.alert_label.configure(bg="#fee2e2", fg="#991b1b")

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 110), (0, 0, 180), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
        cv2.putText(frame, "UYARI! GOZLER UZUN SURE KAPALI", (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        cv2.putText(frame, "Lutfen dikkat edin / mola verin", (24, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        now = time.time()
        if now - self.last_alarm_sound_at >= 1.0:
            self.last_alarm_sound_at = now
            threading.Thread(target=self.play_alarm_sound, daemon=True).start()

    def play_alarm_sound(self):
        if winsound is not None:
            winsound.Beep(1200, 250)
            winsound.Beep(900, 250)
        else:
            try:
                self.root.bell()
            except tk.TclError:
                pass

    def show_frame(self, frame):
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        self.show_image(image)

    def show_image(self, image, text=None):
        if image.size != self.video_size:
            image = image.resize(self.video_size)
        imgtk = ImageTk.PhotoImage(image=image)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk, text=text or "", compound="center")


def main():
    root = tk.Tk()
    app = BlinkDetectionApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()

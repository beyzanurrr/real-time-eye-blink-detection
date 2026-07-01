# Otomatik Göz Kırpma Tespiti

Bu uygulama yüz görüntülerinden göz kırpma hareketlerini tespit eder.

## Kullanılan Yöntemler

- Facial Landmarks Detection
- Dlib 68 noktalı yüz landmark modeli
- CNN yüz dedektörü: `mmod_human_face_detector.dat`
- EAR, yani Eye Aspect Ratio hesabı
- OpenCV ile kamera/video işleme
- Tkinter ile masaüstü arayüz

## Proje Klasör Yapısı

```
otomatik_goz_kirpma_tespiti/
│
├── app.py
├── requirements.txt
├── README.md
└── models/
    ├── shape_predictor_68_face_landmarks.dat
    └── mmod_human_face_detector.dat
```

## Kurulum

1. Python 3.10 veya 3.11 önerilir.

2. Sanal ortam oluşturun:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

3. Gerekli kütüphaneleri kurun:

```bash
pip install -r requirements.txt
```

## Dlib Model Dosyaları

Aşağıdaki dosyaları indirip `models` klasörüne koymanız gerekir:

1. `shape_predictor_68_face_landmarks.dat`
2. `mmod_human_face_detector.dat`

Not: CNN modeli yoksa program otomatik olarak HOG yüz dedektörünü kullanır. Ancak hocanız CNN istediği için `mmod_human_face_detector.dat` dosyasını eklemeniz daha uygundur.

## Çalıştırma

```bash
python app.py
```

## Arayüz Özellikleri

- Kamerayı başlatma
- Video dosyası seçme
- Göz kırpma sayacı
- EAR değerini canlı gösterme
- Yüz tespit durumunu gösterme
- EAR eşik değerini arayüzden değiştirme
- Ardışık kare sayısını değiştirme
- Sayaç sıfırlama

## Algoritma Özeti

1. Kamera veya video kaynağından kare alınır.
2. Dlib CNN yüz dedektörü ile yüz bölgesi tespit edilir.
3. Dlib 68 facial landmark modeli ile göz noktaları çıkarılır.
4. Sağ ve sol göz için EAR değeri hesaplanır.
5. Ortalama EAR değeri belirlenen eşik değerinin altına düşerse göz kapalı kabul edilir.
6. Bu durum belirlenen ardışık kare sayısı kadar devam ederse göz kırpma hareketi sayılır.

## EAR Formülü

EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)

## Uyari Sistemi

- Goz, paneldeki `Uyari Suresi (sn)` degerinden daha uzun kapali kalirsa alarm devreye girer.
- Video uzerinde kirmizi uyari bandi gosterilir.
- Windows ortaminda sesli beep calar; diger sistemlerde Tkinter'in varsayilan zil sesi denenir.
- Goz tekrar acildiginda veya yuz tespiti kayboldugunda alarm durumu otomatik sifirlanir.

## Model Indirme

Gerekli landmark modeli:

- https://github.com/davisking/dlib-models/blob/master/shape_predictor_68_face_landmarks.dat.bz2

Istege bagli CNN yuz modeli:

- https://github.com/davisking/dlib-models/blob/master/mmod_human_face_detector.dat.bz2

Bu dosyalari indirdikten sonra `.bz2` arsivinden cikarin ve `models` klasorune koyun. Klasorde dosya adlari soyle olmali:

- `models/shape_predictor_68_face_landmarks.dat`
- `models/mmod_human_face_detector.dat`

Burada p1-p6 göz çevresindeki 6 landmark noktasını ifade eder.

## Uygulama Alanları

- Sürücü yorgunluk algılama
- Sürücü güvenliği
- Psikolojik araştırmalar
- İnsan-bilgisayar etkileşimi
- Dikkat ve uyanıklık takibi

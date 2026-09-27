"""Lazer kapalı ve açık iki fotoğraftan kabarıklık sonucunu bulur."""

from dataclasses import dataclass

import cv2
import numpy as np

from .config import (
    LASER_BUMP_THRESHOLD,
    LASER_IMAGE_WIDTH,
    LASER_MIN_LENGTH_RATIO,
    LASER_X_RANGE,
    LASER_Y_RANGE,
)


@dataclass(frozen=True)
class LazerOlcumu:
    """Bulunan lazer çizgisinin ölçüm bilgilerini tutar."""

    deviation: float
    signal: float
    length_ratio: float = 0.0


@dataclass(frozen=True)
class LazerKarsilastirma:
    """İki fotoğraf karşılaştırıldıktan sonra arayüze gönderilen sonuçtur."""

    has_bump: bool
    deviation: float
    signal: float
    length_ratio: float
    threshold: float
    direction: str


def _cizgi_sapmasi(
    x_values: np.ndarray,
    y_values: np.ndarray,
    min_tolerance: float,
) -> float:
    """Lazerin normal eğimini çıkarıp kalan bükülmeyi hesaplar."""
    if len(x_values) < 2:
        raise ValueError("Lazer profili ölçüm için çok kısa.")

    # Lazer kamerada biraz eğik durabilir. Bu eğim kabarıklık olmadığı için çıkarılıyor.
    valid_points = np.ones_like(x_values, dtype=bool)
    for _ in range(2):
        line_factors = np.polyfit(
            x_values[valid_points],
            y_values[valid_points],
            1,
        )
        differences = y_values - np.polyval(line_factors, x_values)
        middle = float(np.median(differences[valid_points]))
        spread = float(np.median(np.abs(differences[valid_points] - middle)))
        tolerance = max(min_tolerance, 4.0 * 1.4826 * spread)
        new_points = np.abs(differences - middle) <= tolerance
        if int(np.sum(new_points)) < 2:
            break
        valid_points = new_points

    line_factors = np.polyfit(
        x_values[valid_points],
        y_values[valid_points],
        1,
    )
    differences = y_values - np.polyval(line_factors, x_values)
    return float(np.percentile(differences, 98) - np.percentile(differences, 2))


def _medyan_filtresi(values: np.ndarray, size: int) -> np.ndarray:
    """Çizgideki küçük kamera titreşimlerini azaltır."""
    edge = size // 2
    padded = np.pad(values, (edge, edge), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, size)
    return np.median(windows, axis=1)


def lazer_fotograflarini_karsilastir(
    laser_off_frame: np.ndarray,
    laser_on_frame: np.ndarray,
) -> LazerKarsilastirma:
    """Lazer kapalı ve açık fotoğrafı karşılaştırıp sonucu döndürür."""
    if laser_off_frame is None or laser_on_frame is None:
        raise ValueError("Karşılaştırma için iki fotoğraf da gereklidir.")
    if laser_off_frame.shape != laser_on_frame.shape:
        raise ValueError("İki fotoğrafın görüntü boyutu aynı değil.")

    # İki kare arasındaki kırmızı artış lazer çizgisini ortaya çıkarıyor.
    off_frame = laser_off_frame.astype(np.float32)
    on_frame = laser_on_frame.astype(np.float32)
    color_diff = on_frame - off_frame
    red_score = (
        color_diff[:, :, 2]
        - 0.55 * color_diff[:, :, 1]
        - 0.45 * color_diff[:, :, 0]
    )
    red_score = np.clip(red_score, 0.0, None)

    # Telefon yatay veya dik tutulabildiği için iki yön de deneniyor.
    candidates: list[tuple[float, str, LazerOlcumu]] = []
    for direction, score in (
        ("yatay", red_score),
        ("dikey", cv2.rotate(red_score, cv2.ROTATE_90_CLOCKWISE)),
    ):
        try:
            measurement, quality = _fark_goruntusunden_lazer_olc(score)
            candidates.append((quality, direction, measurement))
        except ValueError:
            continue

    if not candidates:
        raise ValueError(
            "Lazer çizgisi okunamadı. Kamerayı sabit tutup lazeri açtıktan sonra "
            "bir saniye bekleyerek fotoğrafı tekrar alın."
        )

    _, laser_direction, measurement = max(candidates, key=lambda candidate: candidate[0])
    return LazerKarsilastirma(
        has_bump=measurement.deviation >= LASER_BUMP_THRESHOLD,
        deviation=measurement.deviation,
        signal=measurement.signal,
        length_ratio=measurement.length_ratio,
        threshold=LASER_BUMP_THRESHOLD,
        direction=laser_direction,
    )


def _lazer_alanini_hazirla(red_score: np.ndarray) -> tuple[np.ndarray, float]:
    """Ölçüm görüntüsünü küçültür, inceleme alanını ve ölçeği döndürür."""
    original_height, original_width = red_score.shape
    if original_width > LASER_IMAGE_WIDTH:
        work_width = LASER_IMAGE_WIDTH
        work_height = round(
            original_height * work_width / original_width
        )
        red_score = cv2.resize(
            red_score,
            (work_width, work_height),
            interpolation=cv2.INTER_AREA,
        )

    height_scale = original_height / red_score.shape[0]
    height, width = red_score.shape
    x0 = int(width * LASER_X_RANGE[0])
    x1 = int(width * LASER_X_RANGE[1])
    y0 = int(height * LASER_Y_RANGE[0])
    y1 = int(height * LASER_Y_RANGE[1])
    area = red_score[y0:y1, x0:x1]
    if area.shape[0] < 20 or area.shape[1] < 40:
        raise ValueError("Lazer için bakılan görüntü alanı çok küçük.")

    return area, height_scale


def _cizgi_merkezlerini_bul(
    smoothed: np.ndarray,
    peak_rows: np.ndarray,
    baseline: np.ndarray,
    valid_columns: np.ndarray,
) -> np.ndarray:
    """Kalın lazer çizgisinin her sütundaki ağırlıklı merkezini bulur."""
    # Lazer kalın görünse bile çizginin ortasını bulmak için ağırlıklı ortalama alınıyor.
    centers = np.full(smoothed.shape[1], np.nan, dtype=np.float64)
    window = max(5, round(smoothed.shape[0] * 0.025))
    for column in valid_columns:
        peak = int(peak_rows[column])
        bottom = max(0, peak - window)
        top = min(smoothed.shape[0], peak + window + 1)
        values = smoothed[bottom:top, column]
        weights = np.clip(values - baseline[column], 0.0, None)
        if float(np.sum(weights)) > 1e-6:
            rows = np.arange(bottom, top, dtype=np.float64)
            centers[column] = float(np.average(rows, weights=weights))

    return centers


def _fark_goruntusunden_lazer_olc(
    red_score: np.ndarray,
) -> tuple[LazerOlcumu, float]:
    """Kırmızı fark görüntüsünden lazer çizgisinin orta noktalarını çıkarır."""
    area, height_scale = _lazer_alanini_hazirla(red_score)

    # Her sütundaki en güçlü kırmızı bölge lazer için aday kabul ediliyor.
    smoothed = cv2.GaussianBlur(area, (1, 5), 0)
    peak_rows = np.argmax(smoothed, axis=0)
    baseline = np.percentile(smoothed, 65, axis=0)
    peak_strength = np.max(smoothed, axis=0) - baseline

    strong_value = float(np.percentile(peak_strength, 80))
    signal_threshold = max(8.0, min(35.0, strong_value * 0.25))
    valid = peak_strength >= signal_threshold
    valid_columns = np.flatnonzero(valid)
    if len(valid_columns) < 40:
        raise ValueError("Lazer sinyali yeterince güçlü değil.")

    first_column = int(valid_columns[0])
    last_column = int(valid_columns[-1])
    length_ratio = (last_column - first_column + 1) / area.shape[1]
    fill_ratio = len(valid_columns) / max(1, last_column - first_column + 1)
    if length_ratio < LASER_MIN_LENGTH_RATIO or fill_ratio < 0.30:
        raise ValueError("Uzun bir lazer çizgisi bulunamadı.")

    centers = _cizgi_merkezlerini_bul(
        smoothed, peak_rows, baseline, valid_columns
    )

    used = np.flatnonzero(np.isfinite(centers))
    if len(used) < 40:
        raise ValueError("Lazer çizgisinin merkezi hesaplanamadı.")

    # Kısa boşluklar tamamlanıyor ve küçük titreşimler temizleniyor.
    x = np.arange(used[0], used[-1] + 1, dtype=np.float64)
    y = np.interp(x, used, centers[used])
    filter_size = min(11, len(y) if len(y) % 2 else len(y) - 1)
    if filter_size >= 3:
        y = _medyan_filtresi(y, filter_size)

    deviation = _cizgi_sapmasi(x, y, min_tolerance=2.0) * height_scale
    signal = float(np.median(peak_strength[valid]))
    # Kalite puanı yalnız yatay ve dikey adaylardan daha iyi olanı seçmek için kullanılıyor.
    quality = length_ratio * fill_ratio * max(signal, 1.0)
    return (
        LazerOlcumu(
            deviation=deviation,
            signal=signal,
            length_ratio=float(length_ratio),
        ),
        float(quality),
    )

"""Lazer görüntü çiftlerinden yerel çizgi sapmasını ve tekrar edilebilirliği hesaplar."""

from pathlib import Path
import argparse
import csv
import json
from datetime import datetime
from textwrap import dedent
import numpy as np
from PIL import Image, ImageDraw

def medfilt(a, n=21):
    """Profildeki tekil sıçramaları hareketli medyan ile azaltır."""
    h=n//2; p=np.pad(a,(h,h),mode='edge')
    return np.array([np.median(p[i:i+n]) for i in range(len(a))])

def profile(data, prefix, i):
    """RGB renk farkından her sütundaki lazer merkezini çıkarır."""
    on=np.asarray(Image.open(data/f"{prefix}_lazer_acik_{i:02d}.jpg").convert('RGB'),dtype=float)
    off=np.asarray(Image.open(data/f"{prefix}_lazer_kapali_{i:02d}.jpg").convert('RGB'),dtype=float)
    if on.shape != off.shape or min(on.shape[:2]) < 64:
        raise ValueError("Görüntü çifti aynı boyutta ve en az 64 x 64 piksel olmalı.")
    h,w,_=on.shape
    d=on-off
    score=d[:,:,0]-0.45*d[:,:,1]-0.45*d[:,:,2]
    score=np.clip(score,0,None)
    x0,x1=int(.22*w),int(.78*w); y0,y1=int(.30*h),int(.68*h)
    ys=[]
    for x in range(x0,x1):
        col=score[y0:y1,x]
        # Düşey renk farkı profilini yumuşatıp en güçlü bölgenin ağırlıklı merkezini bulur.
        k=np.ones(9)/9
        col=np.convolve(col,k,mode='same')
        if np.max(col) <= 0:
            raise ValueError("Analiz bölgesinde pozitif lazer sinyali bulunamadı.")
        p=int(np.argmax(col)); lo=max(0,p-3); hi=min(len(col),p+4)
        weights=col[lo:hi]
        ys.append(y0+(np.sum(np.arange(lo,hi)*weights)/np.sum(weights) if weights.sum()>0 else p))
    return np.arange(x0,x1), medfilt(np.asarray(ys),21)

def ana_program(argv=None):
    parser = argparse.ArgumentParser(description="Düz ve yükseltilmiş yüzeylerin lazer profillerini karşılaştırır.")
    parser.add_argument("--girdi", type=Path, required=True, help="12 lazer açık/kapalı JPEG görüntüsünün klasörü")
    parser.add_argument("--cikti", type=Path, help="Yeni sonuç klasörü; varsa üzerine yazılmaz")
    args = parser.parse_args(argv)
    DATA = args.girdi.resolve()
    if not DATA.is_dir():
        parser.error("Girdi klasörü bulunamadı.")
    for prefix in ("duz", "yukselti_10kat"):
        for state in ("acik", "kapali"):
            for i in range(1, 4):
                expected = DATA / f"{prefix}_lazer_{state}_{i:02d}.jpg"
                if not expected.is_file():
                    parser.error(f"Eksik görüntü: {expected.name}")
    OUT = args.cikti or (
        Path(__file__).resolve().parents[1] / "output" / "staj1" /
        ("yukselti_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    )
    if OUT.exists():
        parser.error("Çıktı klasörü zaten var; yeni bir klasör belirtin.")
    OUT.mkdir(parents=True, exist_ok=False)
    flat=[]; raised=[]
    for i in range(1,4):
        x,p=profile(DATA, 'duz',i); flat.append(p)
        _,p=profile(DATA, 'yukselti_10kat',i); raised.append(p)
    flat=np.vstack(flat); raised=np.vstack(raised)
    f=np.median(flat,axis=0); r=np.median(raised,axis=0)
    raw=r-f

    # Kenarlardaki kayma ve eğimi çıkararak orta bölgedeki yerel sapmayı ayırır.
    n=len(x); edge=(np.arange(n)<int(.18*n)) | (np.arange(n)>int(.82*n))
    coef=np.polyfit(x[edge],raw[edge],1)
    res=raw-np.polyval(coef,x)
    center=(np.arange(n)>int(.22*n)) & (np.arange(n)<int(.78*n))
    abs_center=np.abs(res[center])
    threshold=np.quantile(abs_center,.90)
    strong=center & (np.abs(res)>=threshold)
    signed=float(np.median(res[strong])); robust=float(np.median(np.abs(res[strong])))
    imax=int(np.argmax(np.abs(res[center])))
    cx=x[center]; cr=res[center]
    max_signed=float(cr[imax]); max_abs=float(abs(max_signed)); max_x=int(cx[imax])
    flat_rep=float(np.median(np.std(flat,axis=0)))
    raised_rep=float(np.median(np.std(raised,axis=0)))
    rep=max(flat_rep,raised_rep)

    result={
      'dataset':str(DATA),'camera_surface_distance_cm':30,
      'laser_offset_cm_approx':10,'laser_angle_deg_approx':60,
      'exposure_us':2500,'analysed_x_range_px':[int(x[0]),int(x[-1])],
      'setup_note':'Mesafe, açı ve pozlama deney düzenine ait sabit değerlerdir; görüntüden ölçülmez veya metadata dosyasından doğrulanmaz.',
      'robust_local_vertical_shift_px':round(robust,3),
      'signed_local_vertical_shift_px':round(signed,3),
      'maximum_local_vertical_shift_px':round(max_abs,3),
      'maximum_shift_x_px':max_x,
      'flat_repeatability_px':round(flat_rep,3),
      'raised_repeatability_px':round(raised_rep,3),
      'signal_to_repeatability_ratio':round(robust/rep,2) if rep else None,
      'image_coordinate_note':'Pozitif y aşağı yönlüdür.',
      'metric_note':'Milimetre dönüşümü için 10 kat kâğıdın gerçek yüksekliği ayrıca ölçülmelidir.'
    }
    (OUT/'wp5_analysis_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'wp5_profiles.csv').open('w',newline='',encoding='utf-8-sig') as q:
        wr=csv.writer(q); wr.writerow(['x_px','flat_y_px','raised_y_px','local_shift_px'])
        wr.writerows(zip(x,np.round(f,4),np.round(r,4),np.round(res,4)))

    # Profil ve yerel sapma grafiğini ek çizim kütüphanesi gerektirmeden oluşturur.
    W,H=1500,800; m=80
    im=Image.new('RGB',(W,H),'white'); dr=ImageDraw.Draw(im)
    dr.text((m,25),'Yerel Yükselti Lazer Çizgisi Analizi',fill='black')
    def poly(vals,color,yc,scale):
        xx=m+(x-x.min())/(x.max()-x.min())*(W-2*m)
        yy=yc+(vals-np.median(vals))*scale
        dr.line(list(zip(xx.astype(int),yy.astype(int))),fill=color,width=3)
    poly(f,'blue',260,5); poly(r,'red',260,5)
    dr.text((m,80),'Mavi: düz yüzey   Kırmızı: 10 kat yerel yükselti',fill='black')
    xx=m+(x-x.min())/(x.max()-x.min())*(W-2*m)
    yy=610-res*12
    dr.line(list(zip(xx.astype(int),yy.astype(int))),fill='purple',width=3)
    dr.line((m,610,W-m,610),fill='gray',width=1)
    dr.text((m,440),'Global eğim çıkarıldıktan sonra yerel düşey kayma (piksel)',fill='black')
    dr.text((m,730),f"Sağlam yerel kayma: {robust:.3f} px | Maksimum: {max_abs:.3f} px | Tekrar edilebilirlik: {rep:.3f} px",fill='black')
    im.save(OUT/'wp5_analysis_summary.png')

    direction = 'aşağı' if signed > 0 else ('yukarı' if signed < 0 else 'kayma yok')
    ratio_text = f'{robust/rep:.2f}' if rep > 0 else 'hesaplanamadı (tekrar sapması sıfır)'
    md=f'''
    # Yerel Yükselti Sayısal Analizi

    ## Analiz çıktısı

    - Sağlam yerel düşey çizgi kayması: **{robust:.3f} piksel**
    - İşaretli kayma: **{signed:.3f} piksel** (görüntü koordinatında {direction})
    - En büyük yerel kayma: **{max_abs:.3f} piksel** (x = {max_x} piksel)
    - Düz yüzey tekrar edilebilirliği: **{flat_rep:.3f} piksel**
    - Yükseltilmiş yüzey tekrar edilebilirliği: **{raised_rep:.3f} piksel**
    - Sinyal/tekrar edilebilirlik oranı: **{ratio_text}**

    Üç tekrarın medyan profilleri kullanıldı. Lazer açık ve kapalı görüntülerin renk farkından çizgi merkezi çıkarıldı; kenar bölgelerinden hesaplanan global eğim kaldırılarak yalnızca orta bölgedeki yerel sapma ölçüldü. Bu değerler verilen görüntü çiftlerini betimler; tek başına ölçüm doğruluğu veya kusur sınıflandırma başarısı kanıtı değildir.

    > Milimetre dönüşümü yapılmadı. Bunun için 10 kat kâğıdın gerçek yüksekliği kumpas/cetvelle ölçülmeli veya bilinen yüksekliklerle çok noktalı kalibrasyon yapılmalıdır.
    '''
    (OUT/'WP5_SAYISAL_ANALIZ.md').write_text(dedent(md).lstrip(),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(ana_program())

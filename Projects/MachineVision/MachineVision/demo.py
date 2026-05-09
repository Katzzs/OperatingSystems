# Sistema ng Pagkilala ng Plaka ng Sasakyan
# =======================================

def main():
    print("\n" + "="*60)
    print("DEMONSTRASYON: SISTEMA NG PAGKILALA NG PLAKA NG SASKYAN")
    print("="*60 + "\n")
    
    # Introduksyon
    print("Maligayang pagdating sa Sistema ng Pagkilala ng Plaka ng Sasakyan!")
    print("Ipinapakita ng sistemang ito ang kakayahan ng computer vision sa pagkilala ng plaka ng sasakyan.\n")
    
    # Bahagi 1: Pangkalahatang-ideya ng Sistema
    print("="*60)
    print("PANGKALAHATANG-IDEYA NG SISTEMA")
    print("="*60)
    print("""
    • Real-time na pagkilala ng plaka ng sasakyan
    • Kaya ang mga nakalimbag at sulat-kamay na plaka
    • Awtomatikong pagsuri ng tamang format ng plaka
    • Gumagamit ng dalawang OCR engine para mas tumpak
    """)
    
    # Bahagi 2: Mga Pangunahing Tampok
    print("\n" + "="*60)
    print("MGA PANGUNAHING TAMPOK")
    print("="*60)
    print("""
    1. DALAWANG URI NG OCR
       - Tesseract OCR para sa karaniwang nakalimbag na teksto
       - EasyOCR para mas mabasa ang sulat-kamay
       - Awto-switching sa pagitan ng dalawang engine
    
    2. MAHUSAY NA PAGHAHANDA NG LARAWAN
       - Pag-ayos ng liwanag at kontrast
       - Pag-alis ng "ingay" sa larawan
       - Pagpapalinaw ng teksto
       - Pag-tama ng anggulo ng larawan
    
    3. MAAASAHANG PAGKILALA
       - Tumpak na pagkilala ng format ng plaka sa Pilipinas
       - May sukat ng katiyakan (confidence level)
       - Maraming paraan ng pagtutugma ng pattern
    """)
    
    # Bahagi 3: Mga Tagubilin sa Paggamit
    print("\n" + "="*60)
    print("MGA TAGUBILIN SA PAGGAMIT")
    print("="*60)
    print("""
    Kapag lumabas ang camera:
    1. Pindutin ang 'DETECT' button para mag-scan ng plaka
    2. Iproseso ng sistema ang larawan at ipapakita ang resulta
    3. Makikita sa resulta ang:
       - Numero ng plaka
       - Antas ng katiyakan
       - Kung wasto ang format
    4. Pindutin ang 's' para i-save ang larawan
    5. Pindutin ang 'q' para umalis
    """)
    
    # Bahagi 4: Mga Pangangailangan
    print("\n" + "="*60)
    print("MGA PANGANGAILANGAN")
    print("="*60)
    print("""
    • Python 3.x
    • OpenCV para sa image processing
    • Tesseract OCR
    • EasyOCR para sa sulat-kamay
    • Webcam (minimum 1280x720 resolution)
    """)
    
    # Bahagi 5: Pagsisimula
    print("\n" + "="*60)
    print("PAGSISIMULA NG DEMO")
    print("="*60)
    print("\nInihahanda ang camera...")
    print("Iniloload ang mga OCR engine...")
    print("Handa na ang sistema!")
    print("\n" + "="*60)
    print("TIP: Siguraduhing maliwanag at malinaw ang plaka na kukuhanan")
    print("="*60 + "\n")
    
    print("Para simulan ang aktwal na demo, patakbuhin ang main na MachineVision.py")
    print("Bubuksan nito ang iyong webcam at magsisimula nang mag-proseso.\n")

if __name__ == "__main__":
    main()
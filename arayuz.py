import streamlit as st
from ajan import gemini_parse
from filtrele import filtrele

st.title("ENTES MPR Ürün Seçim Ajanı")

if "mesajlar" not in st.session_state:
    st.session_state.mesajlar = []


def asistan_yaniti_goster(msg: dict) -> None:
    for uyari in msg.get("uyarilar", []):
        st.warning(uyari)
    if msg.get("gerekce"):
        st.markdown(msg["gerekce"])
    if msg.get("tablo") is not None:
        st.dataframe(msg["tablo"], hide_index=True)
    for bilgi in msg.get("bilgiler", []):
        st.info(bilgi)
    if msg.get("icerik"):
        st.markdown(msg["icerik"])
    if msg.get("kaynak"):
        st.caption(msg["kaynak"])


def yanit_uret(metin: str) -> dict:
    kriterler, degerlendirilemeyen = gemini_parse(metin)

    msg: dict = {
        "uyarilar": [f"Şu isteği tabloda değerlendiremedim: **{m}**" for m in degerlendirilemeyen],
        "gerekce": None,
        "tablo": None,
        "bilgiler": [],
        "icerik": None,
        "kaynak": None,
    }

    if not kriterler:
        msg["icerik"] = "Hiçbir filtre kriteri tanımlanamadı. Lütfen daha açık belirtin."
        return msg

    filtre_str = " · ".join(f"`{k}` = {v}" for k, v in kriterler.items())
    msg["gerekce"] = f"**Uygulanan filtreler:** {filtre_str}"

    sonuc, atlanan = filtrele(kriterler)
    if atlanan:
        msg["uyarilar"].append(
            f"Şu kriterler bu kategoride yok, uygulanmadı: {', '.join(atlanan)}"
        )

    if sonuc.empty:
        for kolon, deger in kriterler.items():
            ara, _ = filtrele({kolon: deger})
            if ara.empty:
                msg["uyarilar"].append(f"Şu kriteri karşılayan model yok: **{kolon} = {deger}**")
            else:
                modeller = ", ".join(ara["Model"].tolist())
                msg["bilgiler"].append(f"`{kolon} = {deger}` → {len(ara)} model: {modeller}")
        msg["icerik"] = "Bu kriterlerin kombinasyonunu karşılayan model yok. ENTES uygulama mühendisine danışın."
    else:
        msg["tablo"] = sonuc
        msg["icerik"] = f"**{len(sonuc)} model eşleşti.**"
        msg["kaynak"] = "Kaynak: urunler.csv"

    return msg


# Geçmiş mesajları göster
for mesaj in st.session_state.mesajlar:
    with st.chat_message(mesaj["rol"]):
        if mesaj["rol"] == "user":
            st.markdown(mesaj["icerik"])
        else:
            asistan_yaniti_goster(mesaj)

# Yeni girdi
if girdi := st.chat_input("İhtiyacınızı tarif edin..."):
    # Kullanıcı mesajı
    st.session_state.mesajlar.append({"rol": "user", "icerik": girdi})
    with st.chat_message("user"):
        st.markdown(girdi)

    # Asistan yanıtı
    with st.chat_message("assistant"):
        with st.spinner("Analiz ediliyor..."):
            yanit = yanit_uret(girdi)
        asistan_yaniti_goster(yanit)

    yanit["rol"] = "assistant"
    st.session_state.mesajlar.append(yanit)

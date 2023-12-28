import os
import streamlit as st
import elevenlabs as el
from dotenv import load_dotenv

load_dotenv()

@st.cache_data
def get_voices() -> list[el.Voice]:
  return list(el.voices())

@st.cache_data
def get_models() -> list[el.Model]:
  return list(el.Models.from_api())

if __name__ == "__main__":
  st.title("🎧 ElevenLabs Speech")
  
  with st.sidebar:
    el_key = st.text_input("API Key _(optional)_", os.getenv("ELEVENLABS_API_KEY"), type="password")
    if el_key:
      el.set_api_key(el_key)
          
    available_models = get_models()
    available_model_ids = [m.model_id for m in available_models]
    available_model_names = [m.name for m in available_models]
    model_name = st.selectbox("Model", available_model_names)
    if model_name:
      model_index = available_model_names.index(model_name)
      model_id = available_model_ids[model_index]
  
    el_voices = get_voices()
    el_voice_names = [f"{voice.name} ({voice.category})" for voice in el_voices]
    el_voice = st.selectbox("Voice", el_voice_names)
    if el_voice:
      el_voice_index = el_voice_names.index(el_voice)
      el_voice_details = el_voices[el_voice_index]
      el_voice_id = el_voice_details.voice_id
      
      # voice sample
      if el_voice_details.preview_url:
        st.audio(el_voice_details.preview_url, format="audio/mp3")
      
      with st.expander("Voice Options"):      
        # voice settings
        if el_voice_details.settings:
          voice_settings = el_voice_details.settings
        else:
          el_voice_details.fetch_settings()
          voice_settings = el_voice_details.settings
        if not voice_settings:
          print("default settings")
          voice_settings = el.Voice.default_settings()
        
        stability = st.slider(
          "Stability", 
          0.0, 
          1.0, 
          value=voice_settings.stability, 
          help="Increasing stability will make the voice more consistent between re-generations, but it can also make it sounds a bit monotone. On longer text fragments we recommend lowering this value."
        )
        simarlity_boost = st.slider(
          "Clarity + Simalarity Enhancement",
          0.0,
          1.0,
          value=voice_settings.similarity_boost,
          help="High enhancement boosts overall voice clarity and target speaker similarity. Very high values can cause artifacts, so adjusting this setting to find the optimal value is encouraged."
        )
        style = st.slider(
          "Style Exaggeration",
          0.0,
          1.0,
          value=voice_settings.style,
          help="High values are recommended if the style of the speech should be exaggerated compared to the uploaded audio. Higher values can lead to more instability in the generated speech. Setting this to 0.0 will greatly increase generation speed and is the default setting."
        )
  
  st.subheader("Text")
  text_to_generate = st.text_area("Text", label_visibility="collapsed")
  generate_bnt = st.button("Generate Speech")
  
  if generate_bnt and text_to_generate:
    audio = el.generate(
      text=text_to_generate,
      model=model_id,
      voice = el.Voice(
        voice_id=el_voice_id,
        settings=el.VoiceSettings(stability=stability, similarity_boost=simarlity_boost, style=style)
      )
    )
    st.audio(audio)
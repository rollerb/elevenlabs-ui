import el_audio, os, uuid, shutil, time
import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd
from pydub import AudioSegment
from dotenv import load_dotenv
from dialogues import Character, Dialogue, get_voice_id, save_dialogue, characters_match, export_dialogue
from sidebar import create_sidebar
from saved_dialogues import get_selected_characters, get_selected_dialogue, on_load_saved, create_saved_dialogues
from generate import create_dialogue_generation, create_continue_dialogue
from utils import log

load_dotenv()
plt.style.use('dark_background')

def show_final_audio() -> bool:
  return "final_audio" in st.session_state and st.session_state.final_audio
    

if __name__ == "__main__":
  st.set_page_config(layout="wide")
  
  if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())  
    log("session id: " + st.session_state.session_id)
  
  st.title("🎧 ElevenLabs Dialogue")
  
  sidebar = create_sidebar()
    
  if sidebar.el_key:
    saves = create_saved_dialogues(sidebar.voices)    
    
    st.header("Characters")
    st.markdown("This is where you setup and define what characters are in your dialogue along with what voice the character should use. You can use the `Voice Explorer` in the sidebar if you want to hear what a voice sounds like.")
    with st.expander("**WARNING**: changing characters can clear the dialogue"):
      st.info("Adding or removing characters and modifying names will clear or reset the dialogue. That being said, you can freely change the voices without affecting the dialogue.")
    
    if saves.selected_save_name:
      character_data = [c.to_dict() for c in get_selected_characters(saves)]
    else:
      character_data = []    
    character_table = st.data_editor(
      pd.DataFrame(character_data, columns=["Name", "Voice", "Description"]),
      use_container_width=True,
        hide_index=True,
      num_rows="dynamic",
      key="character_table",
      column_config={
        "Name": st.column_config.TextColumn(
          "Name",
          required=True,
          width="small"
        ),
        "Voice": st.column_config.SelectboxColumn(
          "Voice",
          options=sidebar.voice_names,
          required=True,
          width="small"
        ),
        "Description": st.column_config.TextColumn(
          "Description",
          required=False,
          width="large"
        )
      }    
    )
  else:
    character_table = pd.DataFrame()
    st.warning("Please enter an API key in the sidebar.")
  
  characters_available = not character_table.empty
  if characters_available:
    characters: list[Character] = []
    for _, row in character_table.iterrows():
      c = Character(
        row["Name"], 
        row["Voice"], 
        get_voice_id(row["Voice"], sidebar.voices),
        description=row["Description"]
      )
      characters.append(c)
    character_names = [character.name for character in characters]
    
    st.header("Dialogue")
    st.markdown("This is where you write or generate the dialogue. The audio dialogue will use the model and voice settings defined in the sidebar. You can generate the audio multiple times, so click `Generate Audio Dialogue` as often as you would like.")
    
    generated_dialogue = create_dialogue_generation(sidebar, saves, characters)

    if "generated_dialogue" in st.session_state:
      characters_matched = characters_match(character_table, st.session_state["generated_dialogue"])
      if not characters_matched:
        log("characters do not match between generated dialogue and current characters")
        st.toast("It appears that the speakers in the dialogue do not match the characters you have defined.", icon="👎")
        del st.session_state["generated_dialogue"]
        
    if generated_dialogue is not None: 
      log("use just created generated dialogue")     
      st.session_state["generated_dialogue"] = generated_dialogue
      dialogue_df = generated_dialogue
    elif "generated_dialogue" in st.session_state:
      log("using cached generated dialogue") 
      dialogue_df = st.session_state["generated_dialogue"]
    elif saves.selected_save_name:
      log("using loaded dialogue") 
      dialogue_data = [d.to_dict(without_line=True) for d in get_selected_dialogue(saves)]
      dialogue_df = pd.DataFrame(dialogue_data, columns=["Speaker", "Text"])
    else:
      log("creating new empty dialogue") 
      dialogue_df = pd.DataFrame([], columns=["Speaker", "Text"])
    
    dialogue_table = st.data_editor(
      dialogue_df,
      use_container_width=True,
      num_rows="dynamic",
      hide_index=True,
      key="dialogue_table",
      column_config={
        "Speaker": st.column_config.SelectboxColumn(
          "Speaker",
          options=character_names,
          required=True,
          width="small"
        ),   
        "Text": st.column_config.TextColumn(
          "Text",
          required=True,
          width="large"
        )
      }
    )    
    
    # save dialogue to file
    if saves.save_dialogue and saves.save_dialogue_name:
      save_dialogue(character_table, dialogue_table, sidebar.voices, f"./session/{st.session_state.session_id}/saves/{saves.save_dialogue_name}.json")
      st.toast("Dialogue has been saved. You will have to click refresh to see it.", icon="👍")
    if saves.prepare_export:
      export_dialogue(character_table, dialogue_table, sidebar.voices, f"./session/{st.session_state.session_id}/export/dialogue.txt")
      st.rerun()
    
    # extract Dialogues from the dialogue table
    if not dialogue_table.empty:
      dialogue: list[Dialogue] = []
      for i, row in dialogue_table.iterrows():
        try:
          character_index = character_names.index(row["Speaker"])
          character = characters[character_index]
          dialogue.append(Dialogue(character, i+1, row["Text"]))
        except:
          print(f"Error: {row['Speaker']} is not a valid character.")
          pass        
      dialogue.sort(key=lambda x: x.line)
      
      # continue generated dialogue
      if sidebar.openai_api_key and not dialogue_table.empty:
        continue_btn = st.button("Cotinue Dialogue", use_container_width=True, help="This uses options set in `Dialogue Generation` to continue the dialogue.")
        if continue_btn:
          generated_dialogue = create_continue_dialogue(sidebar, characters, dialogue)     
          if generated_dialogue is not None: 
            st.session_state["generated_dialogue"] = generated_dialogue
            st.rerun()
      
      # generate audio dialogue files
      existing_audio_files = el_audio.get_generated_audio()
      show_existing_audio_files = len(existing_audio_files) > 0 and "imported_file" in st.session_state
      col1, col2 = st.columns([1, 1])
      with col1:      
        generate_btn = st.button("Generate Audio Dialogue", use_container_width=True) 
      if show_existing_audio_files:     
        with col2:
          use_existing_btn = st.button(
            "Use Existing Audio", 
            use_container_width=True, 
            help="Use the existing audio files imported from a project.")
          if use_existing_btn:
            st.session_state["audio_files"] = existing_audio_files
      if generate_btn:
        st.session_state["final_audio"] = False
        el_audio.clear_audio_files()
        audio_files: list[str] = []
        progress_text = "Generating audio..."
        if "audio_process_error" in st.session_state:
          del st.session_state["audio_process_error"]
        generate_audio_bar = st.progress(0, text=progress_text)
        for i, line in enumerate(dialogue):
          try:
            audio_file = el_audio.generate_and_save(line.text, line.character.voice_id, line.line, sidebar) 
            audio_files.append(audio_file)
          except Exception as e:
            print(e)
            st.session_state["audio_process_error"] = f"{line.character.name} with the voice {line.character.voice} (voice_id: {line.character.voice_id})"
            break
          generate_audio_bar.progress(round((i+1) / len(dialogue), 2), text=progress_text)          
        generate_audio_bar.empty()
        
        if "audio_process_error" in st.session_state:
          st.error(f"""An error occured while generating the audio. Please check your API key.
          Error occurred while processing: {st.session_state.audio_process_error}
          """)
          if "audio_files" in st.session_state:
            del st.session_state["audio_files"]
        else:
          st.session_state["audio_files"] = audio_files
      
      if saves.prepare_project:
        export_dialogue(character_table, dialogue_table, sidebar.voices, f"./session/{st.session_state.session_id}/export/dialogue.txt")
        el_audio.export_audio()
        project_path = f"./session/{st.session_state.session_id}/project"
        os.makedirs(project_path, exist_ok=True)
        shutil.make_archive(f"{project_path}/project", "zip", f"./session/{st.session_state.session_id}/export")
        st.rerun()
      
      if "audio_files" in st.session_state:   
        # display generated audio
        st.header("Audio Dialogue")
        st.markdown("The dialogue text has now been coverted into audio. You can listen to the audio by clicking the play button. If you want to regenerate the audio, you can click the `Generate Audio Dialogue` button above. If you are happy with the audio, you can join the audio files together by clicking the `Join Dialogue` button below. You can also click the `Redo` button to regenerate the audio for a specific line.")
        with st.expander("**WARNING**: deleting dialogue lines requires audio regeneration"):
          st.info("If you delete dialogue lines, you will have to regenerate the audio by clicking the `Generate Audio Dialogue` button above. Adding or modifying dialogue lines will not require regeneration of all lines, but you will likely need to click the `Redo` button for the affected lines.")
                    
        for i, line in enumerate(dialogue):
          st.markdown(f"{i + 1}. **{line.character.name}**: \"{line.text}\"")
          
          col1, col2 = st.columns([9, 1])
          with col1:     
            audio_file = f"./session/{st.session_state.session_id}/audio/line{line.line}.mp3"
            if os.path.exists(audio_file):     
              with open(audio_file, "rb") as audio:  
                st.audio(audio)
            else:
              st.markdown("Audio file not found. Please click the `Redo` button.")       
          with col2:
            redo_key = f"redo_{line.line}"
            redo_btn = st.button("Redo", key=redo_key)
          if redo_btn:
            with st.spinner("Generating audio..."):
              log(f"regenerating audio for {redo_key} for {line.character.name} with {line.character.voice}")
              el_audio.generate_and_save(line.text, line.character.voice_id, line.line, sidebar)
            st.rerun()
          with st.expander("Edit Audio"):
            st.markdown("### 🔊 Basic Settings")
            line_volume = st.slider(
              "Adjust Speech Volume (dB)",
              -25, 
              25, 
              0, 
              1, 
              key=f"volume_{line.line}"
            )
            st.markdown("### 💥 Special Effect")
            effect_name = st.selectbox(
              "Effects", 
              el_audio.get_effect_names(), 
              index=None, 
              label_visibility="collapsed", 
              placeholder="Select an effect",
              key=f"effect_{line.line}"
            )
            if effect_name:
              effect_path = el_audio.get_effect_path(effect_name)
              st.audio(effect_path)
              speech_duration = el_audio.get_audio_duration(audio_file)
              
              effect_volume = st.slider(
                "Adjust Effect Volume (dB)",
                -25, 
                25, 
                0, 
                1, 
                key=f"effect_volume_{line.line}"
              )              
              effect_start = st.slider(
                "Effect Start Time (seconds)", 
                0.0, 
                speech_duration, 
                0.0, 
                0.1, 
                key=f"effect_start_{line.line}",
                help="When the effect should start playing. The effect will cut off if it exceeds the speech."
              )              
              effect_repeat = st.slider(
                "Effect Repeat",
                1,
                10,
                1,
                1,
                key=f"effect_repeat_{line.line}",
                help="If you want the effect to repeat itself."
              )
            else:
              effect_path = None
              effect_start = None
              effect_volume = None
              effect_repeat = None
              
            preview_effect = st.button(
              "Preview", 
              key=f"preview_{line.line}",
              use_container_width=True
            )
            if preview_effect:
              effect_audio, preview_audio = el_audio.preview_audio(
                audio_file, 
                line_volume, 
                effect_path,
                effect_start,
                effect_volume,
                effect_repeat
              )
              
              if effect_name:
                col1, col2 = st.columns([1, 1])
                with col1:
                  st.markdown("<p style='font-size:14px'>Effect Preview</p>", unsafe_allow_html=True)
                  st.audio(effect_audio, format="audio/wav")
                with col2:
                  st.markdown("<p style='font-size:14px'>Overlay Preview</p>", unsafe_allow_html=True)              
                  st.audio(preview_audio, format="audio/wav")
              else:
                st.audio(preview_audio, format="audio/wav")
            
            apply_edits = st.button("Apply", key=f"apply_{line.line}", use_container_width=True)
            if apply_edits:
              _, new_line_audio = el_audio.edit_audio(
                audio_file, 
                line_volume, 
                effect_path,
                effect_start,
                effect_volume,
                effect_repeat                
              )
              new_line_audio.export(audio_file, format="mp3")
              log(f"saving audio {audio_file}")
              st.rerun()
      
      # join final audio
      if "audio_files" in st.session_state:
        join_dialogue = st.button("Join Dialogue")
        line_indices = [d.line for d in dialogue]
        if join_dialogue:          
          el_audio.join_audio(line_indices, sidebar.join_gap)
          st.session_state["final_audio"] = True
      
      # show final audio
      if show_final_audio():
        st.header("Final Dialogue")
        st.markdown("Here is the final dialogue with all the lines joined together. The gap between the lines is controlled by the `Gap Between Dialogue` setting in the sidebar under `Dialogue Options`. If you are unhappy about specific lines, then just click the `Redo` button on the line above and click `Join Dialogue` again.")        
        
        with st.expander("Background Audio"):
          background_names = el_audio.get_background_audio()
          st.markdown("You can add background audio to the final dialogue. If you want to remove the background audio, you will have to regenerate the final dialogue by clicking `Join Dialogue`.")
          background_name = st.selectbox(
            "Background Audio", 
            background_names, 
            index=None, 
            label_visibility="collapsed", 
            placeholder="Select a background audio"
          )
          if background_name:
            st.audio(el_audio.get_background_file_from_name(background_name))
          col1, col2 = st.columns([1, 3])
          with col1:
            fade_in = st.toggle("Fade In", value=True)
            fade_out = st.toggle("Fade Out", value=True)
          with col2:
            lower_db = st.slider("Lower Background Volume (dB)", 0, 15, 0, 1, help="lowers the background audio by specified decibels")

          log(f"Background settings: Fade In:{fade_in}, Fade Out:{fade_out}, Lower Db:{lower_db}")

          add_background_btn = st.button("Add Background", use_container_width=True)
          if add_background_btn and background_name:
            with st.spinner("Adding background audio..."):
              el_audio.apply_background_audio(background_name, fade_in, fade_out, lower_db)
              st.toast("Background audio has been added.", icon="👍")
        
        if "background_added" in st.session_state:
          log("using background audio")
          dialogue_path = f"./session/{st.session_state.session_id}/audio/dialogue_background.mp3"
        else:
          dialogue_path = f"./session/{st.session_state.session_id}/audio/dialogue.mp3"
                  
        st.audio(dialogue_path)
        fig = el_audio.generate_waveform(dialogue_path)       
        st.pyplot(fig)
    
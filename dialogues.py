import json
import pandas as pd
from pathlib import Path
from elevenlabs import Voice
from el_audio import get_voice_id

class Character:
  def __init__(self, name: str, voice: str, voice_id: str) -> None:
    self.name = name
    self.voice = voice
    self.voice_id = voice_id
  
  def to_dict(self) -> dict:
    return {
      "Name": self.name,
      "Voice": self.voice,
      "Voice_ID": self.voice_id
    }
  
  def __str__(self):
    return f"{self.name};{self.voice};{self.voice_id}"
  
  def __repr__(self) -> str:
    return self.__str__()


class Dialogue:
  def __init__(self, character: Character, line: int, text: str):
    self.character = character
    self.line = line
    self.text = text
  
  def to_dict(self, without_line: bool = False) -> dict:
    if without_line:
      return {
        "Speaker": self.character.name,
        "Text": self.text
      }
    else:
      return {
        "Speaker": self.character.name,
        "Line": self.line,
        "Text": self.text
      }
    
  def __str__(self):
    return f"[{self.line}] {self.character.name}: {self.text}"

def generate_dialogue_details(
  characters_df: pd.DataFrame, 
  dialogue_df: pd.DataFrame, 
  voices: list[Voice]
) -> dict:
  """Generate dialogue details in a common format suitiable for JSON."""
  characters: list[Character] = []
  for i, c in characters_df.iterrows():
    characters.append(Character(c["Name"], c["Voice"], get_voice_id(c["Voice"], voices)))
  dialogue: list[Dialogue] = []
  for i, d in dialogue_df.iterrows():
    character = next((c for c in characters if c.name == d["Speaker"]), None)
    dialogue.append(Dialogue(character, i, d["Text"]).to_dict()) 
  dialogue_details = {
    "characters": [c.to_dict() for c in characters],
    "dialogue": dialogue
  }  
  return dialogue_details 

def load_saved_dialogues() -> dict:
  """Load saved dialogues from the saves directory."""
  directory = Path("./saves")
  names = {}
  for json_file in directory.glob("*.json"):
    characters = []
    dialogues = []
    with open(json_file, "r") as f:
      data = json.load(f)
      for character in data["characters"]:
        characters.append(Character(character["Name"], character["Voice"], character["Voice_ID"]))
      for dialogue in data["dialogue"]:
        character = next((c for c in characters if c.name == dialogue["Speaker"]), None)
        dialogues.append(Dialogue(character, dialogue["Line"], dialogue["Text"]))
    names[json_file.stem] = { "characters": characters, "dialogue": dialogues }
  return names

def load_dialogues_with_names() -> (list[str], dict):
  """Load saved dialogues with their names from the saves directory."""
  saved_dialogues = load_saved_dialogues()
  saved_names = list(saved_dialogues.keys())  
  return saved_names, saved_dialogues

def save_dialogue(
  characters: pd.DataFrame, 
  dialogue: pd.DataFrame, 
  voices: list[Voice],
  save_filename: str
) -> None:
  """Save a dialogue to a JSON file."""""
  dialogue_details = generate_dialogue_details(characters, dialogue, voices)      
  with open(f"./saves/{save_filename}.json", "w") as f:
    json.dump(dialogue_details, f, indent=2)  
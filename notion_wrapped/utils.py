import requests
import json
import re

database_page_title = "database_page"

## This function isn't used for the Notion wrapped program, but can be used with recurse.py for easy interaction with the Notion API to update database properties
def update_property(block, property_name, property_value, api_token):
  def update_block_property(block, property_name, property_value):
    if block['object'] == "page":
      block_type = database_page_title
    else:
      block_type = block['type']

    if block_type != database_page_title:
      return None
    
    if property_name == "icon":
      payload = {
        "icon": {
          "type": "emoji",
          "emoji": property_value
        }
      }
      return payload

    property_type = block["properties"][property_name]["type"]
    if property_type == "files":
      payload = {
        "properties": {
          property_name: {
            "files": [
              {
                "type": "external",
                "name": "file or url",
                "external": {
                  "url": property_value
                }
              }
            ]
          }
        }
      }
    elif property_type == "rich_text":
      payload = {
        "properties": {
          property_name: {
            "rich_text": [
              {
                "type": "text",
                "text": {
                  "content": property_value
                }
              }
            ]
          }
        }
      }
    elif property_type == "number":
      payload = {
        "properties": {
          property_name: {
            "number": int(property_value.replace(',', ''))
          }
        }
      }

    return payload
    

  page_id = block["id"]
  url = f"https://api.notion.com/v1/pages/{page_id}"
  headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
  }
  payload = update_block_property(block, property_name, property_value)
  if payload:
    response = requests.patch(url, headers=headers, json=payload)
    return response.status_code == 200
  return False


def get_words(block, just_title=False, just_property=None):
  if block['object'] == "page":
    block_type = database_page_title
  else:
    block_type = block['type']

  def extract_text(property_value):
    if not property_value:
      return ""
    property_type = property_value['type']
    # print(json.dumps(property_value, indent=4))
    if property_type in ['title', 'rich_text']:
      return " ".join(text['plain_text'] for text in property_value[property_type])
    elif property_type in ['select', 'multi_select', 'files'] and property_value[property_type]:
      return " ".join(item['name'] for item in property_value[property_type] if isinstance(item, dict))
    elif property_type in ["number"] and property_value[property_type]: # removed , "date"
      return str(property_value[property_type])
    return ""

  if block_type == "child_page":
    return block[block_type]["title"]
  
  if block_type == "child_database":
    return block[block_type]["title"]

  elif block_type == database_page_title:
    if just_title:
      for prop_name, prop_value in block["properties"].items():
        if prop_value["type"] == "title":
          return extract_text(prop_value)
      return ""
    if just_property:
      return extract_text(block["properties"].get(just_property))
    return " ".join(extract_text(prop) for prop in block["properties"].values())

  elif block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item', 'to_do', 'toggle', 'quote', 'callout', 'code']:
    return " ".join(text['plain_text'] for text in block[block_type]['rich_text'])

  return ""


def print_json(self, json_string):
  print(json.dumps(json_string, indent=4))
      

def get_user_name(user_id, api_token):
  url = f"https://api.notion.com/v1/users/{user_id}"
  headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
  }
  response = requests.get(url, headers=headers)
  response_json = response.json()
  return response_json.get('name', 'N/A')

def count_words_in_text(text):
  words = re.findall(r'\w+', text.lower())
  return len(words)

def extract_notion_id(self, url):
  pattern = r'[a-f0-9]{32}'
  match = re.search(pattern, url)
  return match.group(0) if match else None


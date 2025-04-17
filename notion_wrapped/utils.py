import requests
import json
import re

database_page_title = "database_page"


def get_words(block, just_title=False, just_property=None):
  if not block:
    return ""

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
    elif property_type in ["number", "date"] and property_value[property_type]: # removed then replaced, "date"
      return str(property_value[property_type])
    return ""

  if just_property == 'icon' and block.get('icon'):
    return block["icon"]["emoji"]

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
    return " ".join(extract_text(prop) for prop in reversed(list(block["properties"].values())))

  elif block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item', 'numbered_list_item', 'to_do', 'toggle', 'quote', 'callout', 'code']:
    return " ".join(text['plain_text'] for text in block[block_type]['rich_text'])

  return ""

def property_is_set(block, property_name):
  current_property = get_words(block, just_property=property_name)
  if current_property:
    print(f"{property_name} already set")
    return True
  return False

def print_json(json_string):
  print(json.dumps(json_string, indent=4))

def count_words_in_text(text):
  words = re.findall(r'\w+', text.lower())
  return len(words)

def extract_notion_id( url):
  pattern = r'[a-f0-9]{32}'
  match = re.search(pattern, url)
  return match.group(0) if match else None

def create_reducing_function(joining_function, block_reducing_function):
  def reducing_function(parent_block, child_results=None):
    child_results = child_results or []
    child_results = [result for result in child_results if result]
    return joining_function([block_reducing_function(parent_block)] + child_results)
  return reducing_function
  # I think this joining part should actually be more configurable by the joining function in order to have a fully general create_reducing_function function

  # ideally the reduce function should take in a accumulator and current value, and return the accumulator, but I think this doesn't quite work because it needs to do the function on the new values separately and the n combine them. Because of the multipled workers, maybe I should have it not work for multiple workers then.

add_text = create_reducing_function(lambda x: "\n".join(x), get_words)
add_word_count = create_reducing_function(sum, lambda x: count_words_in_text(get_words(x)))